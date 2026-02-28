import json
from pathlib import Path
from collections import Counter


def get_summary_stats(data: dict) -> dict:
    """计算今日概览统计数据。"""
    limit_up = data.get("limit_up", [])
    limit_broken = data.get("limit_broken", [])
    summary = data.get("summary", {})

    # 优先使用 API 提供的全量统计
    zt_all = int(summary.get("zt_all", 0) or 0)
    seal_rate = float(summary.get("seal_rate", 0) or 0)

    # 炸板率：用本地连板+炸板计算（API 只给高亮股票）
    local_total = len(limit_up) + len(limit_broken)
    bust_rate = round(len(limit_broken) / local_total * 100, 2) if local_total > 0 else 0.0

    max_stock = max(limit_up, key=lambda s: s["continuous_days"], default=None)
    topic_counts = get_topic_counts(limit_up)
    top_topic = topic_counts[0]["topic"] if topic_counts else "—"

    return {
        "limit_up_count": len(limit_up),
        "limit_broken_count": len(limit_broken),
        "zt_all": zt_all,
        "seal_rate": seal_rate,
        "bust_rate": bust_rate,
        "max_continuous": max_stock["continuous_days"] if max_stock else 0,
        "max_continuous_name": max_stock["name"] if max_stock else "—",
        "top_topic": top_topic,
    }


def get_topic_counts(stocks: list[dict]) -> list[dict]:
    """统计涨停股题材出现次数，按频次降序返回。"""
    counter: Counter = Counter()
    topic_stocks: dict[str, list[str]] = {}

    for stock in stocks:
        raw_reason = stock.get("reason", "") or ""
        # 涨停原因可能包含多个题材（以分号、逗号或顿号分隔）
        parts = [
            r.strip()
            for r in raw_reason.replace("；", ";").replace("、", ";").replace(",", ";").split(";")
            if r.strip()
        ]
        reasons = parts if parts else ([raw_reason] if raw_reason else [])

        for reason in reasons:
            counter[reason] += 1
            topic_stocks.setdefault(reason, []).append(stock["name"])

    return [
        {"topic": topic, "count": count, "stocks": topic_stocks[topic]}
        for topic, count in counter.most_common()
    ]


def get_continuous_ladder(stocks: list[dict]) -> list[dict]:
    """
    按连板数分组统计，返回连板梯队数据。
    每组包含连板数、股票数量、成交额最大的代表股名。
    """
    groups: dict[int, list[dict]] = {}
    for stock in stocks:
        days = stock["continuous_days"]
        groups.setdefault(days, []).append(stock)

    result = []
    for days in sorted(groups.keys()):
        group = groups[days]
        top_stock = max(group, key=lambda s: s.get("amount", 0))
        result.append({
            "days": days,
            "count": len(group),
            "top_stock": top_stock["name"],
            "stocks": [s["name"] for s in group],
        })
    return result


def load_history(data_dir: str = "data", limit: int = 10) -> list[dict]:
    """
    加载最近 N 个交易日的数据，用于趋势图。
    返回按日期升序排列的数据列表。
    """
    files = sorted(Path(data_dir).glob("*.json"))[-limit:]
    history = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            stats = get_summary_stats(data)
            history.append({
                "date": data.get("date", f.stem),
                **stats,
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return history
