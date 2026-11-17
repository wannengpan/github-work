# GitHub 热门项目工作台

用 Python 3.10+ 采集 GitHub Trending 全语言日榜、周榜和月榜，合并去重后保存北京时间当天的 SQLite 快照。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python collect.py
```

默认数据库为 `data/trending.sqlite3`，可通过 `--db` 指定其他位置。同一天重复采集会更新再次观测到的项目，并保留当天已入库的其他项目。每天在相近时间运行，便于跨日比较。

## 查询绘图数据

```sql
SELECT snapshot_date, rank, stars, trending_stars_today,
       star_delta, growth_percent
FROM daily_star_growth
WHERE repository = 'owner/repo'
ORDER BY snapshot_date;
```

- `stars` 是采集时的 Star 总数，`trending_stars_today` 是日榜标注的当日 Star 数，仅出现在周榜或月榜时记为 -1。
- `star_delta` 取今天总数减去昨天总数，`growth_percent` 以昨天总数为基准计算百分比。
- 昨天未上榜或没有采集记录时，跨日指标为 NULL。昨天总数为零时，增长率为 NULL。本版本只观测上榜仓库，绘图时可保留缺失日期的断点。

## 打开 HTML 报表

采集成功后会生成或更新工作台目录的 `trending.html`。在 Finder 双击该文件即可查看最新榜单，也可以用 `python3 report.py` 从已有默认数据库重新生成。使用自定义数据库路径时，采集脚本将报表保存到该数据库旁边。

## 开启每天自动采集

1. 在 GitHub 创建一个空的私有仓库，并在本目录运行以下命令。把远程地址换成自己的仓库地址。

   ```bash
   git init -b main
   git add .gitignore .github README.md collect.py report.py descriptions.zh.json requirements.txt data/trending.sqlite3 trending.html
   git commit -m "Add GitHub Trending workbench"
   git remote add origin https://github.com/你的用户名/你的仓库.git
   git push -u origin main
   ```

2. 打开仓库的 **Actions → Collect GitHub Trending → Run workflow**，手动试跑一次。运行完成后，确认日志显示采集成功，仓库里有更新后的 SQLite 文件和报表。如果推送报权限错误，检查仓库或组织是否允许工作流写入默认分支。
3. 此后工作流每天北京时间 07:15 计划启动，并把数据库和报表提交回仓库。工作流使用 GitHub 自动提供的 `GITHUB_TOKEN` 保存结果，采集公开榜单无需配置 API 密钥或外部数据库。
4. 每次想看最新报表时，在本地运行 `git pull --ff-only`，再打开 `trending.html`。启用云端采集后，本地直接运行采集脚本会改动同样的文件，可能导致后续拉取冲突。

历史项目始终保留在报表中，按最近观测、Star 总数、较昨日增长率或近 7 天净增排序。展开「星数历史」可查看每次入榜日期的星数。当天三个榜单均无该项目时不会新增快照。增长按各项目最近观测日计算，缺少对应历史快照时显示「—」。

## 中文简介

报表生成器从 `descriptions.zh.json` 读取译文，按原始简介匹配。新项目或简介变更时先显示原文。更新词条后运行 `python3 report.py` 即可重新生成报表。数据库保留原始简介。
