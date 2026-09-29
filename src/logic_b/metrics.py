from __future__ import annotations

import math
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    s=pd.to_numeric(
        equity,
        errors="coerce",
    ).dropna()
    if s.empty:
        return float("nan")
    return float(
        (s/s.cummax()-1.0).min()
    )


def max_consecutive_losses(
    returns: pd.Series,
) -> int:
    r=pd.to_numeric(
        returns,
        errors="coerce",
    ).dropna()
    longest=0
    current=0
    for value in r:
        if value<0:
            current+=1
            longest=max(
                longest,
                current,
            )
        else:
            current=0
    return int(longest)


def monthly_equity_returns(
    daily_equity: pd.DataFrame,
) -> pd.Series:
    if (
        daily_equity.empty
        or "date" not in daily_equity.columns
        or "equity" not in daily_equity.columns
    ):
        return pd.Series(
            dtype=float
        )

    x=daily_equity.copy()
    x["date"]=pd.to_datetime(
        x["date"],
        errors="coerce",
    )
    x["equity"]=pd.to_numeric(
        x["equity"],
        errors="coerce",
    )
    x=x.dropna(
        subset=["date","equity"]
    ).sort_values("date")
    if x.empty:
        return pd.Series(
            dtype=float
        )

    month_end=(
        x.set_index("date")["equity"]
        .resample("ME")
        .last()
    )

    # First month needs a start-of-period anchor from the first observed equity.
    anchors=pd.concat([
        pd.Series(
            [float(x.iloc[0]["equity"])],
            index=[
                x.iloc[0]["date"]
                -pd.Timedelta(
                    nanoseconds=1
                )
            ],
        ),
        month_end,
    ]).sort_index()

    returns=anchors.pct_change().dropna()
    returns.index=month_end.index[:len(returns)]
    return returns.astype(float)


def summarize_equity(
    daily_equity: pd.DataFrame,
    trades: pd.DataFrame | None=None,
) -> dict[str,float]:
    if daily_equity.empty:
        return {}

    x=daily_equity.sort_values(
        "date"
    ).copy()
    eq=pd.to_numeric(
        x["equity"],
        errors="coerce",
    ).dropna()
    if eq.empty:
        return {}

    exposure_rate=(
        float(
            x["holding"]
            .notna()
            .mean()
        )
        if "holding" in x.columns
        else float("nan")
    )
    suspended_exposure_rate=(
        float(
            x["holding_suspended"]
            .fillna(False)
            .astype(bool)
            .mean()
        )
        if "holding_suspended" in x.columns
        else float("nan")
    )

    if len(eq)<2:
        return {
            "total_return":0.0,
            "max_drawdown":0.0,
            "exposure_rate":exposure_rate,
            "suspended_exposure_rate":
                suspended_exposure_rate,
        }

    total=float(
        eq.iloc[-1]/eq.iloc[0]-1.0
    )
    first_date=pd.to_datetime(
        x["date"].iloc[0]
    )
    last_date=pd.to_datetime(
        x["date"].iloc[-1]
    )
    days=max(
        (last_date-first_date).days,
        1,
    )
    years=days/365.25
    cagr=float(
        (eq.iloc[-1]/eq.iloc[0])
        **(1/years)-1
    )
    mdd=max_drawdown(eq)

    out={
        "total_return":total,
        "cagr":cagr,
        "max_drawdown":mdd,
        "calmar":(
            cagr/abs(mdd)
            if mdd<0
            else float("inf")
        ),
        "exposure_rate":
            exposure_rate,
        "suspended_exposure_rate":
            suspended_exposure_rate,
    }

    monthly=monthly_equity_returns(
        x
    )
    if not monthly.empty:
        out.update({
            "months":float(
                len(monthly)
            ),
            "positive_month_rate":float(
                (monthly>0).mean()
            ),
            "worst_month_return":float(
                monthly.min()
            ),
            "best_month_return":float(
                monthly.max()
            ),
            "median_month_return":float(
                monthly.median()
            ),
        })

    if (
        trades is not None
        and not trades.empty
        and "return" in trades.columns
    ):
        r=pd.to_numeric(
            trades["return"],
            errors="coerce",
        ).dropna()
        wins=r[r>0]
        losses=r[r<0]
        average_win=(
            float(wins.mean())
            if not wins.empty
            else float("nan")
        )
        average_loss=(
            float(losses.mean())
            if not losses.empty
            else float("nan")
        )
        payoff_ratio=(
            average_win/abs(average_loss)
            if (
                not math.isnan(average_win)
                and not math.isnan(average_loss)
                and average_loss<0
            )
            else float("nan")
        )

        out.update({
            "trades":float(
                len(r)
            ),
            "win_rate":float(
                (r>0).mean()
            ),
            "expectancy":float(
                r.mean()
            ),
            "median_trade_return":float(
                r.median()
            ),
            "profit_factor":(
                float(
                    wins.sum()
                    /abs(losses.sum())
                )
                if losses.sum()<0
                else float("inf")
            ),
            "average_win":
                average_win,
            "average_loss":
                average_loss,
            "payoff_ratio":
                payoff_ratio,
            "max_consecutive_losses":
                float(
                    max_consecutive_losses(
                        r
                    )
                ),
        })

        cost_cols=[
            col
            for col in [
                "entry_cost",
                "exit_cost",
            ]
            if col in trades.columns
        ]
        if cost_cols:
            total_cost=0.0
            for col in cost_cols:
                total_cost+=float(
                    pd.to_numeric(
                        trades[col],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                )
            out["total_transaction_cost"]=total_cost

    return out
