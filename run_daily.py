#!/usr/bin/env python3
"""
外贸内参一键流程：抓取 URL → 拉正文并清洗为 Markdown → 合并并调用大模型生成日报。
供本地或 cron/launchd 无人值守执行。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# 保证以项目根为 cwd
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fetch_urls import run as run_fetch_urls
from src.fetch_and_clean import run as run_fetch_clean
from src.summarize import run as run_summarize


def main() -> None:
    date = datetime.now().strftime("%Y-%m-%d")
    print(f"=== 外贸内参 pipeline @ {date} ===")
    run_fetch_urls(date=date)
    run_fetch_clean(date=date)
    run_summarize(date=date)
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
