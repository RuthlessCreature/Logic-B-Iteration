"""B0 proxy ledger tests: returns/costs are inherited, not re-simulated."""
import pandas as pd
import pytest

from logic_b.b0_feedback import b0_equity_to_feedback_ledger


def test_b0_returns_use_original_account_anchor():
    d = pd.DataFrame({
        "date": ["20261009", "20261012", "20261013"],
        "equity": [998000, 1000000, 1030000],
    })
    ledger = b0_equity_to_feedback_ledger(d, initial_cash=1_000_000)
    assert list(ledger.cohort_id.unique()) == ["B0_SIMULATED_FOLLOWERS"]
    assert ledger.net_equity_return.iloc[0] == pytest.approx(-0.002)
    assert ledger.net_equity_return.iloc[1] == pytest.approx(1000000 / 998000 - 1)
    assert ledger.net_equity_return.iloc[2] == pytest.approx(.03)
    assert list(ledger.available_at) == [
        "2026-10-09T16:00:00+08:00",
        "2026-10-12T16:00:00+08:00",
        "2026-10-13T16:00:00+08:00",
    ]


def test_unsorted_dates_normalized_and_sorted():
    d = pd.DataFrame({"date": ["20261012", "20261009"],
                      "equity": [120, 110]})
    x = b0_equity_to_feedback_ledger(d, initial_cash=100)
    assert x.trade_date.to_list() == ["2026-10-09", "2026-10-12"]
    assert x.net_equity_return.to_list() == pytest.approx([.1, 120 / 110 - 1])


def test_repeated_dates_are_not_silently_deduplicated():
    d = pd.DataFrame({"date": ["20261012", "20261012"], "equity": [120, 110]})
    with pytest.raises(ValueError, match="duplicate"):
        b0_equity_to_feedback_ledger(d, initial_cash=100)


def test_invalid_initial_cash_rejected():
    d = pd.DataFrame({"date": ["20261012"], "equity": [120]})
    with pytest.raises(ValueError, match="initial_cash"):
        b0_equity_to_feedback_ledger(d, initial_cash=0)
