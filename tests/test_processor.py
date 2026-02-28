import json
import pytest
from pathlib import Path
from processor import (
    get_summary_stats,
    get_topic_counts,
    get_continuous_ladder,
    load_history,
)

SAMPLE_DATA = {
    "date": "2026-02-28",
    "summary": {
        "zt_all": 48,
        "seal_rate": 75.0,
    },
    "limit_up": [
        {"name": "股A", "code": "000001", "continuous_days": 3, "reason": "人工智能", "amount": 5.2, "price": 10.0, "change_pct": 10.0, "turnover_rate": 12.0},
        {"name": "股B", "code": "000002", "continuous_days": 3, "reason": "人工智能", "amount": 3.1, "price": 8.0, "change_pct": 10.0, "turnover_rate": 8.0},
        {"name": "股C", "code": "000003", "continuous_days": 1, "reason": "新能源", "amount": 2.0, "price": 5.0, "change_pct": 10.0, "turnover_rate": 5.0},
        {"name": "股D", "code": "000004", "continuous_days": 6, "reason": "低空经济", "amount": 8.0, "price": 20.0, "change_pct": 10.0, "turnover_rate": 15.0},
    ],
    "limit_broken": [
        {"name": "股E", "code": "000005", "continuous_days": 0, "reason": "医药", "amount": 1.5, "price": 6.0, "change_pct": 5.0, "turnover_rate": 7.0},
        {"name": "股F", "code": "000006", "continuous_days": 0, "reason": "新能源", "amount": 1.0, "price": 4.0, "change_pct": 3.0, "turnover_rate": 4.0},
    ],
}


class TestGetSummaryStats:
    def test_counts_limit_up(self):
        stats = get_summary_stats(SAMPLE_DATA)
        assert stats["limit_up_count"] == 4

    def test_counts_limit_broken(self):
        stats = get_summary_stats(SAMPLE_DATA)
        assert stats["limit_broken_count"] == 2

    def test_uses_api_zt_all_when_available(self):
        stats = get_summary_stats(SAMPLE_DATA)
        # ztAll from API = 48, overrides local count
        assert stats["zt_all"] == 48

    def test_uses_api_seal_rate(self):
        stats = get_summary_stats(SAMPLE_DATA)
        assert stats["seal_rate"] == 75.0

    def test_calculates_bust_rate_from_local(self):
        data_no_summary = {**SAMPLE_DATA, "summary": {}}
        stats = get_summary_stats(data_no_summary)
        # 炸板率 = 开板 / (涨停 + 开板) = 2/6 ≈ 33.33%
        assert abs(stats["bust_rate"] - 33.33) < 0.1

    def test_finds_max_continuous(self):
        stats = get_summary_stats(SAMPLE_DATA)
        assert stats["max_continuous"] == 6
        assert stats["max_continuous_name"] == "股D"

    def test_finds_strongest_topic(self):
        stats = get_summary_stats(SAMPLE_DATA)
        assert stats["top_topic"] == "人工智能"

    def test_empty_data_returns_zeros(self):
        empty = {"date": "2026-02-28", "limit_up": [], "limit_broken": [], "summary": {}}
        stats = get_summary_stats(empty)
        assert stats["limit_up_count"] == 0
        assert stats["limit_broken_count"] == 0
        assert stats["max_continuous"] == 0


class TestGetTopicCounts:
    def test_returns_sorted_topics(self):
        topics = get_topic_counts(SAMPLE_DATA["limit_up"])
        assert topics[0]["topic"] == "人工智能"
        assert topics[0]["count"] == 2

    def test_includes_all_topics(self):
        topics = get_topic_counts(SAMPLE_DATA["limit_up"])
        topic_names = [t["topic"] for t in topics]
        assert "新能源" in topic_names
        assert "低空经济" in topic_names

    def test_splits_semicolon_reasons(self):
        stocks = [
            {"reason": "算力;AI", "name": "X", "code": "0"},
        ]
        topics = get_topic_counts(stocks)
        topic_names = [t["topic"] for t in topics]
        assert "算力" in topic_names
        assert "AI" in topic_names

    def test_empty_returns_empty_list(self):
        assert get_topic_counts([]) == []


