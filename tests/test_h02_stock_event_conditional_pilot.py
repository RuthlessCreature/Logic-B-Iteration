from __future__ import annotations

from copy import deepcopy
from datetime import date,timedelta
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("h02_stock_conditional_pilot", SCRIPTS / "h02_stock_event_conditional_pilot.py")
assert SPEC and SPEC.loader
PILOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PILOT)


def business_days(start, count):
    days=[]
    d=date.fromisoformat(start)
    while len(days)<count:
        if d.weekday()<5:
            days.append(d.strftime("%Y%m%d"))
        d+=timedelta(days=1)
    return days


def sample():
    days=(business_days("2024-09-23",6)+business_days("2025-06-02",25)
          +business_days("2025-07-01",8)+business_days("2026-01-05",8))
    up={}
    down={}
    for i,d in enumerate(days):
        # One continuously strong symbol, plus two intermittently active ones.
        up[d]={"A"} | ({"B"} if i%2==0 else set()) | ({"C"} if i%3==0 else set())
        down[d]=({"C"} if i%7==0 else set())
    return {"calendar_days":days,"limit_up":up,"limit_down":down,"archive_hashes":{"synthetic":"f"*64}}


def test_stock_event_pilot_has_frozen_tier_d_output():
    report=PILOT.analyze(sample())
    assert report["classification"].startswith("TIER_D")
    assert report["protected_holdout_accessed"] is False
    assert set(report["outcomes"])=={"continuation","down_next","down_three"}
    assert report["periods"]["validation_2025H2"]["candidate_symbol_days"]>0
    assert report["periods"]["forward_2026H1"]["repeat_event"]>0
    for v in report["outcomes"].values():
        for part in v["by_period"].values():
            assert 0<=part["brier_baseline"]<=1
            assert 0<=part["brier_joint"]<=1


def test_future_event_changes_do_not_change_training_fitted_probabilities():
    src=sample()
    before=PILOT.analyze(src)
    later=deepcopy(src)
    for day in later["calendar_days"]:
        if day>="20250701":
            later["limit_down"][day]=set()
            later["limit_up"][day]={"B","Z"}
    after=PILOT.analyze(later)
    for label in PILOT.LABELS:
        assert before["outcomes"][label]["trained_joint_probabilities"]==after["outcomes"][label]["trained_joint_probabilities"]
        assert before["outcomes"][label]["training_pooled_probability"]==after["outcomes"][label]["training_pooled_probability"]


def test_reject_protected_date_in_calendar_before_processing():
    src=sample()
    src["calendar_days"].append("20260701")
    src["limit_up"]["20260701"]={"A"}
    src["limit_down"]["20260701"]=set()
    with pytest.raises(ValueError,match="protected date"):
        PILOT.analyze(src)


def test_missing_partition_is_not_silent_no_event():
    src=sample()
    del src["limit_down"]["20250701"]
    with pytest.raises(ValueError,match="coverage"):
        PILOT.analyze(src)


def test_repeating_prior_pool_is_a_prior_only_feature():
    src=sample()
    before=PILOT.analyze(src)
    new=deepcopy(src)
    # Changing last outcome day's current pool can only affect that day's
    # result, not previously fitted training estimates.
    new["limit_up"]["20260114"]={"A","B","C"} if "20260114" in new["limit_up"] else set()
    after=PILOT.analyze(new)
    assert before["outcomes"]["continuation"]["trained_streak_probabilities"]==after["outcomes"]["continuation"]["trained_streak_probabilities"]
