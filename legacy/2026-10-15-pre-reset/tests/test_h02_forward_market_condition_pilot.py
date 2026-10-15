from __future__ import annotations

import copy
import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest


FILE = Path(__file__).parents[1] / "scripts/h02_forward_market_condition_pilot.py"
SPEC = importlib.util.spec_from_file_location("h02_forward_market_condition_pilot", FILE)
assert SPEC is not None and SPEC.loader is not None
PILOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PILOT)


def synthetic_source():
    def business_days(start, count):
        out = []
        current = date.fromisoformat(start)
        while len(out) < count:
            if current.weekday() < 5:
                out.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
        return out

    days = business_days("2025-05-01", 30) + business_days("2025-07-01", 10) + business_days("2026-01-05", 10)
    rows = []
    for i, day in enumerate(days):
        n = 40 if i % 2 else 100
        k = (n // 4) + (1 if i % 3 == 0 else 0)
        row = {
            "outcome_date": day, "prior_limit_up_candidates": n,
            "next_day_limit_up_pool_matches": k,
            "next_day_limit_down_pool_matches": n // 20,
            "three_trade_day_limit_down_pool_touches": n // 10,
            "three_day_denominator": n,
        }
        if i >= len(days) - 2:
            row["three_trade_day_limit_down_pool_touches"] = None
            row["three_day_denominator"] = None
        rows.append(row)
    return {
        "classification": "TIER_D_HISTORICAL_MARKET_EVENT_OBSERVATION_NOT_TRADING_PERFORMANCE",
        "protected_holdout_accessed": False, "source_run_id": 100,
        "daily": rows,
    }


def test_frozen_market_breadth_pilot_produces_all_periods_without_stock_return_claims():
    report = PILOT.analyze(synthetic_source())
    assert report["status"] == "EXPLORE_FORWARD_DEV_ONLY"
    assert "NOT_PIT_OR_TRADING_RETURNS" in report["classification"]
    assert report["split"]["forward_development"][0].startswith("2026")
    assert set(report["outcomes"]) == {"continuation", "next_day_down_event", "three_day_down_event"}
    for name in report["outcomes"]:
        for period in ("train", "validation_2025H2", "forward_2026H1"):
            result = report["outcomes"][name]["by_period"][period]
            assert 0 <= result["baseline_brier"] <= 1
            assert 0 <= result["breadth_brier"] <= 1
            assert 0 <= result["breadth_plus_lag_brier"] <= 1


def test_future_outcome_cannot_change_prior_training_estimates():
    data = synthetic_source()
    original = PILOT.analyze(data)
    altered = copy.deepcopy(data)
    for row in altered["daily"]:
        if row["outcome_date"] >= "20250701":
            row["next_day_limit_up_pool_matches"] = 0
            row["next_day_limit_down_pool_matches"] = 0
            if row["three_day_denominator"] is not None:
                row["three_trade_day_limit_down_pool_touches"] = 0
    new = PILOT.analyze(altered)
    assert original["train_only_frozen_thresholds"] == new["train_only_frozen_thresholds"]
    for label in original["outcomes"]:
        for field in ("fitted_train_rate", "fitted_breadth_probabilities", "fitted_breadth_plus_lag_probabilities"):
            assert original["outcomes"][label][field] == new["outcomes"][label][field]


def test_last_two_training_three_day_labels_are_purged():
    data = synthetic_source()
    original = PILOT.analyze(data)
    altered = copy.deepcopy(data)
    train = [r for r in altered["daily"] if r["outcome_date"] <= "20250630"]
    assert len(train) >= 3
    for row in train[-2:]:
        row["three_trade_day_limit_down_pool_touches"] = row["three_day_denominator"]
    new = PILOT.analyze(altered)
    assert original["outcomes"]["three_day_down_event"]["fitted_train_rate"] == new["outcomes"]["three_day_down_event"]["fitted_train_rate"]


def test_protected_date_or_flag_rejected():
    data = synthetic_source()
    data["daily"].append({
        "outcome_date": "20260701",
        "prior_limit_up_candidates": 10,
        "next_day_limit_up_pool_matches": 1,
        "next_day_limit_down_pool_matches": 0,
        "three_trade_day_limit_down_pool_touches": None,
        "three_day_denominator": None,
    })
    with pytest.raises(ValueError, match="outside allowed"):
        PILOT.analyze(data)
    data = synthetic_source()
    data["protected_holdout_accessed"] = True
    with pytest.raises(ValueError, match="holdout flag"):
        PILOT.analyze(data)


def test_invalid_numerator_denominator_and_duplicate_day_rejected():
    source = synthetic_source()
    source["daily"][0]["next_day_limit_up_pool_matches"] = 999
    with pytest.raises(ValueError, match="numerator/denominator"):
        PILOT.analyze(source)
    source = synthetic_source()
    source["daily"][1]["outcome_date"] = source["daily"][0]["outcome_date"]
    with pytest.raises(ValueError, match="duplicate day"):
        PILOT.analyze(source)


def test_bad_source_classification_rejected():
    source = synthetic_source()
    source["classification"] = "REAL_TRADING_RETURNS"
    with pytest.raises(ValueError, match="pinned Tier-D"):
        PILOT.analyze(source)
