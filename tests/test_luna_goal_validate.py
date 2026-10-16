import json
from pathlib import Path

import pytest

import scripts.luna_goal_validate as validation


def _inputs(tmp_path):
    frozen = tmp_path / "frozen.json"
    frozen.write_text(json.dumps({"status": "NO_CANDIDATE", "selected_strategy": None,
        "train_window": ["2025-01-01", "2025-12-31"], "selection_sha256": "f" * 64}), encoding="utf-8")
    days = [
        {"date": "2026-01-05", "limit_up": [{"symbol": "600001.SH"}], "limit_down": [],
         "limit_broken": [], "market": {"market_temperature": 30}, "daily": {}, "bars_5m": {}},
        {"date": "2026-01-06", "limit_up": [], "limit_down": [{"symbol": "600001.SH"}],
         "limit_broken": [], "market": {"market_temperature": 28}, "daily": {}, "bars_5m": {}},
    ]
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps({"classification": "HISTORICAL_DATA", "coverage_complete": True,
        "days": days}), encoding="utf-8")
    stable = [{k: day.get(k) for k in ("date", "limit_up", "limit_down", "limit_broken", "market", "daily", "bars_5m")}
              for day in days]
    aggregate = tmp_path / "aggregate.json"
    aggregate.write_text(json.dumps({"input_sha256": validation._digest(stable), "coverage": {
        "event_days": 2, "event_failures": [], "daily_failures": [], "source_codes": 1,
        "minute_requested": 1, "minute_with_bars": 1, "missing_minute_target_days": 0,
        "suspended_target_days": 0, "baostock_queries": 3, "baostock_retries": 0,
        "baostock_api_failures": 0, "planning_outcome_reasons": {"NO_FILL_LIMIT_UP": 1},
        "calendar_cache": {}, "events_cache": {}, "daily_cache": {}, "minute_cache": {}}}), encoding="utf-8")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"initial_cash": 10000, "final_equity": 9900, "return_pct": -1,
        "max_drawdown_pct": -2, "closed_trades": [], "fills": [], "orders": [],
        "daily_equity": [{"day": day["date"], "equity": 10000-i*100, "economically_reconciled": True,
            "symbol": None, "mark_stale": False, "corporate_action_unreconciled": False}
            for i, day in enumerate(days)], "account_unresolved_corporate_actions": []}), encoding="utf-8")
    cache = tmp_path / "cache"
    (cache / "calendar").mkdir(parents=True)
    (cache / "calendar" / "2026-01.json").write_text(json.dumps({"days": ["2026-01-05", "2026-01-06"]}), encoding="utf-8")
    out = tmp_path / "public"
    out.mkdir()
    (out / "dashboard.html").write_text("<html>training dashboard</html>", encoding="utf-8")
    return frozen, dataset, aggregate, ledger, cache, out


def test_validation_outputs_v0_only_and_insufficient_when_no_candidate(tmp_path, monkeypatch):
    paths = _inputs(tmp_path)
    monkeypatch.setattr(validation, "export_normalized_parquet", lambda _root: {})
    monkeypatch.setattr(validation, "physical_cache_inventory", lambda _root: {
        "total_bytes": 100, "total_files": 1, "by_source_type_month": [{
            "provider": "xuangubao", "dataset": "events", "year": "2026", "month": "2026-01",
            "format": "json", "files": 2, "physical_bytes": 100, "mib": 0.0001, "rows": 3,
            "trading_days": 2, "partition_status": "MONTH_PARTITIONED", "partition_manifest_sha256": "a"*64}]})
    report = validation.build_validation(*paths[:4], paths[4], paths[5], "verified-head")
    assert report["status"] == "INSUFFICIENT"
    assert report["frozen_selection"]["selected_strategy"] is None
    assert report["sessions"] == 2
    assert (paths[5] / "validation_v0_equity.csv").is_file()
    assert "V0_REFERENCE_ONLY_NO_FROZEN_CANDIDATE" in (paths[5] / "validation_v0_equity.csv").read_text(encoding="utf-8")
    assert "2026H1 开发验证" in (paths[5] / "dashboard.html").read_text(encoding="utf-8")


def test_validation_refuses_protected_data_and_candidate_freeze(tmp_path):
    paths = _inputs(tmp_path)
    dataset = json.loads(paths[1].read_text(encoding="utf-8"))
    dataset["days"].append(dict(dataset["days"][-1], date="2026-07-01"))
    paths[1].write_text(json.dumps(dataset), encoding="utf-8")
    with pytest.raises(ValueError, match="2026H1 dates only"):
        validation.build_validation(*paths[:4], paths[4], paths[5])
    frozen = json.loads(paths[0].read_text(encoding="utf-8"))
    frozen["status"] = "FROZEN"
    paths[0].write_text(json.dumps(frozen), encoding="utf-8")
    with pytest.raises(ValueError, match="NO_CANDIDATE"):
        validation.build_validation(*paths[:4], paths[4], paths[5])
