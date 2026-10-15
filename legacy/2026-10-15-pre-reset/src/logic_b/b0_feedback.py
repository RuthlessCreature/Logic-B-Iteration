"""Adapt a completed, cost-accounted B0 portfolio equity path to H01 proxy inputs.

This represents hypothetical *B0 protocol followers*, not actual market
traders, not all limit-up chasers, and not evidence of causal psychology.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def b0_equity_to_feedback_ledger(
    daily_equity: pd.DataFrame, *,
    initial_cash: float, cohort_id: str = "B0_SIMULATED_FOLLOWERS",
) -> pd.DataFrame:
    if initial_cash <= 0 or not np.isfinite(initial_cash):
        raise ValueError("initial_cash must be positive and finite")
    if not {"date", "equity"} <= set(daily_equity.columns):
        raise ValueError("B0 run must have date and equity")
    if daily_equity.empty:
        raise ValueError("B0 run has no daily equity")
    data = daily_equity.copy()
    data["trade_date"] = pd.to_datetime(data["date"], errors="raise").dt.normalize()
    if data["trade_date"].duplicated().any():
        raise ValueError("duplicate B0 daily equity dates")
    data = data.sort_values("trade_date")
    data["equity"] = pd.to_numeric(data["equity"], errors="raise")
    if data["equity"].isna().any() or not np.isfinite(data["equity"]).all():
        raise ValueError("invalid B0 portfolio equity")
    if (data["equity"] <= 0).any():
        raise ValueError("portfolio exhausted; zero/negative equity is blocked")
    anchor = pd.concat(
        [pd.Series([initial_cash], dtype=float),
         data["equity"].reset_index(drop=True)], ignore_index=True
    )
    net_returns = anchor.pct_change().iloc[1:].to_numpy(dtype=float)
    iso = data["trade_date"].dt.strftime("%Y-%m-%d").to_list()
    return pd.DataFrame({
        "cohort_id": cohort_id,
        "trade_date": iso,
        "net_equity_return": net_returns,
        "available_at": [d + "T16:00:00+08:00" for d in iso],
        "source_type": "B0_PORTFOLIO_SIMULATION_NOT_ACTUAL_INVESTORS",
    })
