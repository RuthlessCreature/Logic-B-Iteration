import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "luna_goal_train", Path("scripts/luna_goal_train.py"))
TRAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRAIN)


def test_train_input_rejects_validation_or_protected_dates(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"classification": "HISTORICAL_DATA_PARTIAL_NOT_BROKER_FILLS",
        "coverage_complete": True, "days": [{"date": "2025-12-31"}, {"date": "2026-01-02"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="2025 dates only"):
        TRAIN._load_2025(path)


def test_train_input_requires_sorted_unique_2025_dates(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"classification": "HISTORICAL_DATA_PARTIAL_NOT_BROKER_FILLS",
        "coverage_complete": True, "days": [{"date": "2025-01-03"}, {"date": "2025-01-02"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="sorted and unique"):
        TRAIN._load_2025(path)


def test_fixed_version_schedule_is_finite():
    assert [x["id"] for x in TRAIN.VERSIONS] == [
        "V0_SIMPLE_STREAK", "V1_MARKET_STATE_GATE", "V2_BREAK_FEEDBACK_VETO"]
    assert TRAIN.VERSIONS[1]["params"]["min_market_temperature"] == 40
    assert TRAIN.VERSIONS[2]["params"]["max_breaks"] == 1


def test_market_state_proxies_are_lagged_for_next_session_only():
    rows = TRAIN._market_state([
        {"date": "2025-01-02", "market": {"market_temperature": 50},
         "limit_up": [{"symbol": "600001.SH"}], "limit_down": [], "limit_broken": []},
        {"date": "2025-01-03", "market": {"market_temperature": 30},
         "limit_up": [], "limit_down": [{"symbol": "600001.SH"}], "limit_broken": []},
    ])
    assert rows[0]["signal_eligible_on"] == "2025-01-03"
    assert rows[1]["strong_to_down_feedback_count"] == 1
    assert rows[1]["signal_eligible_on"] is None
    assert rows[1]["publication_time_certified"] is False
