from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

PATH = Path(__file__).parents[1] / "scripts" / "h02_final_stock_forecast.py"
SPEC = importlib.util.spec_from_file_location("h02_final_stock_forecast", PATH)
assert SPEC and SPEC.loader
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


def frame(n=120):
    rng = np.random.default_rng(19)
    data = {name: rng.normal(size=n) for name in MODEL.FEATURES}
    data["vendor_streak_length"] = rng.integers(1, 5, size=n)
    data["continuation_D"] = (data["vendor_streak_length"] > 2).astype(int)
    return pd.DataFrame(data)


def test_logistic_is_deterministic_and_train_only_scaled():
    data = frame()
    train, test = data.iloc[:80], data.iloc[80:]
    a = MODEL._fit_predict(train, test, "continuation_D")
    b = MODEL._fit_predict(train, test, "continuation_D")
    assert np.array_equal(a, b)
    assert np.all((a > 0) & (a < 1))


def test_metrics_and_ranking_keep_exposure_metrics():
    metrics = MODEL._metrics(np.array([0, 1, 0, 1]), np.array([.1, .8, .2, .7]))
    assert metrics["brier"] < .1
    assert metrics["top_decile_event_recall"] == .5
    d = pd.DataFrame({"phase": ["forward_2026H1"]*4, "outcome_date": ["20260102"]*4,
        "ts_code": ["A","B","C","D"], "vendor_streak_length": [1,2,3,4],
        "p_continuation": [.2,.4,.6,.8], "p_down_next": [.1,.1,.1,.1], "p_down_three": [.2,.2,.2,.2],
        "continuation_D": [0,0,1,1], "down_next_D": [0,0,0,1], "down_three_D_to_D2": [0,0,1,1]})
    result = MODEL._ranking(d)["forward_2026H1"]
    assert result["risk_adjusted_top3"]["selected"] == 3
    assert result["risk_adjusted_top1"]["sessions"] == 1
    assert result["risk_adjusted_top3"]["candidate_symbol_day_coverage"] == .75


def test_ranking_uses_full_unfiltered_pool_as_baseline():
    d = pd.DataFrame({"phase": ["forward_2026H1"]*2, "outcome_date": ["20260102"]*2,
        "ts_code": ["A","B"], "vendor_streak_length": [1,2], "p_continuation": [.2,.8],
        "p_down_next": [.1,.2], "p_down_three": [.2,.3], "continuation_D": [0,1],
        "down_next_D": [0,1], "down_three_D_to_D2": [0,1]})
    result = MODEL._ranking(d)["forward_2026H1"]["unfiltered_all_candidates"]
    assert result["selected"] == 2
    assert result["candidate_symbol_day_coverage"] == 1.0
    assert result["three_day_down_rate"] == .5
