import pandas as pd

from logic_b.replay.runner import ReplayResult
from logic_b.walkforward import (
    build_expanding_folds,
    evaluate_walk_forward,
)


def dates(n=240):
    return (
        pd.bdate_range(
            "2025-01-02",
            periods=n,
        )
        .strftime("%Y%m%d")
        .tolist()
    )


def test_expanding_folds_are_chronological_and_no_shuffle():
    folds=build_expanding_folds(
        dates(),
        min_train_days=120,
        validation_days=40,
        step_days=40,
        warmup_days=2,
    )

    assert len(folds)==3
    assert folds[0].train_start=="20250102"
    assert folds[0].train_end<folds[0].validation_start
    assert folds[1].train_end<folds[1].validation_start
    assert folds[0].validation_end<folds[1].validation_start
    assert len(folds[0].warmup_dates)==2


class FakeRunner:
    def __init__(self,initial_cash=100000):
        self.initial_cash=initial_cash

    def run(self,replay_dates):
        rows=[]
        equity=self.initial_cash
        for i,day in enumerate(replay_dates):
            equity*=1.001
            rows.append({
                "date":day,
                "equity":equity,
                "holding":"A" if i%2 else None,
            })

        final=pd.to_datetime(
            replay_dates[-1]
        )
        trades=[{
            "ts_code":"A",
            "entry_time":
                final-pd.Timedelta(days=1),
            "exit_time":final,
            "net_return":0.01,
        }]
        return ReplayResult(
            signals=[],
            fills=[],
            trades=trades,
            daily_equity=rows,
            metrics={},
        )


def test_walk_forward_evaluation_summarizes_fold_stability():
    metrics,summary=evaluate_walk_forward(
        trade_dates=dates(),
        runner_factory=lambda:FakeRunner(),
        initial_cash=100000,
        min_train_days=120,
        validation_days=40,
        step_days=40,
        warmup_days=2,
    )

    assert len(metrics)==3
    assert summary["folds"]==3
    assert summary["positive_return_fold_rate"]==1.0
    assert summary["positive_expectancy_fold_rate"]==1.0
    assert summary["closed_trades"]==3
