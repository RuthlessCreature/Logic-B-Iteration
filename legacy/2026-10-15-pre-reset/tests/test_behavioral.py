"""Synthetic fixtures for psychology-first H01 feature point-in-time safety."""
import pandas as pd
import pytest

from logic_b.behavioral import build_feedback_features


def sample():
    calendar = ["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13"]
    equity = pd.DataFrame({
        "cohort_id": ["momentum"] * 4,
        "trade_date": calendar,
        "net_equity_return": [0.01, -0.01, 0.02, 0.90],
        "available_at": [
            "2026-10-08T16:00:00+08:00",
            "2026-10-09T16:00:00+08:00",
            "2026-10-12T16:00:00+08:00",
            "2026-10-13T16:00:00+08:00",
        ],
    })
    return equity, calendar


def test_strictly_lagged_features_ignore_t_future_return():
    equity, dates = sample()
    x = build_feedback_features(equity, dates)
    assert list(x.status)[:3] == ["BLOCKED_INSUFFICIENT_HISTORY"] * 3
    assert x.status.iloc[3] == "READY"
    assert x.lagged_compound_return.iloc[3] == pytest.approx(1.01 * .99 * 1.02 - 1)
    assert x.lagged_win_day_fraction.iloc[3] == pytest.approx(2 / 3)
    equity.loc[3, "net_equity_return"] = -0.99
    assert build_feedback_features(equity, dates).lagged_compound_return.iloc[3] == pytest.approx(
        x.lagged_compound_return.iloc[3]
    )


def test_late_upstream_data_blocks():
    equity, dates = sample()
    equity.loc[2, "available_at"] = "2026-10-13T10:00:00+08:00"
    assert build_feedback_features(equity, dates).status.iloc[3] == "BLOCKED_DATA_NOT_YET_AVAILABLE"


def test_missing_sessions_are_not_silently_imputed_as_flat():
    equity, dates = sample()
    with pytest.raises(ValueError, match="incomplete calendar"):
        build_feedback_features(equity.iloc[:-1], dates)


def test_duplicates_not_counted_twice():
    equity, dates = sample()
    with pytest.raises(ValueError, match="duplicate"):
        build_feedback_features(pd.concat([equity, equity.iloc[[0]]]), dates)


def test_invalid_equity_is_rejected():
    equity, dates = sample()
    equity.loc[1, "net_equity_return"] = -1.0
    with pytest.raises(ValueError, match="invalid daily equity return"):
        build_feedback_features(equity, dates)
