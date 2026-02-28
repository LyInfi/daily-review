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


def get_lb_stocks(stocks: list[dict]) -> list[dict]:
    """返回连板数 >= 2 的股票列表（过滤首板和0板）。"""
    return [s for s in stocks if s.get("continuous_days", 0) >= 2]


def get_continuous_ladder(stocks: list[dict]) -> list[dict]:
    """
    按连板数分组统计，返回连板梯队数据（仅含 >= 2 板）。
    每组包含连板数、股票数量、成交额最大的代表股名。
    """
    groups: dict[int, list[dict]] = {}
    for stock in stocks:
        days = stock["continuous_days"]
        if days < 2:
            continue
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


_EXTRA_10D_FIELDS = [
    "up_count", "down_count", "dt_count", "lb_count",
    "up10_count", "down9_count", "yizi_count", "zt_925",
    "rate_1to2", "rate_2to3", "rate_3to4", "lb_rate", "lb_rate_prev",
    "zt_amount", "total_amount", "sh_amount", "cyb_amount", "kcb_amount",
    "shouban", "er_lb", "san_lb", "si_lb", "wu_lb",
    "t_before10", "t_1000_1130", "t_1300_1400", "t_1400_1500",
]


def _history_entry_from_10d(entry: dict) -> dict:
    """将 history_10d 中的一条摘要转为 load_history 统一格式。"""
    zt_all = entry.get("zt_all", 0)
    broken = entry.get("limit_broken_count", 0)
    total = zt_all + broken
    bust_rate = round(broken / total * 100, 2) if total > 0 else 0.0
    result = {
        "date": entry["date"],
        "limit_up_count": zt_all,
        "limit_broken_count": broken,
        "zt_all": zt_all,
        "seal_rate": entry.get("seal_rate", 0.0),
        "bust_rate": bust_rate,
        "max_continuous": 0,
        "max_continuous_name": "—",
        "top_topic": "—",
    }
    for field in _EXTRA_10D_FIELDS:
        result[field] = entry.get(field, 0)
    return result


def load_history(data_dir: str = "data", limit: int = 10) -> list[dict]:
    """
    加载最近 N 个交易日的数据，用于趋势图。
    当本地文件不足时，从最新文件的 history_10d 字段补充历史数据。
    返回按日期升序排列的数据列表。
    """
    files = sorted(Path(data_dir).glob("*.json"))[-limit:]
    history: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            stats = get_summary_stats(data)
            file_date = data.get("date", f.stem)
            entry = {"date": file_date, **stats}
            # 从 history_10d 中补充 tenDays 衍生指标（仅取与本文件日期匹配的条目）
            for h in data.get("history_10d", []):
                if h.get("date") == file_date:
                    converted = _history_entry_from_10d(h)
                    for field in _EXTRA_10D_FIELDS:
                        entry[field] = converted.get(field, 0)
                    break
            history.append(entry)
        except (json.JSONDecodeError, KeyError):
            continue

    # 若本地文件不足，从最新文件的 history_10d 补充
    if len(history) < limit:
        all_files = sorted(Path(data_dir).glob("*.json"), reverse=True)
        existing_dates = {h["date"] for h in history}
        for f in all_files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                h10d = data.get("history_10d", [])
                if not h10d:
                    continue
                for entry in reversed(h10d):  # 从最新到最旧
                    if entry["date"] not in existing_dates and len(history) < limit:
                        history.append(_history_entry_from_10d(entry))
                        existing_dates.add(entry["date"])
                break  # 只用最新文件的 history_10d
            except (json.JSONDecodeError, KeyError):
                continue

    return sorted(history, key=lambda x: x["date"])
