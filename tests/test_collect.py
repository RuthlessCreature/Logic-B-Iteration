import json
from pathlib import Path
from urllib.error import URLError
import pytest
from logic_b.collect import _check_dates, _bs_code, fetch_calendar, fetch_xgb_day, fetch_daily, fetch_5m, make_dataset
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

def test_daily_storage_is_split_into_reusable_month_partitions(tmp_path):
    class Fake:
        def __init__(self):
            self.calls = []
        def historical(self, code, start, end, *, freq):
            self.calls.append((start, end, freq))
            days = {"2025-01-02": "10", "2025-02-03": "11"}
            return [{"date": day, "open": price, "high": price, "low": price,
                     "close": price, "preclose": price, "volume": "100",
                     "isST": "0", "tradestatus": "1"}
                    for day, price in days.items() if start <= day <= end]
    client = Fake()
    result = fetch_daily("600001.SH", tmp_path, client, start="2025-01-01", end="2025-02-28")
    assert client.calls == [("2025-01-01", "2025-01-31", "d"),
                            ("2025-02-01", "2025-02-28", "d")]
    assert (tmp_path / "daily/2025-01/600001.SH.json").is_file()
    assert (tmp_path / "daily/2025-02/600001.SH.json").is_file()
    assert sorted(result["records"]) == ["2025-01-02", "2025-02-03"]
    again = fetch_daily("600001.SH", tmp_path, client, start="2025-01-01", end="2025-02-28")
    assert len(client.calls) == 2
    assert again["records"] == result["records"]
    assert again["cache_reused_months"] == 2
    assert again["downloaded_months"] == 0

def test_existing_full_range_daily_cache_migrates_without_download(tmp_path):
    import hashlib
    source = tmp_path / "daily" / "600001.SH.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"code":"600001.SH","range":["2025-01-01","2025-12-31"],
        "provider":"baostock","frequency":"d","adjustflag":"3","records":{
            "2025-01-02":{"close":10},"2025-02-03":{"close":11}}}),encoding="utf-8")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    class NoDownload:
        def historical(self,*args,**kwargs):
            raise AssertionError("monthly cache migration should reuse stored source rows")
    result=fetch_daily("600001.SH",tmp_path,NoDownload(),start="2025-01-01",end="2025-02-28")
    assert sorted(result["records"]) == ["2025-01-02","2025-02-03"]
    jan=json.loads((tmp_path/"daily/2025-01/600001.SH.json").read_text(encoding="utf-8"))
    feb=json.loads((tmp_path/"daily/2025-02/600001.SH.json").read_text(encoding="utf-8"))
    assert jan["parent_cache_sha256"] == source_sha
    assert feb["parent_cache_sha256"] == source_sha
    assert result["cache_reused_months"] == 2
    assert result["downloaded_months"] == 0

def test_xgb_network_retry_count_is_part_of_provenance(tmp_path):
    calls = 0
    def request(url):
        nonlocal calls
        calls += 1
        if calls in (1, 2):
            raise URLError("temporary network receive error")
        if "market_indicator" in url:
            return {"data": [{"market_temperature": 40}]}, "0" * 64
        if "pool_name=limit_up" in url:
            return {"data": [{"symbol": "600001.SH"}]}, "1" * 64
        return {"data": []}, "2" * 64
    item = fetch_xgb_day("2025-01-02", tmp_path, request=request)
    assert item["provenance"]["retry_count_by_endpoint"]["limit_up"] == 2
    assert item["provenance"]["retry_count_by_endpoint"]["limit_down"] == 0
    assert not (tmp_path / "failures.jsonl").exists()

def test_xgb_failed_endpoint_records_recoverable_partition(tmp_path):
    def request(_url):
        raise URLError("offline test failure")
    with pytest.raises(URLError):
        fetch_xgb_day("2025-01-02", tmp_path, request=request)
    failures = (tmp_path / "failures.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(failures) == 1
    failure = json.loads(failures[0])
    assert failure["provider"] == "xuangubao"
    assert failure["partition"] == "2025-01-02/limit_up"
    assert failure["attempts"] == 3

def test_baostock_network_receive_error_relogs_in_and_retries(monkeypatch):
    from logic_b.collect import BaoStockClient
    import logic_b.collect as collect
    monkeypatch.setattr(collect.time, "sleep", lambda _: None)
    class Result:
        fields = ["date", "code"]
        error_msg = "network receive error"
        def __init__(self, error_code):
            self.error_code = error_code
            self.done = False
        def next(self):
            if self.error_code != "0" or self.done:
                return False
            self.done = True
            return True
        def get_row_data(self):
            return ["2025-01-02", "sh.600001"]
    class FakeBaoStock:
        def __init__(self):
            self.query_count = 0
            self.login_count = 0
        def login(self):
            self.login_count += 1
            return type("Login", (), {"error_code": "0"})()
        def logout(self):
            return None
        def query_history_k_data_plus(self, *args, **kwargs):
            self.query_count += 1
            return Result("10002007" if self.query_count == 1 else "0")
    fake = FakeBaoStock()
    client = BaoStockClient()
    client.bs = fake
    client.query_retry_count = 0
    client.query_failures = []
    client.query_count = 0
    assert client.historical("600001.SH", "2025-01-01", "2025-01-31", freq="d") == [
        {"date": "2025-01-02", "code": "sh.600001"}]
    assert fake.query_count == 2
    assert fake.login_count == 1
    assert client.query_retry_count == 1

def test_trade_calendar_uses_month_partitions_and_cache(tmp_path):
    class Fake:
        def __init__(self): self.calls=[]
        def trade_calendar(self,start,end):
            self.calls.append((start,end))
            return ["2025-01-02"] if start.startswith("2025-01") else ["2025-02-03"]
    client=Fake()
    result=fetch_calendar("2025-01-01","2025-02-28",tmp_path,client)
    assert result["days"] == ["2025-01-02","2025-02-03"]
    assert client.calls == [("2025-01-01","2025-01-31"),("2025-02-01","2025-02-28")]
    assert len(result["partitions"]) == 2
    again=fetch_calendar("2025-01-01","2025-02-28",tmp_path,client)
    assert again["days"] == result["days"]
    assert again["cache_reused_months"] == 2
    assert len(client.calls) == 2
