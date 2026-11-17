import json
import sqlite3
from contextlib import closing
from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent


def write_report(db_path, output):
    translations_path = ROOT / "descriptions.zh.json"
    translations = json.loads(translations_path.read_text(encoding="utf-8"))
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("""
            SELECT current.*, current.stars - week.stars AS week_delta
            FROM daily_star_growth AS current
            LEFT JOIN trending_snapshots AS week
              ON week.repository = current.repository
              AND week.snapshot_date = date(current.snapshot_date, '-7 days')
            WHERE current.snapshot_date = (
                SELECT MAX(snapshot_date) FROM trending_snapshots
                WHERE repository = current.repository
            )
            ORDER BY current.snapshot_date DESC, current.rank
        """).fetchall()
        history = {}
        for snapshot in db.execute(
            "SELECT repository, snapshot_date, stars FROM trending_snapshots ORDER BY snapshot_date DESC"
        ):
            history.setdefault(snapshot["repository"].casefold(), []).append(
                f"<li>{escape(snapshot['snapshot_date'])} · {snapshot['stars']:,} Star</li>"
            )
    date = rows[0]["snapshot_date"] if rows else "暂无数据"
    observed = sum(row["snapshot_date"] == date for row in rows)
    cards = []
    for row in rows:
        original = row["description"] or ""
        description = translations.get(original, original)
        name = escape(row["repository"])
        url = quote(row["repository"], safe="/")
        snapshots = "".join(history[row["repository"].casefold()])
        delta = row["star_delta"]
        percent = row["growth_percent"]
        change = "—" if delta is None else f"{delta:+,}"
        if percent is not None:
            change += f" ({percent:+.1f}%)"
        week = row["week_delta"]
        weekly_change = "—" if week is None else f"{week:+,}"
        cards.append(f"""
<tr data-stars="{row['stars']}" data-date="{escape(row['snapshot_date'])}" data-week="{week if week is not None else ''}"
 data-growth="{percent if percent is not None else ''}"><td class="project"><a href="https://github.com/{url}">{name}</a>
<small>{escape(description)}</small>
<details><summary>星数历史</summary><ul>{snapshots}</ul></details></td>
<td><span class="language">{escape(row['language'] or '—')}</span></td><td class="num">{row['stars']:,}</td>
<td>{escape(row['snapshot_date'])}</td><td class="num">{change}</td><td class="num">{weekly_change}</td></tr>""")
    output.write_text(f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub 热门项目工作台</title>
<style>
* {{ box-sizing:border-box }}
:root {{ color-scheme:light; --ink:#182922; --muted:#52655a; --line:#dce5de; --accent:#176644 }}
body {{ margin:0;background:#f2f5ef;color:var(--ink);font:15px/1.55 "Instrument Sans",system-ui,sans-serif }}
main {{ max-width:1360px;margin:auto;padding:clamp(16px,4vw,56px) }}
header {{ padding:clamp(22px,4vw,42px);background:#173a2e;color:#fff;border-radius:22px;display:flex;justify-content:space-between;gap:24px;align-items:end;flex-wrap:wrap }}
h1 {{ margin:0;font-size:clamp(28px,4vw,48px);letter-spacing:-.045em;line-height:1.15 }}
h2 {{ margin:0;font-size:23px }}
.stats {{ display:flex;flex-wrap:wrap;gap:28px;margin:0 }}
.stats div {{ min-width:90px }}
.stats dt {{ color:#c4dece;font-size:13px }}
.stats dd {{ font-size:22px;font-weight:700;margin:2px 0 0;font-variant-numeric:tabular-nums }}
section {{ margin-top:28px;background:#fff;border:1px solid var(--line);border-radius:20px;overflow:hidden }}
.toolbar {{ padding:20px 24px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap }}
.controls {{ display:flex;gap:10px;flex-wrap:wrap }}
input,select {{ font:inherit;color:var(--ink);background:#f8faf7;border:1px solid #cbd8cd;border-radius:9px;padding:8px 12px;max-width:100% }}
:focus-visible {{ outline:2px solid #24865d;outline-offset:3px }}
.panel {{ overflow:auto }}
table {{ width:100%;border-collapse:collapse;min-width:800px }}
th,td {{ padding:15px 18px;text-align:left;border-top:1px solid var(--line);vertical-align:top }}
th {{ background:#eff4ed;color:#45594c;font-size:13px;white-space:nowrap }}
tbody tr:hover {{ background:#f8faf7 }}
.project {{ width:46%;overflow-wrap:anywhere }}
a {{ color:var(--accent);font-weight:750;text-decoration:none }}
a:hover {{ text-decoration:underline }}
small {{ display:block;margin-top:4px;color:var(--muted);font-size:13px }}
details {{ margin-top:7px;color:var(--muted);font-size:13px }}
summary {{ cursor:pointer;color:var(--accent);width:fit-content }}
details ul {{ margin:6px 0;padding-left:22px }}
.num {{ white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:650 }}
.language {{ display:inline-block;background:#eff4ed;padding:2px 8px;border-radius:6px;font-size:13px }}
.note,#empty {{ margin:14px 24px;color:var(--muted);font-size:13px }}
</style>
<main>
<header><h1>GitHub 选题工作台</h1>
<dl class="stats">
<div><dt>项目总数</dt><dd>{len(rows)}</dd></div>
<div><dt>最近一天观测</dt><dd>{observed}</dd></div>
<div><dt>最近观测日期</dt><dd>{date}</dd></div>
</dl></header>
<section aria-labelledby="projects">
<div class="toolbar"><h2 id="projects">项目库</h2>
<div class="controls">
<input type="search" id="search" aria-label="搜索项目" placeholder="搜索仓库、简介或语言">
<select id="sort" aria-label="排序方式">
<option value="date">最近观测</option>
<option value="stars">Star 总数</option>
<option value="growth">较昨日增长率</option>
<option value="week">近 7 天净增</option>
</select></div></div>
<div class="panel"><table><thead><tr><th>项目</th><th>语言</th>
<th>Star 总数</th><th>最近观测</th><th>较昨日净增</th><th>近 7 天净增</th></tr></thead>
<tbody>{''.join(cards)}</tbody></table></div>
<p id="empty" role="status" hidden>没有匹配的项目。</p>
<p class="note">增长以项目最近观测日为基准。缺少对应日期的快照时显示「—」。</p>
</section></main>
<script>
const sort = document.querySelector('#sort');
const table = document.querySelector('tbody');
const search = document.querySelector('#search');
const empty = document.querySelector('#empty');
search.addEventListener('input', () => {{
  const query = search.value.trim().toLowerCase();
  let matches = 0;
  for (const row of table.rows) {{
    const text = [row.querySelector('.project a'), row.querySelector('small'),
                  row.querySelector('.language')].map(node => node.textContent).join(' ');
    row.hidden = !text.toLowerCase().includes(query);
    if (!row.hidden) matches++;
  }}
  empty.hidden = matches > 0;
}});
sort.addEventListener('change', () => {{
  const key = sort.value;
  const rows = Array.from(table.rows);
  const score = row => row.dataset[key] === '' ? -Infinity : Number(row.dataset[key]);
  rows.sort((a, b) => key === 'date' ? b.dataset.date.localeCompare(a.dataset.date) :
    (score(b) - score(a)) || b.dataset.date.localeCompare(a.dataset.date));
  table.append(...rows);
}});
</script></html>
""", encoding="utf-8")


if __name__ == "__main__":
    write_report(ROOT / "data/trending.sqlite3", ROOT / "trending.html")