class TestGetContinuousLadder:
    def test_groups_by_continuous_days(self):
        ladder = get_continuous_ladder(SAMPLE_DATA["limit_up"])
        days_map = {item["days"]: item for item in ladder}
        assert days_map[3]["count"] == 2
        assert days_map[1]["count"] == 1
        assert days_map[6]["count"] == 1

    def test_includes_top_stock_name(self):
        ladder = get_continuous_ladder(SAMPLE_DATA["limit_up"])
        six_board = next(item for item in ladder if item["days"] == 6)
        assert six_board["top_stock"] == "股D"

    def test_sorted_by_days_ascending(self):
        ladder = get_continuous_ladder(SAMPLE_DATA["limit_up"])
        days = [item["days"] for item in ladder]
        assert days == sorted(days)

    def test_empty_returns_empty_list(self):
        assert get_continuous_ladder([]) == []


class TestLoadHistory:
    def _write_day(self, data_dir: Path, date: str, limit_up_count: int = 2):
        data = {
            "date": date,
            "summary": {"zt_all": 50, "seal_rate": 80.0},
            "limit_up": [
                {"name": f"股{i}", "code": f"00000{i}", "continuous_days": i,
                 "reason": "人工智能", "amount": 5.0, "price": 10.0,
                 "change_pct": 10.0, "turnover_rate": 8.0}
                for i in range(1, limit_up_count + 1)
            ],
            "limit_broken": [],
        }
        (data_dir / f"{date}.json").write_text(json.dumps(data), encoding="utf-8")

    def test_returns_list_of_stats(self, tmp_path):
        self._write_day(tmp_path, "2026-02-25")
        self._write_day(tmp_path, "2026-02-26")
        result = load_history(data_dir=str(tmp_path))
        assert len(result) == 2
        assert result[0]["date"] == "2026-02-25"

    def test_respects_limit(self, tmp_path):
        for i in range(1, 6):
            self._write_day(tmp_path, f"2026-02-{20 + i:02d}")
        result = load_history(data_dir=str(tmp_path), limit=3)
        assert len(result) == 3

    def test_skips_invalid_json(self, tmp_path):
        self._write_day(tmp_path, "2026-02-25")
        (tmp_path / "2026-02-26.json").write_text("invalid json", encoding="utf-8")
        result = load_history(data_dir=str(tmp_path))
        assert len(result) == 1

    def test_empty_dir_returns_empty_list(self, tmp_path):
        result = load_history(data_dir=str(tmp_path))
        assert result == []


def test_history_entry_from_10d_full_fields():
    """_history_entry_from_10d 应透传全部新字段，缺字段默认填0。"""
    from processor import _history_entry_from_10d
    entry = {
        "date": "2026-02-10",
        "zt_all": 60,
        "limit_broken_count": 14,
        "seal_rate": 81.0,
        "up_count": 2500,
        "down_count": 1000,
        "dt_count": 7,
        "lb_count": 21,
        "up10_count": 55,
        "down9_count": 10,
        "yizi_count": 5,
        "zt_925": 3,
        "rate_1to2": 28.0,
        "rate_2to3": 15.0,
        "rate_3to4": 10.0,
        "lb_rate": 35.0,
        "lb_rate_prev": 30.0,
        "zt_amount": 1111.0,
        "total_amount": 8000.0,
        "sh_amount": 5000.0,
        "cyb_amount": 2000.0,
        "kcb_amount": 800.0,
        "shouban": 49,
        "er_lb": 11,
        "san_lb": 4,
        "si_lb": 3,
        "wu_lb": 1,
        "t_before10": 20,
        "t_1000_1130": 19,
        "t_1300_1400": 15,
        "t_1400_1500": 3,
    }
    result = _history_entry_from_10d(entry)
    assert result["up_count"] == 2500
    assert result["rate_1to2"] == 28.0
    assert result["shouban"] == 49
    assert result["t_1000_1130"] == 19
    assert result["zt_amount"] == 1111.0
    assert result["lb_rate"] == 35.0


def test_history_entry_from_10d_missing_fields_default_zero():
    """缺少新字段时应默认填0，不报错（旧缓存兼容性）。"""
    from processor import _history_entry_from_10d
    entry = {
        "date": "2026-01-01",
        "zt_all": 50,
        "limit_broken_count": 10,
        "seal_rate": 75.0,
        # 没有任何新字段
    }
    result = _history_entry_from_10d(entry)
    assert result["up_count"] == 0
    assert result["shouban"] == 0
    assert result["lb_rate"] == 0
