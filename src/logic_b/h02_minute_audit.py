"""H02-only minute execution structural audit.

This checks whether a candidate has *structurally usable* historical one-minute
bars at the 09:35 decision boundary. It does NOT certify the provider's
historical publication timestamp, official daily price limits, or a fill.
Sparse bars are not automatically treated as a halt or corruption.
"""
from __future__ import annotations

import math
import pandas as pd


REQUIRED = frozenset({"trade_time", "open", "high", "low", "close", "vol"})


def audit_h02_minute_execution(bars: pd.DataFrame, trade_date: str) -> dict:
    """Fail closed, returning a machine-readable reason without filling gaps.

    The 09:35 bar is allowed for signal construction; fills require later bars.
    A positive-volume later bar is *necessary*, never sufficient, for a fill.
    """
    if bars.empty:
        return {"status": "BLOCKED", "reason": "empty_minute_data"}
    missing = sorted(REQUIRED - set(bars.columns))
    if missing:
        return {"status": "BLOCKED", "reason": "missing_execution_fields", "fields": missing}
    if len(trade_date) != 8 or not trade_date.isdigit():
        return {"status": "BLOCKED", "reason": "invalid_trade_date"}
    times = pd.to_datetime(bars["trade_time"], errors="coerce")
    if times.isna().any():
        return {"status": "BLOCKED", "reason": "invalid_minute_timestamp"}
    if times.dt.tz is not None:
        return {"status": "BLOCKED", "reason": "timezone_must_be_exchange_local"}
    if not times.is_unique or not times.is_monotonic_increasing:
        return {"status": "BLOCKED", "reason": "duplicate_or_unsorted_minute"}
    if (times.dt.strftime("%Y%m%d") != trade_date).any():
        return {"status": "BLOCKED", "reason": "wrong_trading_day"}
    clock = times.dt.strftime("%H:%M:%S")
    in_session = ((clock >= "09:30:00") & (clock <= "11:30:00")) | (
        (clock >= "13:00:00") & (clock <= "15:00:00"))
    if (~in_session).any() or (times.dt.second != 0).any():
        return {"status": "BLOCKED", "reason": "out_of_session_or_nonminute_timestamp"}
    decision = pd.Timestamp(f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} 09:35:00")
    if not (times == decision).any():
        return {"status": "BLOCKED", "reason": "missing_0935_checkpoint"}
    later = times > decision
    if not later.any():
        return {"status": "BLOCKED", "reason": "missing_post_signal_bar"}

    px = bars[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    if not px.notna().all().all() or not (px > 0).all().all():
        return {"status": "BLOCKED", "reason": "invalid_ohlc"}
    if (px["high"] < px[["open", "low", "close"]].max(axis=1)).any() or (
        px["low"] > px[["open", "high", "close"]].min(axis=1)
    ).any():
        return {"status": "BLOCKED", "reason": "inconsistent_ohlc"}
    vol = pd.to_numeric(bars["vol"], errors="coerce")
    if vol.isna().any() or not vol.map(lambda x: math.isfinite(x) and x >= 0).all():
        return {"status": "BLOCKED", "reason": "invalid_minute_volume"}
    if not (vol.loc[later] > 0).any():
        return {"status": "BLOCKED", "reason": "no_post_signal_trade_volume"}
    return {
        "status": "STRUCTURALLY_VALID",
        "reason": "not_point_in_time_or_fill_certified",
        "bar_count": len(bars),
        "post_signal_bars": int(later.sum()),
        "post_signal_positive_volume_bars": int((vol.loc[later] > 0).sum()),
        "sparse_bars_not_auto_halt": True,
        "provider_publication_certified": False,
        "fill_certified": False,
    }
