"""Independent Baostock historical daily-state normalization for H02 research.

Not a 09:35 certified event stream. Never substitute end-of-day daily
OHLC or an inferred price band for intraday decision/fill evidence.
"""
from __future__ import annotations

import math
import pandas as pd

class H02IndependentDataInvalid(ValueError):
    pass


def normalize_baostock_daily(row: dict) -> dict:
    """Validate one unadjusted historical daily observation.

    BaoStock daily K history includes ST and trade status, but it does NOT
    provide official per-stock up/down limits or their intraday publication.
    """
    required={"date","code","adjustflag","tradestatus","isST","preclose",
              "open","high","low","close","volume","amount"}
    if required-set(row):
        raise H02IndependentDataInvalid(f"missing fields: {sorted(required-set(row))}")
    day=str(row["date"])
    dt=pd.to_datetime(day,errors="coerce")
    if pd.isna(dt) or dt.strftime("%Y-%m-%d")!=day:
        raise H02IndependentDataInvalid("invalid historical trading date")
    code=str(row["code"]).lower()
    if len(code)!=9 or code[2]!="." or code[:2] not in ("sh","sz") or not code[3:].isdigit():
        raise H02IndependentDataInvalid("invalid BaoStock security code")
    if str(row["adjustflag"])!="3":
        raise H02IndependentDataInvalid("unadjusted prices required: adjustflag=3")
    if str(row["isST"]) not in ("0","1") or str(row["tradestatus"]) not in ("0","1"):
        raise H02IndependentDataInvalid("unknown ST or trade state; fail closed")
    tradeable=str(row["tradestatus"])=="1"
    def numeric(name):
        try: val=float(row[name])
        except (TypeError,ValueError): val=float("nan")
        return val
    prices={name:numeric(name) for name in ("preclose","open","high","low","close")}
    if tradeable and (not all(math.isfinite(v) and v>0 for v in prices.values()) or
                      prices["high"]+1e-7<max(prices["open"],prices["close"],prices["low"]) or
                      prices["low"]-1e-7>min(prices["open"],prices["close"],prices["high"])):
        raise H02IndependentDataInvalid("invalid historical unadjusted daily OHLC")
    return {
        "trade_date":dt.strftime("%Y%m%d"),
        "ts_code":code[3:].upper()+("."+"SH" if code[:2]=="sh" else ".SZ"),
        "is_st":str(row["isST"])=="1",
        "is_trading":tradeable,
        **prices,
        "volume_shares":numeric("volume"), "turnover_cny":numeric("amount"),
        "source":"baostock_historical_daily_unadjusted",
        "intraday_publication_audited":False,
        "official_limit_prices_provided":False,
    }


def compare_daily_to_historical_minutes(day: dict, bars: pd.DataFrame, *,
                                        close_tol: float=0.011) -> dict:
    """End-of-day cross-provider check only, explicitly not 09:35 feature."""
    if not day["is_trading"] or bars.empty:
        return {"status":"UNVERIFIED_NONTRADING_OR_EMPTY"}
    cols={"trade_time","open","high","low","close"}
    if cols-set(bars):
        return {"status":"BLOCKED_MISSING_BAR_FIELDS"}
    times=pd.to_datetime(bars["trade_time"],errors="coerce")
    if times.isna().any() or not times.is_unique or (times.dt.strftime("%Y%m%d")!=day["trade_date"]).any():
        return {"status":"BLOCKED_TIME_INCONSISTENCY"}
    close_diff=abs(float(bars.iloc[-1]["close"])-day["close"])
    high_diff=abs(float(bars.high.max())-day["high"])
    low_diff=abs(float(bars.low.min())-day["low"])
    open_diff=abs(float(bars.iloc[0]["open"])-day["open"])
    exact_tick=all(q<=close_tol for q in [close_diff,high_diff,low_diff,open_diff])
    return {
        "status":"MATCH_TICK_TOLERANCE" if exact_tick else "REVIEW_DAILY_MINUTE_MISMATCH",
        "open_abs_diff":open_diff, "high_abs_diff":high_diff,
        "low_abs_diff":low_diff, "close_abs_diff":close_diff,
        "minute_bars":len(bars),"proves_entry_fill":False,
        "st_filter_needed":bool(day["is_st"]),
    }
