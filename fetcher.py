import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

BASE_URL = "https://www.wuylh.com/replayrobot/json"
DATA_DIR = "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.wuylh.com/replayrobot/index.html",
}


def _map_stock(raw: dict) -> dict:
    """将 API 原始股票字段映射到统一格式。"""
    try:
        continuous_days = int(raw.get("lb_count", 0) or 0)
    except (ValueError, TypeError):
        continuous_days = 0
    return {
        "name": raw.get("name", ""),
        "code": raw.get("code", ""),
        "continuous_days": continuous_days,
        "reason": raw.get("type", ""),
        "price": float(raw.get("price", 0) or 0),
        "change_pct": float(raw.get("precent", 0) or 0),
        "amount": float(raw.get("amount", 0) or 0),
        "turnover_rate": float(raw.get("tor", 0) or 0),
    }


def _parse_ten_days(ten_days: list) -> list[dict]:
    """
    从 tenDays 数组解析近10日趋势摘要。
    tenDays[0]=日期, [3]=总涨停, [19]=开板数, [20]=封板率%
    """
    if not ten_days or len(ten_days) < 21:
        return []
    dates = ten_days[0]
    zt_all_list = ten_days[3]
    broken_list = ten_days[19]
    seal_list = ten_days[20]
    n = min(len(dates), len(zt_all_list), len(broken_list), len(seal_list))
    result = []
    for i in range(n):
        parts = str(dates[i]).split("-")
        normalized = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        result.append({
            "date": normalized,
            "zt_all": int(zt_all_list[i] or 0),
            "limit_broken_count": int(broken_list[i] or 0),
            "seal_rate": float(seal_list[i] or 0),
        })
    return result


def parse_daily_data(json_data: dict, date_str: str) -> dict:
    """
    解析 wuylh JSON 响应，返回标准化的每日复盘数据。
    json_data: API 原始 JSON（已解析为 dict）
    """
    lbg_stocks = json_data.get("lbg", {}).get("datas", [])
    qt_stocks = json_data.get("qt", {}).get("datas", [])
    gg_stocks = json_data.get("gg", {}).get("datas", [])
    ztkb_stocks = json_data.get("ztkb", {}).get("datas", [])

    limit_up = [_map_stock(s) for s in lbg_stocks + qt_stocks + gg_stocks]
    limit_broken = [_map_stock(s) for s in ztkb_stocks]

    today = json_data.get("today", {})
    summary = {
        "zt_all": int(today.get("ztAll", 0) or 0),
        "seal_rate": float(today.get("fbl", 0) or 0),
    }

    history_10d = _parse_ten_days(json_data.get("tenDays", []))

    return {
        "date": date_str,
        "limit_up": limit_up,
        "limit_broken": limit_broken,
        "summary": summary,
        "history_10d": history_10d,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch_today_data(date_str: str | None = None) -> dict:
    """爬取指定日期的复盘数据。默认为今日。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    url = f"{BASE_URL}/{date_str}p.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        json_data = resp.json()
    except requests.RequestException as e:
        raise ConnectionError(f"爬取失败 {url}: {e}") from e

    time.sleep(1)
    return parse_daily_data(json_data, date_str=date_str)


def load_or_fetch(
    date_str: str | None = None,
    data_dir: str = DATA_DIR,
    fetch_fn=None,
) -> tuple[dict, str | None]:
    """
    加载当日数据文件，若不存在则调用 fetch_fn 爬取。
    返回 (data, warning_message)
    warning_message: 若使用了历史数据，返回提示文字；否则 None
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    if fetch_fn is None:
        fetch_fn = fetch_today_data

    data_path = Path(data_dir) / f"{date_str}.json"

    # 存在当日文件，直接加载
    if data_path.exists():
        data = json.loads(data_path.read_text(encoding="utf-8"))
        return data, None

    # 尝试爬取
    try:
        data = fetch_fn(date_str=date_str)
    except ConnectionError:
        data = {"date": date_str, "limit_up": [], "limit_broken": [], "summary": {}}

    # 有数据则保存
    if data.get("limit_up"):
        data_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return data, None

    # 爬取为空（休市/非交易日），优先回退到最近有数据的本地文件
    existing = sorted(Path(data_dir).glob("*.json"), reverse=True)
    if existing:
        fallback_data = json.loads(existing[0].read_text(encoding="utf-8"))
        fallback_date = existing[0].stem
        warning = f"今日休市或数据为空，显示 {fallback_date} 的数据"
        return fallback_data, warning

    # 本地无任何缓存（首次运行），向前探测最近 10 个自然日，找到最近有数据的交易日
    base_date = datetime.strptime(date_str, "%Y-%m-%d")
    for days_back in range(1, 11):
        candidate = (base_date - timedelta(days=days_back)).strftime("%Y-%m-%d")
        try:
            fallback = fetch_fn(date_str=candidate)
        except ConnectionError:
            continue
        if fallback.get("limit_up"):
            candidate_path = Path(data_dir) / f"{candidate}.json"
            candidate_path.write_text(
                json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            warning = f"今日休市或数据为空，显示 {candidate} 的数据"
            return fallback, warning

    return {"date": date_str, "limit_up": [], "limit_broken": [], "summary": {}}, "暂无历史数据"
