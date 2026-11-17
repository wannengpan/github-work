import argparse
import re
import sqlite3
import ssl
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import certifi
from bs4 import BeautifulSoup

from report import write_report

URL = "https://github.com/trending?since={}"
DEFAULT_DB = Path(__file__).resolve().parent / "data" / "trending.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trending_snapshots (
    snapshot_date TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    repository TEXT NOT NULL COLLATE NOCASE,
    rank INTEGER NOT NULL,
    description TEXT,
    language TEXT,
    stars INTEGER NOT NULL,
    trending_stars_today INTEGER NOT NULL,
    PRIMARY KEY (snapshot_date, repository),
    UNIQUE (snapshot_date, rank)
);
CREATE VIEW IF NOT EXISTS daily_star_growth AS
SELECT current.*,
       current.stars - previous.stars AS star_delta,
       100.0 * (current.stars - previous.stars)
           / NULLIF(previous.stars, 0) AS growth_percent
FROM trending_snapshots AS current
LEFT JOIN trending_snapshots AS previous
    ON previous.repository = current.repository
    AND previous.snapshot_date = date(current.snapshot_date, '-1 day');
"""


def parse_trending(html, period="daily"):
    window = {"daily": "today", "weekly": "this week", "monthly": "this month"}[period]
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for rank, card in enumerate(soup.select("article.Box-row"), start=1):
        heading = card.select_one("h2 a[href]")
        repository = heading["href"].strip("/") if heading else ""
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
            raise ValueError(f"第 {rank} 名缺少有效仓库路径")
        stars = card.select_one(f'a[href="/{repository}/stargazers"]')
        total = stars.get_text(strip=True).replace(",", "") if stars else ""
        daily = re.search(rf"([\d,]+)\s+stars?\s+{window}\b", card.get_text(" ", strip=True))
        if not total.isdecimal() or (period == "daily" and daily is None):
            raise ValueError(f"{repository} 的 Star 字段解析失败")
        description = card.select_one("p")
        language = card.select_one('[itemprop="programmingLanguage"]')
        rows.append((
            repository, rank,
            description.get_text(" ", strip=True) if description else None,
            language.get_text(strip=True) if language else None,
            int(total), int(daily[1].replace(",", "")) if period == "daily" else -1,
        ))
    if not rows:
        raise ValueError("页面没有可解析的 Trending 项目")
    return rows


def save_snapshot(db_path, captured_at, rows):
    day = captured_at.date().isoformat()
    timestamp = captured_at.isoformat()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path, timeout=30)) as db:
        db.executescript(SCHEMA)
        with db:
            db.execute("BEGIN IMMEDIATE")
            latest = db.execute(
                "SELECT MAX(collected_at) FROM trending_snapshots WHERE snapshot_date = ?", (day,)
            ).fetchone()[0]
            if latest and latest >= timestamp:
                return False
            seen = {row[0].casefold() for row in rows}
            earlier = db.execute(
                """SELECT repository, rank, description, language, stars, trending_stars_today, collected_at
                   FROM trending_snapshots WHERE snapshot_date = ? ORDER BY rank""",
                (day,),
            )
            observations = [(row, timestamp) for row in rows]
            observations.extend((row[:-1], row[-1]) for row in earlier
                                if row[0].casefold() not in seen)
            db.execute("DELETE FROM trending_snapshots WHERE snapshot_date = ?", (day,))
            db.executemany(
                "INSERT INTO trending_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ((day, observed_at, row[0], rank, *row[2:])
                 for rank, (row, observed_at) in enumerate(observations, start=1)),
            )
    return True


def main():
    parser = argparse.ArgumentParser(description="采集 GitHub Trending 日、周、月榜")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 文件路径")
    args = parser.parse_args()
    try:
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=certifi.where())
        candidates = {}
        for period in ("daily", "weekly", "monthly"):
            request = Request(URL.format(period), headers={
                "User-Agent": "GitHub-Trending-Workbench/1.0",
                "Accept-Language": "en",
            })
            with urlopen(request, timeout=30, context=context) as response:
                for row in parse_trending(response.read(), period):
                    candidates.setdefault(row[0].casefold(), row)
        captured_at = datetime.now(ZoneInfo("Asia/Shanghai"))
        rows = [
            (row[0], rank, *row[2:])
            for rank, row in enumerate(candidates.values(), start=1)
        ]
        saved = save_snapshot(args.db, captured_at, rows)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"采集失败：{exc}\n")
    day = captured_at.date().isoformat()
    print(f"{day} 已保存 {len(rows)} 个项目至 {args.db}" if saved
          else f"{day} 已保留更新的快照")
    report_path = args.db.with_name("trending.html") if args.db != DEFAULT_DB else DEFAULT_DB.parent.parent / "trending.html"
    try:
        write_report(args.db, report_path)
    except (OSError, sqlite3.Error) as exc:
        parser.exit(1, f"数据已保存，HTML 更新失败：{exc}\n")
    print(f"HTML 报表：{report_path}")


if __name__ == "__main__":
    main()
