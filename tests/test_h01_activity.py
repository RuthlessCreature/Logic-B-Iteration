"""H01-A: integrity and causal-timing tests on synthetic data (not A-share results)."""
import numpy as np
import pandas as pd
import pytest

from logic_b.behavioral import build_feedback_features
from logic_b.h01_activity import (
    H01DataBlocked, limitup_continuation, join_feedback_activity,
    expanding_window_h01,
)
from logic_b.storage import LocalParquetStore


def fixture(tmp_path, n=30):
    store = LocalParquetStore(tmp_path)
    dates = pd.bdate_range("2026-02-02", periods=n).strftime("%Y%m%d").tolist()
    for i, day in enumerate(dates):
        # Small, deliberately changing cohorts. Unobserved accounts are NOT inferred.
        ids = [f"{v:06d}.SZ" for v in range(i % 5, i % 5 + 7 + i % 3)]
        frame = pd.DataFrame({"ts_code": ids, "trade_date": day})
        store.write_frame("limit_up", day, frame, metadata={"source": "test"})
    activity = limitup_continuation(store, dates)
    iso = pd.to_datetime(dates).strftime("%Y-%m-%d").tolist()
    ledger = pd.DataFrame({
        "cohort_id": ["momentum_proxy"] * n,
        "trade_date": iso,
        "net_equity_return": [((i % 7) - 3) / 1000 for i in range(n)],
        "available_at": [d + "T16:00:00+08:00" for d in iso],
    })
    features = build_feedback_features(ledger, iso, lookback=3)
    return store, dates, activity, features


def test_repeat_denominator_uses_yesterday_limitup_symbols(tmp_path):
    store, dates, activity, features = fixture(tmp_path)
    s0 = set(store.read_frame("limit_up", dates[0]).ts_code)
    s1 = set(store.read_frame("limit_up", dates[1]).ts_code)
    assert activity.repeat_rate.iloc[1] == pytest.approx(len(s0 & s1) / len(s0))
    assert np.isnan(activity.repeat_rate.iloc[0])


def test_missing_partition_is_not_treated_as_zero_activity(tmp_path):
    store, dates, _, _ = fixture(tmp_path)
    store.frame_path("limit_up", dates[5]).unlink()
    with pytest.raises(H01DataBlocked, match="missing/invalid"):
        limitup_continuation(store, dates)


def test_invalid_duplicate_symbols_block(tmp_path):
    store, dates, _, _ = fixture(tmp_path)
    frame = pd.DataFrame({"ts_code": ["000001.SZ", "000001.SZ"], "trade_date": [dates[8]] * 2})
    store.write_frame("limit_up", dates[8], frame)
    with pytest.raises(H01DataBlocked, match="duplicate"):
        limitup_continuation(store, dates)


def test_h01_evaluator_is_outcome_lagged(tmp_path):
    _, _, activity, features = fixture(tmp_path)
    joined = join_feedback_activity(features, activity, "momentum_proxy")
    summary, forecasts = expanding_window_h01(joined, min_train_days=10, min_test_days=5)
    assert summary["test_days"] >= 5
    assert len(forecasts) == summary["test_days"]
    # Changing a future outcome must not change *the same day*'s prediction.
    index = joined.index[-1]
    changed = joined.copy()
    changed.loc[index, "repeat_rate"] = 0.97
    _, alternate = expanding_window_h01(changed, min_train_days=10, min_test_days=5)
    a, b = forecasts.iloc[-1], alternate.iloc[-1]
    assert a.baseline_prediction == pytest.approx(b.baseline_prediction)
    assert a.h01_prediction == pytest.approx(b.h01_prediction)
    assert a.observed_repeat_rate != b.observed_repeat_rate


def test_missing_feature_is_blocked_not_reported_as_evidence(tmp_path):
    _, _, activity, features = fixture(tmp_path)
    features["status"] = "BLOCKED_DATA_NOT_YET_AVAILABLE"
    joined = join_feedback_activity(features, activity, "momentum_proxy")
    result, forecasts = expanding_window_h01(joined, min_train_days=10, min_test_days=5)
    assert result["status"].startswith("BLOCKED")
    assert forecasts.empty


def test_prior_day_label_late_publication_is_blocked(tmp_path):
    _, _, activity, features = fixture(tmp_path)
    activity.loc[activity.index[3], "label_observed_at"] = (
        activity.loc[activity.index[4], "trade_date"] + "T12:00:00+08:00"
    )
    with pytest.raises(H01DataBlocked, match="prior-day activity"):
        join_feedback_activity(features, activity, "momentum_proxy")


def test_cohort_calendar_mismatch_is_error(tmp_path):
    _, _, activity, features = fixture(tmp_path)
    with pytest.raises(H01DataBlocked, match="calendar mismatch"):
        join_feedback_activity(features.iloc[:-1], activity, "momentum_proxy")
