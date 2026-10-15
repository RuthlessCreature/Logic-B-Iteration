from __future__ import annotations

from dataclasses import asdict,dataclass
from typing import Callable

import pandas as pd

from .replay.runner import ReplayResult


@dataclass(frozen=True)
class ThresholdPoint:
    min_confirmation: float
    min_tradability: float

    def as_dict(self) -> dict:
        return asdict(self)


def build_threshold_neighborhood(
    *,
    base_confirmation: float,
    base_tradability: float,
    confirmation_step: float=0.03,
    tradability_step: float=0.05,
) -> list[ThresholdPoint]:
    """Return the fixed 3x3-minus-center local threshold neighborhood."""
    if confirmation_step<=0 or tradability_step<=0:
        raise ValueError(
            "neighborhood steps must be positive"
        )

    points=[]
    for dc in (-1,0,1):
        for dt in (-1,0,1):
            if dc==0 and dt==0:
                continue
            confirmation=(
                base_confirmation
                +dc*confirmation_step
            )
            tradability=(
                base_tradability
                +dt*tradability_step
            )
            if not (
                0<=confirmation<=1
                and 0<=tradability<=1
            ):
                raise ValueError(
                    "threshold neighborhood leaves [0,1]"
                )
            points.append(
                ThresholdPoint(
                    min_confirmation=
                        round(
                            confirmation,
                            10,
                        ),
                    min_tradability=
                        round(
                            tradability,
                            10,
                        ),
                )
            )

    if len(points)!=8:
        raise RuntimeError(
            "expected exactly 8 threshold neighbors"
        )
    return points


def summarize_threshold_neighborhood(
    rows: list[dict],
    *,
    min_positive_expectancy_rate: float=0.75,
    min_positive_total_return_rate: float=0.75,
    max_neighbor_drawdown_abs: float=0.30,
    min_closed_trades_each: int=20,
) -> dict:
    if not rows:
        return {
            "stable":False,
            "tested_neighbors":0,
            "reason":"no neighborhood results",
        }

    frame=pd.DataFrame(rows)
    expectancy=pd.to_numeric(
        frame.get("expectancy"),
        errors="coerce",
    )
    total_return=pd.to_numeric(
        frame.get("total_return"),
        errors="coerce",
    )
    drawdown=pd.to_numeric(
        frame.get("max_drawdown"),
        errors="coerce",
    )
    trades=pd.to_numeric(
        frame.get("closed_trades"),
        errors="coerce",
    )

    valid_expectancy=expectancy.notna()
    positive_expectancy_rate=(
        float(
            (
                expectancy[
                    valid_expectancy
                ]>0
            ).mean()
        )
        if valid_expectancy.any()
        else 0.0
    )
    valid_return=total_return.notna()
    positive_total_return_rate=(
        float(
            (
                total_return[
                    valid_return
                ]>0
            ).mean()
        )
        if valid_return.any()
        else 0.0
    )

    worst_drawdown_abs=(
        float(drawdown.abs().max())
        if drawdown.notna().any()
        else float("nan")
    )
    minimum_closed_trades=(
        int(trades.min())
        if trades.notna().any()
        else 0
    )

    conditions={
        "all_expectancy_finite":
            bool(valid_expectancy.all()),
        "all_total_return_finite":
            bool(valid_return.all()),
        "all_drawdown_finite":
            bool(drawdown.notna().all()),
        "positive_expectancy_rate":
            positive_expectancy_rate
            >=min_positive_expectancy_rate,
        "positive_total_return_rate":
            positive_total_return_rate
            >=min_positive_total_return_rate,
        "drawdown_limit":
            (
                pd.notna(
                    worst_drawdown_abs
                )
                and worst_drawdown_abs
                <=max_neighbor_drawdown_abs
            ),
        "minimum_trade_count":
            minimum_closed_trades
            >=min_closed_trades_each,
    }

    stable=all(
        conditions.values()
    )

    return {
        "stable":bool(stable),
        "tested_neighbors":int(len(frame)),
        "positive_expectancy_rate":
            positive_expectancy_rate,
        "positive_total_return_rate":
            positive_total_return_rate,
        "worst_drawdown_abs":
            worst_drawdown_abs,
        "minimum_closed_trades":
            minimum_closed_trades,
        "thresholds":{
            "min_positive_expectancy_rate":
                min_positive_expectancy_rate,
            "min_positive_total_return_rate":
                min_positive_total_return_rate,
            "max_neighbor_drawdown_abs":
                max_neighbor_drawdown_abs,
            "min_closed_trades_each":
                min_closed_trades_each,
        },
        "conditions":conditions,
    }


def evaluate_threshold_neighborhood(
    *,
    trade_dates: list[str],
    runner_factory: Callable[
        [ThresholdPoint],
        object,
    ],
    points: list[ThresholdPoint],
    min_positive_expectancy_rate: float=0.75,
    min_positive_total_return_rate: float=0.75,
    max_neighbor_drawdown_abs: float=0.30,
    min_closed_trades_each: int=20,
) -> tuple[list[dict],dict]:
    """Replay each fixed neighbor; never choose or return a best parameter."""
    rows=[]

    for index,point in enumerate(points):
        runner=runner_factory(
            point
        )
        result: ReplayResult=runner.run(
            trade_dates
        )
        metrics=result.metrics

        rows.append({
            "neighbor":index,
            "min_confirmation":
                point.min_confirmation,
            "min_tradability":
                point.min_tradability,
            "total_return":
                metrics.get(
                    "total_return"
                ),
            "cagr":
                metrics.get("cagr"),
            "max_drawdown":
                metrics.get(
                    "max_drawdown"
                ),
            "expectancy":
                metrics.get(
                    "expectancy"
                ),
            "win_rate":
                metrics.get(
                    "win_rate"
                ),
            "closed_trades":
                metrics.get(
                    "closed_trades",
                    metrics.get(
                        "trades",
                        0,
                    ),
                ),
            "signals":
                metrics.get(
                    "signals"
                ),
        })

    summary=summarize_threshold_neighborhood(
        rows,
        min_positive_expectancy_rate=
            min_positive_expectancy_rate,
        min_positive_total_return_rate=
            min_positive_total_return_rate,
        max_neighbor_drawdown_abs=
            max_neighbor_drawdown_abs,
        min_closed_trades_each=
            min_closed_trades_each,
    )
    return rows,summary
