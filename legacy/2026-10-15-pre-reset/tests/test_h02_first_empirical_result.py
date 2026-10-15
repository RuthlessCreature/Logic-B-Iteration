from __future__ import annotations

import pandas as pd
import pytest
import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).parents[1] / "scripts/h02_first_empirical_result.py"
_SPEC = importlib.util.spec_from_file_location("h02_first_empirical_result_test_module", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load empirical result module: {_MODULE_PATH}")
result = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(result)


def event_data():
    days = ["20240927", "20240930", "20241008", "20241009", "20241010"]
    up = {
        "20240927": {"A", "B", "C"},
        "20240930": {"A"},
        "20241008": {"B"},
        "20241009": {"D"},
        "20241010": {"A"},
    }
    down = {
        "20240927": set(),
        "20240930": {"B"},
        "20241008": {"C"},
        "20241009": {"A"},
        "20241010": set(),
    }
    return {
        "calendar_days": days,
        "calendar_hashes": {day: f"calendar-{day}" for day in days},
        "limit_up": up,
        "limit_down": down,
        "partition_hashes": {
            "limit_up": {day: f"up-{day}" for day in days},
            "limit_down": {day: f"down-{day}" for day in days},
        },
        "archive_hashes": {"fixture": "f" * 64},
        "manifest_hashes_verified": 15,
        "manifest_hashes_expected": 15,
    }


def test_cross_holiday_event_counts_and_three_session_union():
    report = result.compute_statistics(event_data(), "20240930", "20241010")
    row = report["daily"][0]
    assert row["prior_candidate_date"] == "20240927"
    assert row["outcome_date"] == "20240930"
    assert row["three_day_limit_down_partition_sha256"] == [
        "down-20240930", "down-20241008", "down-20241009"
    ]
    assert row["prior_limit_up_candidates"] == 3
    assert row["next_day_limit_up_pool_matches"] == 1
    assert row["next_day_limit_down_pool_matches"] == 1
    assert row["three_trade_day_limit_down_pool_touches"] == 3
    assert report["overall"]["continuation"]["numerator"] == 1
    assert report["overall"]["continuation"]["denominator"] == 6
    assert report["overall"]["next_day_down_event"]["numerator"] == 1
    assert report["overall"]["three_day_down_event"]["numerator"] == 4
    assert report["overall"]["three_day_down_event"]["denominator"] == 4
    assert report["overall"]["three_day_observation_days"] == 2


def test_final_sessions_without_full_future_window_are_excluded_from_three_day():
    report = result.compute_statistics(event_data(), "20240930", "20241010")
    assert report["daily"][-1]["outcome_date"] == "20241010"
    assert report["daily"][-1]["three_day_denominator"] is None
    assert report["overall"]["three_day_observation_days"] == 2
    assert report["skipped_or_limited_days"]["THREE_DAY_WINDOW_NOT_FULLY_WITHIN_DEVELOPMENT_RANGE"] == 2


def test_missing_trading_session_partition_fails_closed():
    data = event_data()
    del data["limit_down"]["20241008"]
    with pytest.raises(result.EmpiricalDataError, match="missing .* partition"):
        result.compute_statistics(data, "20240930", "20241010")


def test_protected_date_cannot_enter_calendar_or_requested_range():
    data = event_data()
    data["calendar_days"].append("20260701")
    with pytest.raises(result.EmpiricalDataError, match="protected/post-development"):
        result.compute_statistics(data)
    with pytest.raises(result.EmpiricalDataError, match="protected/post-development"):
        result.compute_statistics(event_data(), "20260701", "20260701")


@pytest.mark.parametrize("dataset", ["limit_up", "limit_down"])
def test_duplicate_symbol_rows_are_rejected_before_set_conversion(dataset):
    frame = pd.DataFrame({"trade_date": ["2024-09-27", "2024-09-27"], "ts_code": ["A", "A"]})
    with pytest.raises(result.EmpiricalDataError, match=f"duplicate {dataset} symbol-day"):
        result._date_set(frame, dataset=dataset, partition="20240927")


def test_hash_verified_zero_column_empty_event_partition_means_no_events():
    codes, rows = result._date_set(pd.DataFrame(), dataset="limit_down", partition="20240927")
    assert codes == set()
    assert rows == 0


def test_year_and_half_year_group_by_outcome_date():
    data = event_data()
    days = ["20241231", "20250102", "20250103", "20250106"]
    data["calendar_days"] = days
    data["calendar_hashes"] = {day: f"cal-{day}" for day in days}
    data["limit_up"] = {day: {"X"} for day in days}
    data["limit_down"] = {day: set() for day in days}
    data["partition_hashes"] = {
        "limit_up": {day: f"up-{day}" for day in days},
        "limit_down": {day: f"down-{day}" for day in days},
    }
    report = result.compute_statistics(data, "20250102", "20250106")
    assert set(report["by_year"]) == {"2025"}
    assert set(report["by_half_year"]) == {"2025H1"}
    assert report["by_year"]["2025"]["outcome_trade_days"] == 3
    assert report["overall"]["cross_half_year_calendar_pairs"] == 1


def test_same_day_up_down_overlap_is_reported_not_suppressed():
    data = event_data()
    data["limit_up"]["20240930"].add("B")
    report = result.compute_statistics(data, "20240930", "20240930")
    assert report["daily"][0]["same_day_up_down_pool_overlap"] == 1
    assert report["overall"]["same_day_up_down_pool_overlap_symbol_days"] == 1


def test_unavailable_archive_set_fails_closed(tmp_path):
    with pytest.raises(result.EmpiricalDataError, match="exactly the five trusted"):
        result.load_market_events([tmp_path / "missing.zip"])


def test_empty_prior_pool_is_reported_as_skipped_not_zero_rate():
    data = event_data()
    data["limit_up"]["20240927"] = set()
    report = result.compute_statistics(data, "20240930", "20241008")
    assert report["skipped_or_limited_days"]["EMPTY_PRIOR_LIMIT_UP_POOL"] == 1
    assert all(row["outcome_date"] != "20240930" for row in report["daily"])


def test_report_serialization_is_deterministic(tmp_path):
    report = result.compute_statistics(event_data(), "20240930", "20241010")
    json_a, md_a = tmp_path / "a.json", tmp_path / "a.md"
    json_b, md_b = tmp_path / "b.json", tmp_path / "b.md"
    result.write_reports(report, json_a, md_a)
    result.write_reports(report, json_b, md_b)
    assert json_a.read_bytes() == json_b.read_bytes()
    assert md_a.read_bytes() == md_b.read_bytes()
    rendered = md_a.read_text(encoding="utf-8")
    assert "Unweighted daily rates" in rendered
    assert "2024H2" in rendered

