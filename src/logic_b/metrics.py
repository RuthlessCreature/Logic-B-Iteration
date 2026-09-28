from __future__ import annotations
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    s=pd.to_numeric(equity,errors="coerce").dropna()
    if s.empty: return float("nan")
    return float((s/s.cummax()-1.0).min())


def summarize_equity(daily_equity: pd.DataFrame, trades: pd.DataFrame|None=None) -> dict[str,float]:
    if daily_equity.empty: return {}
    x=daily_equity.sort_values("date").copy()
    eq=pd.to_numeric(x["equity"],errors="coerce").dropna()
    if len(eq)<2: return {"total_return":0.0,"max_drawdown":0.0}
    total=float(eq.iloc[-1]/eq.iloc[0]-1.0)
    days=max((pd.to_datetime(x["date"].iloc[-1])-pd.to_datetime(x["date"].iloc[0])).days,1)
    years=days/365.25
    cagr=float((eq.iloc[-1]/eq.iloc[0])**(1/years)-1)
    mdd=max_drawdown(eq)
    out={"total_return":total,"cagr":cagr,"max_drawdown":mdd,"calmar":cagr/abs(mdd) if mdd<0 else float("inf")}
    if trades is not None and not trades.empty and "return" in trades.columns:
        r=pd.to_numeric(trades["return"],errors="coerce").dropna(); wins=r[r>0]; losses=r[r<0]
        out.update({"trades":float(len(r)),"win_rate":float((r>0).mean()),"expectancy":float(r.mean()),"median_trade_return":float(r.median()),"profit_factor":float(wins.sum()/abs(losses.sum())) if losses.sum()<0 else float("inf")})
    return out
