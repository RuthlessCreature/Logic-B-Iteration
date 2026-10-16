from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .metrics import summarize_equity
from .replay.runner import ReplayResult


@dataclass(frozen=True)
class WalkForwardFold:
    index: int
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    warmup_dates: tuple[str,...]
    validation_dates: tuple[str,...]

    @property
    def replay_dates(self) -> list[str]:
        return [
            *self.warmup_dates,
            *self.validation_dates,
        ]


def build_expanding_folds(
    trade_dates: list[str],
    *,
    min_train_days: int=120,
    validation_days: int=40,
    step_days: int=40,
    warmup_days: int=2,
) -> list[WalkForwardFold]:
    """Build chronological expanding-window validation folds.

    No random shuffle is permitted. Warmup dates are immediately before the
    validation window and exist only to build D-1/D-2 point-in-time state.
    """
    dates=sorted(
        pd.to_datetime(trade_dates)
        .strftime("%Y%m%d")
        .tolist()
    )

    for name,value in (
        ("min_train_days",min_train_days),
        ("validation_days",validation_days),
        ("step_days",step_days),
        ("warmup_days",warmup_days),
    ):
        if value<1:
            raise ValueError(
                f"{name} must be >= 1"
            )

    if min_train_days<warmup_days:
        raise ValueError(
            "min_train_days must be >= warmup_days"
        )

    folds=[]
    validation_start_index=min_train_days
    fold_index=0

    while (
        validation_start_index
        +validation_days
        <=len(dates)
    ):
        validation_end_index=(
            validation_start_index
            +validation_days
        )
        warmup_start=max(
            0,
            validation_start_index
            -warmup_days,
        )

        folds.append(
            WalkForwardFold(
                index=fold_index,
                train_start=dates[0],
                train_end=dates[
                    validation_start_index-1
                ],
                validation_start=dates[
                    validation_start_index
                ],
                validation_end=dates[
                    validation_end_index-1
                ],
                warmup_dates=tuple(
                    dates[
                        warmup_start:
                        validation_start_index
                    ]
                ),
                validation_dates=tuple(
                    dates[
                        validation_start_index:
                        validation_end_index
                    ]
                ),
            )
        )

        fold_index+=1
        validation_start_index+=step_days

    return folds


def validation_fold_metrics(
    result: ReplayResult,
    fold: WalkForwardFold,
    *,
    initial_cash: float,
) -> dict[str,float | str | int | None]:
    """Measure only the validation window.

    Warmup sessions establish state but their P&L is excluded. Validation is
    anchored to the actual portfolio equity at the end of the last warmup
    session. Trade expectancy uses only trades fully contained in validation.
    """
    validation_set=set(fold.validation_dates)
    warmup_set=set(fold.warmup_dates)

    all_equity=pd.DataFrame(result.daily_equity)
    if all_equity.empty:
        raise ValueError("replay returned no equity rows")

    all_equity["date"]=pd.to_datetime(all_equity["date"])
    all_equity["date_key"]=all_equity["date"].dt.strftime("%Y%m%d")

    validation_equity=all_equity[
        all_equity["date_key"].isin(validation_set)
    ].copy()
    if validation_equity.empty:
        raise ValueError("replay returned no validation equity rows")

    warmup_equity=all_equity[
        all_equity["date_key"].isin(warmup_set)
    ].sort_values("date")

    if warmup_equity.empty:
        baseline_date=validation_equity["date"].min()-pd.Timedelta(days=1)
        baseline_equity=float(initial_cash)
    else:
        baseline_row=warmup_equity.iloc[-1]
        baseline_date=pd.Timestamp(baseline_row["date"])
        baseline_equity=float(baseline_row["equity"])

    metric_equity=pd.concat(
        [
            pd.DataFrame([{
                "date":baseline_date,
                "equity":baseline_equity,
            }]),
            validation_equity[["date","equity"]],
        ],
        ignore_index=True,
    )

    trades=pd.DataFrame(result.trades)
    if not trades.empty:
        trades["entry_date_key"]=pd.to_datetime(
            trades["entry_time"]
        ).dt.strftime("%Y%m%d")
        trades["exit_date_key"]=pd.to_datetime(
            trades["exit_time"]
        ).dt.strftime("%Y%m%d")
        trades=trades[
            trades["entry_date_key"].isin(validation_set)
            &trades["exit_date_key"].isin(validation_set)
        ].copy()
        trades=trades.rename(columns={"net_return":"return"})

    metrics=summarize_equity(metric_equity,trades)
    metrics.update({
        "fold":fold.index,
        "train_start":fold.train_start,
        "train_end":fold.train_end,
        "validation_start":fold.validation_start,
        "validation_end":fold.validation_end,
        "validation_trade_days":len(fold.validation_dates),
        "validation_baseline_equity":baseline_equity,
        "complete_validation_trades":int(len(trades)),
        "exposure_rate":(
            float(validation_equity["holding"].notna().mean())
            if "holding" in validation_equity.columns
            else float("nan")
        ),
    })
    return metrics

def summarize_walk_forward(
    fold_metrics: list[dict],
) -> dict[str,float | int]:
    if not fold_metrics:
        return {
            "folds":0,
        }

    frame=pd.DataFrame(fold_metrics)

    def mean_bool(series: pd.Series) -> float:
        return float(
            series.fillna(False).mean()
        )

    total_return=pd.to_numeric(
        frame["total_return"],
        errors="coerce",
    )
    drawdown=pd.to_numeric(
        frame["max_drawdown"],
        errors="coerce",
    )

    out={
        "folds":int(len(frame)),
        "positive_return_fold_rate":
            float((total_return>0).mean()),
        "mean_total_return":
            float(total_return.mean()),
        "median_total_return":
            float(total_return.median()),
        "worst_total_return":
            float(total_return.min()),
        "best_total_return":
            float(total_return.max()),
        "median_max_drawdown":
            float(drawdown.median()),
        "worst_max_drawdown":
            float(drawdown.min()),
    }

    if "expectancy" in frame.columns:
        expectancy=pd.to_numeric(
            frame["expectancy"],
            errors="coerce",
        )
        valid=expectancy.dropna()
        out[
            "positive_expectancy_fold_rate"
        ]=(
            float((valid>0).mean())
            if not valid.empty
            else float("nan")
        )
        out["median_expectancy"]=(
            float(valid.median())
            if not valid.empty
            else float("nan")
        )

    if "trades" in frame.columns:
        out["closed_trades"]=int(
            pd.to_numeric(
                frame["trades"],
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )

    return out


def evaluate_walk_forward(
    *,
    trade_dates: list[str],
    runner_factory: Callable[[],object],
    initial_cash: float,
    min_train_days: int=120,
    validation_days: int=40,
    step_days: int=40,
    warmup_days: int=2,
) -> tuple[list[dict],dict]:
    folds=build_expanding_folds(
        trade_dates,
        min_train_days=min_train_days,
        validation_days=validation_days,
        step_days=step_days,
        warmup_days=warmup_days,
    )

    metrics=[]
    for fold in folds:
        runner=runner_factory()
        result=runner.run(
            fold.replay_dates
        )
        metrics.append(
            validation_fold_metrics(
                result,
                fold,
                initial_cash=initial_cash,
            )
        )

    return metrics,summarize_walk_forward(
        metrics
    )
