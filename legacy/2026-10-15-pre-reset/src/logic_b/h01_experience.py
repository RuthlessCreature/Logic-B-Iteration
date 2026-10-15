"""Point-in-time market-level *experience proxy* from prior limit-up cohort.

The provider's 'yesterday_limit_up_avg_pcp' is an observed historical market
summary, NOT executable cohort P&L, not individual investor costs, and not proof
that imitation or psychological reinforcement occurred.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .h01_activity import H01DataBlocked
from .storage import LocalParquetStore


def build_vendor_limitup_experience(
    store: LocalParquetStore,
    trade_dates: Sequence[str],
    *,
    lookback: int = 3,
    checkpoint: str = "09:35",
) -> pd.DataFrame:
    if lookback < 2:
        raise ValueError("minimum lookback is 2")
    dates = list(trade_dates)
    if len(dates) < lookback + 1 or dates != sorted(set(dates)):
        raise H01DataBlocked("unsorted, duplicate or insufficient calendar")
    try:
        clock = pd.to_datetime("2000-01-01 " + checkpoint, errors="raise")
    except (ValueError, TypeError) as exc:
        raise H01DataBlocked("invalid checkpoint time") from exc

    rows = []
    for day in dates:
        if len(day) != 8 or not day.isdigit():
            raise H01DataBlocked(f"invalid date: {day}")
        if not store.exists("market_indicator", day) or not store.verify("market_indicator", day):
            raise H01DataBlocked(f"missing vendor summary or bad manifest: {day}")
        x = store.read_frame("market_indicator", day)
        if x.empty or "yesterday_limit_up_avg_pcp" not in x:
            raise H01DataBlocked(f"missing market-experience field: {day}")
        if "timestamp" in x:
            x = x.sort_values("timestamp")
        elif "event_time" in x:
            x = x.sort_values("event_time")
        else:
            raise H01DataBlocked(f"untimed market indicator: {day}")
        raw = pd.to_numeric(x["yesterday_limit_up_avg_pcp"], errors="coerce").iloc[-1]
        if not np.isfinite(raw):
            raise H01DataBlocked(f"invalid market-experience value: {day}")
        rows.append(float(raw))

    result = []
    for i, day in enumerate(dates):
        date = pd.to_datetime(day, format="%Y%m%d").strftime("%Y-%m-%d")
        asof = pd.Timestamp(date, tz="Asia/Shanghai").replace(
            hour=clock.hour, minute=clock.minute
        )
        ready = i >= lookback
        previous = np.array(rows[i - lookback:i], dtype=float) if ready else np.array([])
        result.append({
            "cohort_id": "VENDOR_PRIOR_LIMITUP_MARKET_PROXY",
            "trade_date": date,
            "asof_at": asof.isoformat(),
            "status": "READY" if ready else "BLOCKED_INSUFFICIENT_HISTORY",
            # Historical indicator scale is used AS REPORTED. Ridge feature standardizes it.
            # Arithmetic average is descriptive; these are not invested portfolio returns.
            "h01_experience_proxy": float(previous.mean()) if ready else np.nan,
            "metric": "lagged_mean_of_yesterday_limit_up_avg_pcp_raw",
            "actual_cohort_profit": False,
        })
    return pd.DataFrame(result)
