import json
from pathlib import Path
import pytest

from logic_b.storage import export_normalized_parquet, physical_cache_inventory


def test_inventory_uses_physical_sizes_and_month_rows(tmp_path):
    events=tmp_path/"events"/"2025-01-02.json"
    events.parent.mkdir()
    events.write_text(json.dumps({"date":"2025-01-02","limit_up":[{"symbol":"600001.SH"}],
        "limit_down":[],"limit_broken":[{"symbol":"600002.SH"}],"market":{}}),encoding="utf-8")
    daily=tmp_path/"daily"/"2025-01"/"600001.SH.json"
    daily.parent.mkdir(parents=True)
    daily.write_text(json.dumps({"records":{"2025-01-02":{"close":10}}}),encoding="utf-8")
    inv=physical_cache_inventory(tmp_path)
    assert inv["total_bytes"]==events.stat().st_size+daily.stat().st_size
    assert inv["r2_status"]=="NOT_CONNECTED"
    grouped={(x["dataset"],x["month"]):x for x in inv["by_source_type_month"]}
    assert grouped[("events","2025-01")]["rows"]==2
    assert grouped[("events","2025-01")]["trading_days"]==1
    assert grouped[("daily","2025-01")]["rows"]==1
    assert len(grouped[("events","2025-01")]["partition_manifest_sha256"])==64
    assert grouped[("daily","2025-01")]["partition_status"]=="MONTH_PARTITIONED"


def test_parquet_export_writes_measured_compressed_month_files(tmp_path):
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    event=tmp_path/"events"/"2025-01-02.json"
    event.parent.mkdir()
    event.write_text(json.dumps({"date":"2025-01-02","limit_up":[{"symbol":"600001.SH"}],
        "limit_down":[],"limit_broken":[],"market":{"market_temperature":42}}),encoding="utf-8")
    daily=tmp_path/"daily"/"2025-01"/"600001.SH.json"
    daily.parent.mkdir(parents=True)
    daily.write_text(json.dumps({"code":"600001.SH","provider":"baostock",
        "records":{"2025-01-02":{"open":10,"high":11,"low":9,"close":10}}}),encoding="utf-8")
    minute=tmp_path/"minute"/"600001.SH"/"2025-01-02.json"
    minute.parent.mkdir(parents=True)
    minute.write_text(json.dumps({"code":"600001.SH","day":"2025-01-02","bar_timestamp":"END",
        "bars":[{"time":"09:45","open