import json
import pytest
import requests
from pathlib import Path
from unittest.mock import MagicMock, patch
from fetcher import parse_daily_data, fetch_today_data, load_or_fetch


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_data.json"
FIXTURE_JSON = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class TestParseDailyData:
    def test_returns_dict_with_expected_keys(self):
        result = parse_daily_data(FIXTURE_JSON, date_str="2026-02-28")
        assert "date" in result
        assert "limit_up" in result
        assert "limit_broken" in result
        assert "summary" in result

    def test_combines_lbg_qt_gg_for_limit_up(self):
        result = parse_daily_data(FIXTURE_JSON, date_str="2026-02-28")
        # lbg has 2 stocks, qt has 1, gg has 0
        assert len(result["limit_up"]) == 3

    def test_limit_up_stock_has_required_fields(self):
        result = parse_daily_data(FIXTURE_JSON, date_str="2026-02-28")
        stock = result["limit_up"][0]
        assert stock["name"] == "测试股A"
        assert stock["code"] == "001896"
        assert stock["continuous_days"] == 7
        assert stock["reason"] == "算力;AI"
        assert stock["price"] == 13.34
        assert stock["change_pct"] == 9.98
        assert stock["amount"] == 16.84
        assert stock["turnover_rate"] == 8.39

    def test_lb_count_converted_to_int(self):
        result = parse_daily_data(FIXTURE_JSON, date_str="2026-02-28")
        for stock in result["limit_up"]:
            assert isinstance(stock["continuous_days"], int)

    def test_ztkb_maps_to_limit_broken(self):
        result = parse_daily_data(FIXTURE_JSON, date_str="2026-02-28")
        assert len(result["limit_broken"]) == 2
        broken = result["limit_broken"][0]
        assert broken["name"] == "测试股D"
        assert broken["code"] == "000010"

    def test_summary_stats_extracted(self):
        result = parse_daily_data(FIXTURE_JSON, date_str="2026-02-28")
        summary = result["summary"]
        assert summary["zt_all"] == 48
        assert summary["seal_rate"] == 75.0

    def test_date_set_correctly(self):
        result = parse_daily_data(FIXTURE_JSON, date_str="2026-02-28")
        assert result["date"] == "2026-02-28"


