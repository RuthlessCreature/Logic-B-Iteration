import json
from pathlib import Path
import pytest
from logic_b.collect import _check_dates, _bs_code, fetch_xgb_day, fetch_daily, fetch_5m, make_dataset
from logic_b.identity import canonical_code

def test_vendor_event_cache_with_st_name_stable(tmp_path):
    def fake(url):
        if "market_indicator" in url:
            return {"data": [{"market_temperature": 40}]}, "0" * 64
        if "pool_name=limit_up" in url:
            return {"data": [{"symbol": "600001.SS", "stock_chi_name": "*ST某某",
                              "limit_up_days": 2, "break_limit_up_times": 1}]}, "a" * 64
        return {"data": []}, "b" * 64
    item = fetch_xgb_day("2020-01-02", tmp_path, request=fake)
    assert item["limit_up"][0]["symbol"] == "600001.SH"
    assert item["limit_up"][0]["name"] == "*ST某某"
    assert fetch_xgb_day("2020-01-02", tmp_path, request=lambda x: (_ for _ in ()).throw(Exception())) == item

def test_oa_code_translation():
    assert _bs_code("600001.SH") == "sh.600001"
    assert _bs_code("000001.SZ") == "sz.000001"

def test_daily_and_minute_provider_normalization(tmp_path):
    class Fake:
        def historical(self, code, start, end, *, freq):
            if freq == "d":
                return [{"date": "2020-01-02", "open": "10", "high": "10.2", "low": "9.8",
                         "close": "10", "preclose": "9.95", "volume": "12345", "isST": "1", "tradestatus": "1"}]
            return [{"date": "2020-01-03", "time": "20200103094500000", "open": "10.1",
                     "high": "10.2", "low": "10", "close": "10.1", "volume": "1500"}]
    a = fetch_daily("600001.SH", tmp_path, Fake(), start="2020-01-01", end="2020-01-10")
    b = fetch_5m("600001.SH", "2020-01-03", tmp_path, Fake())
    assert a["records"]["2020-01-02"]["is_st"] is True
    assert a["records"]["2020-01-02"]["preclose"] == 9.95
    assert a["records"]["2020-01-02"]["volume"] == 12345
    assert b["bars"][0]["time"] == "09:45"
    assert b["bar_timestamp"] == "END"

def test_unavailable_history_is_reported_not_filled(tmp_path):
    events = tmp_path / "events"
    events.mkdir()
    (events / "2020-01-02.json").write_text(json.dumps({"date":"2020-01-02",
      "limit_up":[{"symbol":"600001.SH", "limit_up_days":1}],"market":{}}), encoding="utf-8")
    (events / "2020-01-03.json").write_text(json.dumps({"date":"2020-01-03",
      "limit_up":[],"market":{}}), encoding="utf-8")
    out = make_dataset(tmp_path, ["2020-01-02", "2020-01-03"], save_to=tmp_path / "result.json")
    assert out["coverage_complete"] is False
    assert out["coverage"]["codes_with_daily_cache"] == 0
    assert out["days"][1]["daily"] == {}

def test_future_range_rejected():
    with pytest.raises(ValueError):
        _check_dates("2026-06-30", "2026-07-01")
