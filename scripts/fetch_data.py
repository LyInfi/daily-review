#!/usr/bin/env python3
"""
GitHub Actions 数据抓取脚本。
从 repo 根目录运行: python scripts/fetch_data.py [--date YYYY-MM-DD]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 将 repo 根目录加入 Python 路径，以便 import fetcher
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetcher import fetch_today_data  # noqa: E402

DATA_DIR = Path("data")
INDEX_FILE = DATA_DIR / "index.json"


def update_index(date_str: str) -> None:
    """将 date_str 插入 data/index.json 头部（若不存在则创建）。"""
    if INDEX_FILE.exists():
        dates = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    else:
        dates = []

    if date_str not in dates:
        dates.insert(0, date_str)
        INDEX_FILE.write_text(
            json.dumps(dates, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Updated index.json: added {date_str}")
    else:
        print(f"index.json already contains {date_str}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch daily stock data")
    parser.add_argument("--date", default=None, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    data_path = DATA_DIR / f"{date_str}.json"

    DATA_DIR.mkdir(exist_ok=True)

    # 幂等：文件已存在则跳过抓取，仍更新 index
    if data_path.exists():
        print(f"Data for {date_str} already exists, skipping fetch.")
        update_index(date_str)
        return

    print(f"Fetching data for {date_str} ...")
    try:
        data = fetch_today_data(date_str=date_str)
    except ConnectionError as e:
        print(f"ERROR: Fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not data.get("limit_up"):
        print(f"No data for {date_str} (non-trading day?), skipping.")
        sys.exit(0)

    data_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved {data_path}")
    update_index(date_str)


if __name__ == "__main__":
    main()