class TestFetchTodayData:
    def test_returns_parsed_data_on_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = FIXTURE_JSON
        mock_resp.raise_for_status.return_value = None

        with patch("fetcher.requests.get", return_value=mock_resp), \
             patch("fetcher.time.sleep"):
            result = fetch_today_data(date_str="2026-02-28")

        assert result["date"] == "2026-02-28"
        assert "limit_up" in result

    def test_raises_connection_error_on_http_failure(self):
        with patch("fetcher.requests.get", side_effect=requests.RequestException("timeout")):
            with pytest.raises(ConnectionError, match="爬取失败"):
                fetch_today_data(date_str="2026-02-28")

    def test_uses_today_when_date_not_provided(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = FIXTURE_JSON
        mock_resp.raise_for_status.return_value = None

        with patch("fetcher.requests.get", return_value=mock_resp), \
             patch("fetcher.time.sleep"):
            result = fetch_today_data()  # no date_str

        assert "date" in result


class TestLoadOrFetch:
    def test_loads_existing_data_file(self, tmp_path):
        date_str = "2026-02-28"
        data = {"date": date_str, "limit_up": [], "limit_broken": [], "summary": {}}
        (tmp_path / f"{date_str}.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

        result, warning = load_or_fetch(
            date_str=date_str, data_dir=str(tmp_path), fetch_fn=None
        )
        assert result["date"] == date_str
        assert warning is None

    def test_calls_fetch_when_no_file(self, tmp_path):
        date_str = "2026-02-28"
        mock_data = {"date": date_str, "limit_up": [{"name": "X"}], "limit_broken": [], "summary": {}}
        mock_fetch = MagicMock(return_value=mock_data)

        result, warning = load_or_fetch(
            date_str=date_str, data_dir=str(tmp_path), fetch_fn=mock_fetch
        )
        mock_fetch.assert_called_once()
        assert result["date"] == date_str

    def test_falls_back_to_latest_when_fetch_empty(self, tmp_path):
        prev_data = {"date": "2026-02-27", "limit_up": [{"name": "Y"}], "limit_broken": [], "summary": {}}
        (tmp_path / "2026-02-27.json").write_text(
            json.dumps(prev_data), encoding="utf-8"
        )
        # fetch returns empty data (休市)
        mock_fetch = MagicMock(
            return_value={"date": "2026-02-28", "limit_up": [], "limit_broken": [], "summary": {}}
        )

        result, warning = load_or_fetch(
            date_str="2026-02-28", data_dir=str(tmp_path), fetch_fn=mock_fetch
        )
        assert result["date"] == "2026-02-27"
        assert warning is not None

    def test_returns_warning_when_no_data_at_all(self, tmp_path):
        mock_fetch = MagicMock(
            return_value={"date": "2026-02-28", "limit_up": [], "limit_broken": [], "summary": {}}
        )

        result, warning = load_or_fetch(
            date_str="2026-02-28", data_dir=str(tmp_path), fetch_fn=mock_fetch
        )
        assert warning is not None

    def test_handles_connection_error_gracefully(self, tmp_path):
        mock_fetch = MagicMock(side_effect=ConnectionError("网络错误"))

        result, warning = load_or_fetch(
            date_str="2026-02-28", data_dir=str(tmp_path), fetch_fn=mock_fetch
        )
        # Should return empty data with warning (no fallback file exists)
        assert warning is not None
        assert result["limit_up"] == []

    def test_uses_today_date_when_none_provided(self, tmp_path):
        mock_fetch = MagicMock(
            return_value={"date": "2026-02-28", "limit_up": [{"name": "X"}], "limit_broken": [], "summary": {}}
        )
        result, warning = load_or_fetch(data_dir=str(tmp_path), fetch_fn=mock_fetch)
        mock_fetch.assert_called_once()


def test_parse_ten_days_full_fields():
    """_parse_ten_days 应解析全部30个指标字段。"""
    from fetcher import _parse_ten_days
    ten_days = [None] * 31
    ten_days[0] = ["2026-1-1", "2026-1-2"]
    for idx in [1,2,3,4,5,6,7,8,14,19,20,21,22,23,24,25,26,27,28,29,30]:
        ten_days[idx] = [float(idx)] * 2
    for idx in [9,10,11,12,13,15,16,17,18]:
        ten_days[idx] = [float(idx)] * 20

    result = _parse_ten_days(ten_days)
    assert len(result) == 2
    entry = result[0]
    assert entry["up_count"] == 1.0
    assert entry["down_count"] == 2.0
    assert entry["zt_all"] == 3.0
    assert entry["dt_count"] == 4.0
    assert entry["lb_count"] == 5.0
    assert entry["up10_count"] == 6.0
    assert entry["down9_count"] == 7.0
    assert entry["yizi_count"] == 8.0
    assert entry["shouban"] == 9.0
    assert entry["er_lb"] == 10.0
    assert entry["san_lb"] == 11.0
    assert entry["si_lb"] == 12.0
    assert entry["wu_lb"] == 13.0
    assert entry["zt_925"] == 14.0
    assert entry["t_before10"] == 15.0
    assert entry["t_1000_1130"] == 16.0
    assert entry["t_1300_1400"] == 17.0
    assert entry["t_1400_1500"] == 18.0
    assert entry["limit_broken_count"] == 19.0
    assert entry["seal_rate"] == 20.0
    assert entry["rate_1to2"] == 21.0
    assert entry["rate_2to3"] == 22.0
    assert entry["rate_3to4"] == 23.0
    assert entry["lb_rate"] == 24.0
    assert entry["lb_rate_prev"] == 25.0
    assert entry["zt_amount"] == 26.0
    assert entry["total_amount"] == 27.0
    assert entry["sh_amount"] == 28.0
    assert entry["cyb_amount"] == 29.0
    assert entry["kcb_amount"] == 30.0
