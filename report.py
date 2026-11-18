import json
import sqlite3
from contextlib import closing
from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent


LANGUAGE_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Rust": "#dea584", "Go": "#00ADD8", "Java": "#b07219", "C": "#555555",
    "C++": "#f34b7d", "C#": "#178600", "HTML": "#e34c26", "CSS": "#663399",
    "Shell": "#89e051", "Ruby": "#701516", "PHP": "#4F5D95", "Swift": "#F05138",
    "Kotlin": "#A97BFF", "Vue": "#41b883", "Svelte": "#ff3e00",
}

ICONS = {
    "light": "M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
    "dark": "M20 15a8.5 8.5 0 0 1-11-11A8.5 8.5 0 1 0 20 15Z",
    "system": "M3 4h18v12H3zM12 16v4m-4 0h8",

    "inbox": "M4 4h16l2 10v6H2v-6L4 4Z M2 14h6l2 3h4l2-3h6",
    "watch": "M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12Z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
    "ignore": "M6 6l12 12m0-12L6 18",
    "growth": "M3 19h18M5 15l5-5 4 3 6-8m-5 0h5v5",
    "topic": "M6 4h12v16l-6-4-6 4V4Z",
}


def icon(name):
    return (f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" '
            f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true"><path d="{ICONS[name]}"/></svg>')


def sparkline(snapshots):
    ordered = snapshots[::-1]
    low = min(stars for _, stars in ordered)
    high = max(stars for _, stars in ordered)
    points = []
    for index, (_, stars) in enumerate(ordered):
        x = 4 + 72 * index / max(len(ordered) - 1, 1)
        y = 12 if high == low else 20 - 16 * (stars - low) / (high - low)
        points.append(f"{x:.1f},{y:.1f}")
    label = escape("；".join(f"{date}：{stars:,}" for date, stars in ordered), quote=True)
    if len(points) == 1:
        mark = '<circle cx="40" cy="12" r="2.5" fill="currentColor"/>'
    else:
        mark = f'<polyline points="{" ".join(points)}" fill="none" stroke="currentColor" stroke-width="1.8"/>'
    return f'<svg class="spark" viewBox="0 0 80 24" role="img" aria-label="{label}"><title>{label}</title>{mark}</svg>'


def badge(delta):
    if delta is None:
        return '<span class="delta neutral">暂无</span>'
    tone = "positive" if delta > 0 else "negative" if delta < 0 else "neutral"
    return f'<span class="delta {tone}">{delta:+,}</span>'


def write_report(db_path, output):
    translations_path = ROOT / "descriptions.zh.json"
    translations = json.loads(translations_path.read_text(encoding="utf-8"))
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("""
            SELECT current.*, current.stars - week.stars AS week_delta,
                   current.stars - month.stars AS month_delta,
                   100.0 * (current.stars - week.stars) / NULLIF(week.stars, 0) AS week_growth
            FROM daily_star_growth AS current
            LEFT JOIN trending_snapshots AS week
              ON week.repository = current.repository
              AND week.snapshot_date = date(current.snapshot_date, '-7 days')
            LEFT JOIN trending_snapshots AS month
              ON month.repository = current.repository
              AND month.snapshot_date = date(current.snapshot_date, '-30 days')
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
                (snapshot["snapshot_date"], snapshot["stars"])
            )
    date = rows[0]["snapshot_date"] if rows else "暂无数据"
    languages = sorted({row["language"] for row in rows if row["language"]}, key=str.casefold)
    options = "".join(f'<option>{escape(language)}</option>' for language in languages)
    cards = []
    for row in rows:
        original = row["description"] or ""
        description = translations.get(original, original)
        name = escape(row["repository"])
        url = quote(row["repository"], safe="/")
        trend = sparkline(history[row["repository"].casefold()])
        language = row["language"] or "—"
        color = LANGUAGE_COLORS.get(language, "#8b949e")
        delta = row["star_delta"]
        percent = row["growth_percent"]
        week = row["week_delta"]
        cards.append(f"""
<tr data-repo="{escape(row['repository'].casefold(), quote=True)}"
 data-day="{delta if delta is not None else ''}"
 data-month="{row['month_delta'] if row['month_delta'] is not None else ''}"
 data-rate="{row['week_growth'] if row['week_growth'] is not None else ''}"
 data-stars="{row['stars']}" data-date="{escape(row['snapshot_date'])}" data-week="{week if week is not None else ''}"
 data-growth="{percent if percent is not None else ''}"><td class="row-number"></td><td class="project"><a href="https://github.com/{url}">{name}</a>
<small title="{escape(description, quote=True)}">{escape(description)}</small></td>
<td><span class="language"><i style="--language:{color}"></i>{escape(language)}</span></td>
<td class="num"><span class="stars">{row['stars']:,}{trend}</span></td>
<td class="num">{badge(delta)}</td><td class="num">{badge(week)}</td>
<td><div class="actions"><button type="button" class="save primary" data-action="topic">加入选题库</button>
<button type="button" class="save icon" data-action="watch" title="保留观察" aria-label="保留观察">{icon('watch')}</button>
<button type="button" class="save icon" data-action="ignore" title="停止跟踪" aria-label="停止跟踪">{icon('ignore')}</button></div></td></tr>""")
    output.write_text(f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub 热门项目工作台</title>
<style>
* {{ box-sizing:border-box }}
:root {{ color-scheme:light; --ink:#182922; --muted:#52655a; --line:#dce5de; --accent:#176644 }}
body {{ margin:0;background:#fff;color:var(--ink);font:15px/1.55 "Instrument Sans",system-ui,sans-serif }}
body {{ display:grid;grid-template-columns:220px minmax(0,1fr);min-height:100vh }}
aside {{ background:#f7f9f7;border-right:1px solid var(--line);padding:24px 16px }}
aside strong {{ display:block;padding:0 10px;margin-bottom:24px }}
nav {{ display:grid;gap:8px }}
nav button,.save {{ font:inherit;cursor:pointer;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--accent);padding:7px 10px;white-space:nowrap }}
nav button {{ display:flex;align-items:center;gap:8px;text-align:left;border:0;border-left:3px solid transparent;background:transparent;color:var(--ink);padding:8px 16px }}
nav button[aria-current="page"] {{ background:#e5f0e8;border-left-color:var(--accent);color:var(--accent);font-weight:700 }}
main {{ width:100%;max-width:1440px;margin:0 auto;padding:clamp(16px,3vw,40px) }}
@media(max-width:700px) {{
  body {{ display:block }}
  aside {{ padding:12px 16px;border-bottom:1px solid var(--line) }}
  aside strong {{ margin-bottom:8px }}
  nav {{ display:flex;flex-wrap:wrap }}
}}
header {{ padding:0 0 16px;border-bottom:1px solid var(--line) }}
h1 {{ margin:0;font-size:28px;letter-spacing:-.035em;line-height:1.2 }}
.page-meta {{ margin:8px 0 0;color:var(--muted);font-size:13px }}
section {{ margin-top:16px }}
.toolbar {{ margin-bottom:16px }}
.controls {{ display:flex;justify-content:flex-start;gap:8px;flex-wrap:wrap }}
#search {{ width:min(100%,320px) }}
input,select {{ font:inherit;color:var(--ink);background:#f8faf7;border:1px solid #cbd8cd;border-radius:9px;padding:8px 16px;max-width:100% }}
:focus-visible {{ outline:2px solid #24865d;outline-offset:3px }}
.panel {{ overflow:auto;border-top:1px solid var(--line);border-bottom:1px solid var(--line) }}
table {{ width:100%;border-collapse:collapse;min-width:800px }}
th,td {{ padding:16px;text-align:left;border-top:1px solid var(--line);vertical-align:middle }}
th {{ background:#f5f7f5;color:#45594c;font-size:13px;white-space:nowrap }}
tbody tr:hover {{ background:#f8faf7 }}
.actions {{ display:flex;align-items:center;gap:8px;white-space:nowrap }}
.primary {{ background:var(--accent);color:white;border-color:var(--accent);padding:8px }}
.icon {{ width:32px;height:32px;padding:0;place-items:center;display:inline-grid }}
[hidden] {{ display:none !important }}
.stars {{ display:inline-flex;align-items:center;gap:8px }}
.spark {{ width:80px;height:24px;color:var(--accent);flex:none }}
.delta {{ display:inline-block;border-radius:8px;padding:0 8px }}
.positive {{ color:#14613d;background:#e4f4eb }}
.negative {{ color:#9e3434;background:#fceaea }}
.neutral {{ color:#64716b;background:#f1f3f2 }}
.metrics {{ display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:16px 0 }}
.metrics div {{ min-width:0;border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:0 2px 8px #18292208 }}
.metrics dt {{ font-size:13px;color:var(--muted) }}
.metrics dd {{ margin:8px 0 0;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap }}
@media(max-width:700px) {{ .metrics {{ grid-template-columns:repeat(2,minmax(0,1fr)) }} }}

.project {{ width:34%;max-width:0 }}
a {{ color:var(--accent);font-weight:750;text-decoration:none }}
a:hover {{ text-decoration:underline }}
small {{ display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;height:40px;line-height:20px;color:var(--muted);font-size:13px }}
.project a {{ display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap }}
.num,th:nth-child(4),th:nth-child(5),th:nth-child(6) {{ text-align:right }}
.num {{ white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:650 }}
.stopped .project a::after {{ content:' · 已停止跟踪';font-size:12px;color:var(--muted) }}
.language {{ display:inline-flex;align-items:center;gap:8px;white-space:nowrap;font-size:13px }}
.language i {{ width:8px;height:8px;border-radius:50%;background:var(--language) }}
.note,#empty {{ margin:14px 0;color:var(--muted);font-size:13px }}
aside {{ position:sticky;top:0;height:100vh;overflow:auto;display:flex;flex-direction:column }}
.theme-control {{ display:flex;width:fit-content;gap:4px;margin-top:auto;border:1px solid var(--line);border-radius:12px;padding:4px;background:#fff }}
.theme-control button {{ display:grid;place-items:center;width:32px;height:32px;border:0;border-radius:8px;background:transparent;color:var(--muted);cursor:pointer }}
.theme-control button:hover,.theme-control button[aria-pressed="true"] {{ background:#e9eeea;color:var(--ink) }}
header,.header-tools {{ display:flex;align-items:center;gap:16px;flex-wrap:wrap }}
header {{ justify-content:space-between }}
.header-tools,.row-number {{ color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums }}
.row-number {{ width:1%;white-space:nowrap }}
@media(max-width:700px) {{
  aside {{ height:auto;z-index:2 }}
  .theme-control {{ margin-top:8px }}
}}
:root[data-theme="dark"] {{
  color-scheme:dark;--ink:#ededed;--muted:#aeaeae;--line:#383838;--accent:#82d4a8;
}}
[data-theme="dark"] body,[data-theme="dark"] .metrics div {{ background:#121212 }}
[data-theme="dark"] aside,[data-theme="dark"] th,[data-theme="dark"] input,
[data-theme="dark"] select,[data-theme="dark"] .theme-control,[data-theme="dark"] .save {{ background:#1c1c1c;color:var(--ink);border-color:var(--line) }}
[data-theme="dark"] .theme-control button:hover,[data-theme="dark"] .theme-control button[aria-pressed="true"],[data-theme="dark"] nav button[aria-current="page"],[data-theme="dark"] tbody tr:hover {{ background:#292929 }}
[data-theme="dark"] .primary {{ background:var(--accent);color:#14241b }}
[data-theme="dark"] .positive {{ background:#244b36;color:#a0e3ba }}
[data-theme="dark"] .negative {{ background:#502c2c;color:#ffc2c2 }}
[data-theme="dark"] .neutral {{ background:#303030;color:#cccccc }}
</style>
<aside><strong>GitHub 选题工作台</strong><nav aria-label="工作台导航">
<button type="button" data-view="all" aria-current="page">{icon("inbox")}待审核项目</button>
<button type="button" data-view="tracked">{icon("watch")}持续跟踪</button>
<button type="button" data-view="ignored">{icon("ignore")}已忽略</button>
<button type="button" data-view="growth">{icon("growth")}增长榜</button>
<button type="button" data-view="saved">{icon("topic")}我的选题库</button>
</nav>
<div class="theme-control" role="group" aria-label="显示主题">
<button type="button" data-mode="dark" aria-label="深色" title="深色" aria-pressed="false">{icon("dark")}</button>
<button type="button" data-mode="system" aria-label="跟随系统" title="跟随系统" aria-pressed="true">{icon("system")}</button>
<button type="button" data-mode="light" aria-label="浅色" title="浅色" aria-pressed="false">{icon("light")}</button>
</div></aside>
<main>
<header><div><h1 id="projects">待审核项目</h1>
<p class="page-meta"><span id="count">{len(rows)} 个项目</span></p></div>
<div class="header-tools"><span>最近观测 <time>{date}</time></span><button type="button" class="save" id="refresh">同步最新数据</button></div>
</header>
<dl class="metrics">
<div><dt>待审核项目数</dt><dd id="pending-total">0</dd></div>
<div><dt>今日新增 Star 最多</dt><dd id="daily-leader">暂无</dd></div>
<div><dt>本周增长最快</dt><dd id="weekly-leader">暂无</dd></div>
<div><dt>已加入选题库数</dt><dd id="topic-total">0</dd></div>
</dl>
<section aria-labelledby="projects">
<div class="toolbar"><div class="controls">
<input type="search" id="search" aria-label="搜索项目" placeholder="搜索仓库、简介或语言">
<select id="language" aria-label="筛选语言"><option value="">全部语言</option>{options}</select>
<select id="sort" aria-label="排序方式">
<option value="date">最近观测</option>
<option value="stars">Star 总数</option>
<option value="day">近 1 天净增</option>
<option value="month">近 30 天净增</option>
<option value="rate">近 7 天增长率</option>
<option value="growth">较昨日增长率</option>
<option value="week">近 7 天净增</option>
</select></div></div>
<div class="panel"><table><thead><tr><th scope="col">序号</th><th>项目</th><th>语言</th>
<th>Star 总数</th><th>较昨日净增</th><th>近 7 天净增</th><th>选题</th></tr></thead>
<tbody>{''.join(cards)}</tbody></table></div>
<div class="note"><button type="button" class="save" id="export" hidden>导出忽略名单</button></div>
<p class="note" id="status" role="status"></p>
<p id="empty" role="status" hidden>没有匹配的项目。</p>
<p class="note">增长以项目最近观测日为基准。缺少对应日期的快照时显示「暂无」。</p>
</section></main>
<script>
const themeButtons = document.querySelectorAll('.theme-control button');
const systemTheme = matchMedia('(prefers-color-scheme: dark)');
let themeMode = 'system';
try {{
  const preference = localStorage.getItem('github-workbench-theme');
  if (['system', 'light', 'dark'].includes(preference)) themeMode = preference;
}} catch {{}}
function applyTheme() {{
  document.documentElement.dataset.theme = themeMode === 'system'
    ? (systemTheme.matches ? 'dark' : 'light') : themeMode;
  for (const button of themeButtons) {{
    button.setAttribute('aria-pressed', String(button.dataset.mode === themeMode));
  }}
}}
for (const button of themeButtons) {{
  button.addEventListener('click', () => {{
    themeMode = button.dataset.mode;
    applyTheme();
    try {{ localStorage.setItem('github-workbench-theme', themeMode); }} catch {{}}
  }});
}}
systemTheme.addEventListener('change', applyTheme);
applyTheme();
document.querySelector('#refresh').addEventListener('click', () => location.reload());

const sort = document.querySelector('#sort');
const languageFilter = document.querySelector('#language');
const table = document.querySelector('tbody');
const search = document.querySelector('#search');
const empty = document.querySelector('#empty');
const storageKey = 'github-workbench-editorial-v1';
const nav = document.querySelector('nav');
const title = document.querySelector('#projects');
const status = document.querySelector('#status');
let saved = new Set();
let view = 'all';
let watched = new Set();
let ignored = new Set();
try {{
  const state = JSON.parse(localStorage.getItem(storageKey) || '[]');
  saved = new Set(Array.isArray(state) ? state : state.saved);
  watched = new Set(state.watched || []);
  ignored = new Set(state.ignored || []);
}} catch {{
  status.textContent = '无法读取本机选题记录。';
}}

function render() {{
  const key = sort.value;
  const query = search.value.trim().toLowerCase();
  const rows = Array.from(table.rows);
  const score = row => row.dataset[key] === '' ? -Infinity : Number(row.dataset[key]);
  rows.sort((a, b) => key === 'date' ? b.dataset.date.localeCompare(a.dataset.date) :
    (score(b) - score(a)) || b.dataset.date.localeCompare(a.dataset.date));
  let matches = 0;
  let pending = 0;
  const leaders = {{day: null, week: null}};
  for (const row of rows) {{
    const selected = saved.has(row.dataset.repo);
    const stopped = ignored.has(row.dataset.repo);
    const button = row.querySelector('[data-action="topic"]');
    const watch = row.querySelector('[data-action="watch"]');
    const ignore = row.querySelector('[data-action="ignore"]');
    watch.hidden = view !== 'all';
    ignore.title = stopped ? '恢复跟踪' : '停止跟踪';
    ignore.setAttribute('aria-label', ignore.title);
    if (!selected && !watched.has(row.dataset.repo) && !stopped) pending++;
    if (!stopped && row.dataset.date === '{date}') {{
      for (const metric of ['day', 'week']) {{
        const value = Number(row.dataset[metric]);
        if (value > 0 && (!leaders[metric] || value > leaders[metric].value)) {{
          leaders[metric] = {{value, name: row.querySelector('.project a').textContent}};
        }}
      }}
    }}
    row.classList.toggle('stopped', stopped);
    button.textContent = selected ? '移出选题库' : '加入选题库';
    const text = [row.querySelector('.project a'), row.querySelector('small'),
                  row.querySelector('.language')].map(node => node.textContent).join(' ');
    row.hidden = (view === 'all' && (selected || watched.has(row.dataset.repo) || stopped)) ||
      (view === 'ignored' && !stopped) ||
      (['tracked', 'growth'].includes(view) && stopped) ||
      (view === 'saved' && !selected) ||
      (view === 'growth' && (row.dataset.date !== '{date}' || row.dataset[key] === '')) ||
      (languageFilter.value !== '' && row.querySelector('.language').textContent !== languageFilter.value) ||
      !text.toLowerCase().includes(query);
    row.querySelector(".row-number").textContent = row.hidden ? "" : ++matches;
  }}
  table.append(...rows);
  document.querySelector('#pending-total').textContent = pending;
  document.querySelector('#topic-total').textContent = saved.size;
  for (const [id, leader] of [['daily-leader', leaders.day], ['weekly-leader', leaders.week]]) {{
    const tile = document.getElementById(id);
    tile.textContent = leader ? `${{leader.name}} +${{leader.value.toLocaleString()}}` : '暂无';
    tile.title = tile.textContent;
  }}
  document.querySelector("#count").textContent = matches + " 个项目";
  empty.hidden = matches > 0;
  empty.textContent = view === 'saved' && !query ? '还没有选题。可在全部项目中加入。' : '没有匹配的项目。';
  if (view === 'all' && !query) empty.textContent = '暂无待审核项目。';
  document.querySelector('#export').hidden = view !== 'ignored';
}}

nav.addEventListener('click', event => {{
  const button = event.target.closest('[data-view]');
  if (!button) return;
  view = button.dataset.view;
  title.textContent = button.textContent;
  search.value = '';
  languageFilter.value = '';
  sort.value = view === 'growth' ? 'week' : 'date';
  for (const item of nav.querySelectorAll('button')) item.removeAttribute('aria-current');
  button.setAttribute('aria-current', 'page');
  render();
}});

table.addEventListener('click', event => {{
  const button = event.target.closest('.save');
  if (!button) return;
  const repo = button.closest('tr').dataset.repo;
  const next = {{ saved: new Set(saved), watched: new Set(watched), ignored: new Set(ignored) }};
  const action = button.dataset.action;
  if (action === 'topic') {{
    if (next.saved.has(repo)) {{ next.saved.delete(repo); next.watched.add(repo); }}
    else next.saved.add(repo);
  }} else if (action === 'watch') next.watched.add(repo);
  else if (next.ignored.has(repo)) {{ next.ignored.delete(repo); next.watched.add(repo); }}
  else next.ignored.add(repo);
  try {{
    localStorage.setItem(storageKey, JSON.stringify({{
      saved: [...next.saved], watched: [...next.watched], ignored: [...next.ignored]
    }}));
    ({{ saved, watched, ignored }} = next);
    status.textContent = action === 'ignore' ?
      (ignored.has(repo) ? '已在本机停止跟踪。请同步忽略名单到采集任务。' : '已在本机恢复跟踪。请同步忽略名单到采集任务。') :
      '选题状态已保存。';
    render();
  }} catch {{
    status.textContent = '浏览器无法保存选题。';
  }}
}});
document.querySelector('#export').addEventListener('click', () => {{
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([JSON.stringify([...ignored])], {{type:'application/json'}}));
  link.download = 'ignored-repositories.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}});
search.addEventListener('input', render);
languageFilter.addEventListener('change', render);
sort.addEventListener('change', render);
render();
</script></html>
""", encoding="utf-8")


if __name__ == "__main__":
    write_report(ROOT / "data/trending.sqlite3", ROOT / "trending.html")
