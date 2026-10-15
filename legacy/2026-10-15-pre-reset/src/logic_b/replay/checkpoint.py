from __future__ import annotations

from datetime import datetime
import numpy as np
import pandas as pd


def _limits(limit_prices: pd.DataFrame) -> pd.DataFrame:
    required={"ts_code","pre_close","up_limit","down_limit"}
    missing=required-set(limit_prices.columns)
    if missing:
        raise ValueError(f"limit_prices missing columns: {sorted(missing)}")
    return limit_prices.set_index("ts_code",drop=False)


def _finalize(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[
            "ts_code","pct_from_prev_close","relative_to_peer_median",
            "checkpoint_amount","checkpoint_amount_rank","at_limit",
            "one_price_limit","opened_after_limit",
        ])
    out=pd.DataFrame(rows)
    med=float(out["pct_from_prev_close"].median())
    out["relative_to_peer_median"]=out["pct_from_prev_close"]-med
    out["checkpoint_amount_rank"]=out["checkpoint_amount"].rank(pct=True,method="average")
    return out


def build_auction_checkpoint(
    candidate_codes: list[str],
    auction_df: pd.DataFrame,
    limit_prices: pd.DataFrame,
) -> pd.DataFrame:
    """Build 09:25/09:30 opening-auction replay features.

    Historical auction data may be published by the vendor after close, but the
    matched auction result itself is market-observable by the open. The caller
    must keep vendor publication time separate from market event time.
    """
    if auction_df.empty:
        return _finalize([])
    lim=_limits(limit_prices)
    a=auction_df[auction_df["ts_code"].isin(candidate_codes)].copy()
    rows=[]
    for _,r in a.iterrows():
        code=str(r["ts_code"])
        if code not in lim.index:
            continue
        lr=lim.loc[code]
        pre=float(lr["pre_close"])
        up=float(lr["up_limit"])
        close=float(r["close"])
        high=float(r.get("high",close))
        low=float(r.get("low",close))
        amount=float(r.get("amount",0.0) or 0.0)
        eps=max(.001,up*1e-5)
        rows.append({
            "ts_code":code,
            "pct_from_prev_close":close/pre-1.0,
            "checkpoint_amount":amount,
            "at_limit":bool(close>=up-eps),
            "one_price_limit":bool(low>=up-eps and high>=up-eps),
            "opened_after_limit":False,
        })
    return _finalize(rows)


def build_minute_checkpoint(
    candidate_codes: list[str],
    minute_frames: dict[str,pd.DataFrame],
    limit_prices: pd.DataFrame,
    checkpoint: datetime,
) -> pd.DataFrame:
    """Build features using bars whose timestamps are <= checkpoint only."""
    lim=_limits(limit_prices)
    rows=[]
    for code in candidate_codes:
        if code not in minute_frames or code not in lim.index:
            continue
        bars=minute_frames[code].copy()
        if bars.empty or "trade_time" not in bars.columns:
            continue
        bars["trade_time"]=pd.to_datetime(bars["trade_time"])
        bars=bars[bars["trade_time"]<=checkpoint].sort_values("trade_time")
        if bars.empty:
            continue
        lr=lim.loc[code]
        pre=float(lr["pre_close"]); up=float(lr["up_limit"])
        last=bars.iloc[-1]
        close=float(last["close"])
        eps=max(.001,up*1e-5)
        amount=float(pd.to_numeric(bars["amount"],errors="coerce").fillna(0).sum()) if "amount" in bars.columns else 0.0
        touched=(pd.to_numeric(bars["high"],errors="coerce")>=up-eps)
        below_after_touch=False
        if touched.any():
            first_pos=int(np.flatnonzero(touched.to_numpy())[0])
            later=bars.iloc[first_pos:]
            below_after_touch=bool((pd.to_numeric(later["low"],errors="coerce")<up-eps).any())
        all_at_limit=bool(
            (pd.to_numeric(bars["low"],errors="coerce")>=up-eps).all()
            and (pd.to_numeric(bars["high"],errors="coerce")>=up-eps).all()
        )
        rows.append({
            "ts_code":code,
            "pct_from_prev_close":close/pre-1.0,
            "checkpoint_amount":amount,
            "at_limit":bool(close>=up-eps),
            "one_price_limit":all_at_limit,
            "opened_after_limit":below_after_touch,
        })
    return _finalize(rows)
