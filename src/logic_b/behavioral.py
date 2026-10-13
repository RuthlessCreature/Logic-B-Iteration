"""H01 point-in-time behavioral feedback from *synthetic* cohort equity.

This feature is an observable proxy for reinforcement, NOT verified actual
returns of identifiable 'hot money' investors or retail accounts.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

REQUIRED = {"cohort_id", "trade_date", "net_equity_return", "available_at"}
SH_TZ = "Asia/Shanghai"


def build_feedback_features(
    equity: pd.DataFrame,
    calendar: Sequence[str],
    lookback: int = 3,
    checkpoint: str = "09:35",
) -> pd.DataFrame:
    """Compute date t's cohort feedback from finalized dates STRICTLY < t.

    equity must contain exactly one row per cohort and trading calendar date,
    including explicit zero net returns for *valid* no-trade days. Missing
    sessions are blocked, never silently imputed. 'available_at' must be
    the actual time finalized daily P&L was observable.
    """
    if lookback < 2:
        raise ValueError("lookback must be >= 2")
    missing = REQUIRED - set(equity.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    dates = pd.to_datetime(list(calendar), format="%Y-%m-%d", errors="raise")
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("calendar must be unique and strictly increasing")
    if equity.empty:
        raise ValueError("cohort equity missing; do not synthesize zeros")

    df = equity.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="raise").dt.normalize()
    df["available_at"] = pd.to_datetime(
        df["available_at"], errors="raise", utc=True
    ).dt.tz_convert(SH_TZ)
    df["net_equity_return"] = pd.to_numeric(df["net_equity_return"], errors="raise")
    if df[list(REQUIRED)].isna().any().any():
        raise ValueError("null critical cohort data")
    if not np.isfinite(df["net_equity_return"]).all() or (df["net_equity_return"] <= -1).any():
        raise ValueError("invalid daily equity return")
    if df.duplicated(["cohort_id", "trade_date"]).any():
        raise ValueError("duplicate cohort-day rows")
    if not df["trade_date"].isin(dates).all():
        raise ValueError("cohort dates absent from calendar")

    try:
        hh, mm = (int(v) for v in checkpoint.split(":"))
    except (ValueError, TypeError) as exc:
        raise ValueError("checkpoint must be HH:MM") from exc
    if not 0 <= hh <= 23 or not 0 <= mm <= 59:
        raise ValueError("invalid checkpoint")

    out = []
    for cohort, part in df.groupby("cohort_id", sort=True):
        part = part.sort_values("trade_date").set_index("trade_date")
        if set(part.index) != set(dates):
            raise ValueError(f"incomplete calendar for {cohort}; blocked, not imputed")
        for i, day in enumerate(dates):
            cutoff = pd.Timestamp(day.date(), tz=SH_TZ).replace(hour=hh, minute=mm)
            base = {
                "cohort_id": cohort,
                "trade_date": day.strftime("%Y-%m-%d"),
                "asof_at": cutoff.isoformat(),
                "lookback": lookback,
            }
            if i < lookback:
                status = "BLOCKED_INSUFFICIENT_HISTORY"
            else:
                window = part.loc[dates[i - lookback:i]]
                status = (
                    "BLOCKED_DATA_NOT_YET_AVAILABLE"
                    if (window["available_at"] > cutoff).any()
                    else "READY"
                )
            if status != "READY":
                out.append({
                    **base, "status": status,
                    "lagged_compound_return": np.nan,
                    "lagged_win_day_fraction": np.nan,
                    "lagged_loss_day_fraction": np.nan,
                })
                continue
            rets = window["net_equity_return"].to_numpy(dtype=float)
            out.append({
                **base, "status": "READY",
                "lagged_compound_return": float(np.prod(1 + rets) - 1),
                "lagged_win_day_fraction": float(np.mean(rets > 0)),
                "lagged_loss_day_fraction": float(np.mean(rets < 0)),
            })
    return pd.DataFrame(out)
