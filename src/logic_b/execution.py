from __future__ import annotations

from datetime import datetime
import pandas as pd

from .models import Fill, FillModel


def _prep(minute_bars: pd.DataFrame, signal_time: datetime) -> pd.DataFrame:
    """Only bars strictly after signal_time may be used for execution.

    A checkpoint built from the bar ending at 09:35 cannot also claim a fill
    inside that same 09:35 bar.
    """
    bars=minute_bars.copy()
    bars["trade_time"]=pd.to_datetime(bars["trade_time"])
    return bars[bars["trade_time"] > signal_time].sort_values("trade_time")


def _volume(bars: pd.DataFrame) -> pd.Series:
    if "vol" not in bars.columns:
        return pd.Series(0.0,index=bars.index,dtype=float)
    return pd.to_numeric(bars["vol"],errors="coerce").fillna(0.0)


def simulate_buy_fill(
    *, ts_code: str, signal_time: datetime, minute_bars: pd.DataFrame,
    limit_up_price: float, model: FillModel
) -> Fill:
    if minute_bars.empty:
        return Fill(ts_code,"BUY",signal_time,None,None,False,"no_minute_data",model)
    bars=_prep(minute_bars,signal_time)
    if bars.empty:
        return Fill(ts_code,"BUY",signal_time,None,None,False,"no_bar_after_signal",model)

    eps=max(0.001,limit_up_price*1e-5)
    bars["sealed"]=(bars["low"]>=limit_up_price-eps)&(bars["high"]>=limit_up_price-eps)
    bars["vol"]=_volume(bars)

    if model==FillModel.OPTIMISTIC:
        r=bars.iloc[0]
        return Fill(ts_code,"BUY",signal_time,r["trade_time"],float(min(r["open"],limit_up_price)),True,"optimistic_first_post_signal_bar",model)

    openable=bars[(~bars["sealed"])&(bars["vol"]>0)]
    if openable.empty:
        return Fill(ts_code,"BUY",signal_time,None,None,False,"sealed_limit_no_open",model)

    if model==FillModel.REALISTIC:
        r=openable.iloc[0]
        px=float(min(max(r["open"],r["low"]),limit_up_price))
        return Fill(ts_code,"BUY",signal_time,r["trade_time"],px,True,"first_openable_post_signal_bar",model)

    flags=(~bars["sealed"])&(bars["vol"]>0)
    eligible=bars[flags & flags.shift(1,fill_value=False)]
    if eligible.empty:
        return Fill(ts_code,"BUY",signal_time,None,None,False,"no_two_consecutive_openable_bars",model)
    r=eligible.iloc[0]
    px=float(min(max(r["open"],r["low"]),limit_up_price))
    return Fill(ts_code,"BUY",signal_time,r["trade_time"],px,True,"two_bar_confirmation",model)


def simulate_sell_fill(
    *, ts_code: str, signal_time: datetime, minute_bars: pd.DataFrame,
    limit_down_price: float, model: FillModel
) -> Fill:
    if minute_bars.empty:
        return Fill(ts_code,"SELL",signal_time,None,None,False,"no_minute_data",model)
    bars=_prep(minute_bars,signal_time)
    if bars.empty:
        return Fill(ts_code,"SELL",signal_time,None,None,False,"no_bar_after_signal",model)

    eps=max(0.001,limit_down_price*1e-5)
    bars["locked"]=(bars["high"]<=limit_down_price+eps)&(bars["low"]<=limit_down_price+eps)
    bars["vol"]=_volume(bars)

    if model==FillModel.OPTIMISTIC:
        r=bars.iloc[0]
        return Fill(ts_code,"SELL",signal_time,r["trade_time"],float(max(r["open"],limit_down_price)),True,"optimistic_first_post_signal_bar",model)

    openable=bars[(~bars["locked"])&(bars["vol"]>0)]
    if openable.empty:
        return Fill(ts_code,"SELL",signal_time,None,None,False,"locked_limit_down",model)

    if model==FillModel.REALISTIC:
        r=openable.iloc[0]
        return Fill(ts_code,"SELL",signal_time,r["trade_time"],float(max(r["open"],limit_down_price)),True,"first_openable_post_signal_bar",model)

    flags=(~bars["locked"])&(bars["vol"]>0)
    eligible=bars[flags & flags.shift(1,fill_value=False)]
    if eligible.empty:
        return Fill(ts_code,"SELL",signal_time,None,None,False,"no_two_consecutive_openable_bars",model)
    r=eligible.iloc[0]
    return Fill(ts_code,"SELL",signal_time,r["trade_time"],float(max(r["open"],limit_down_price)),True,"two_bar_confirmation",model)
