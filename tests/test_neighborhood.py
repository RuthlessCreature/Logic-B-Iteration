from types import SimpleNamespace

from logic_b.neighborhood import (
    build_threshold_neighborhood,
    evaluate_threshold_neighborhood,
    summarize_threshold_neighborhood,
)


def test_fixed_threshold_neighborhood_has_exactly_eight_points():
    points=build_threshold_neighborhood(
        base_confirmation=0.58,
        base_tradability=0.45,
        confirmation_step=0.03,
        tradability_step=0.05,
    )

    assert len(points)==8
    pairs={
        (
            point.min_confirmation,
            point.min_tradability,
        )
        for point in points
    }
    assert (0.58,0.45) not in pairs
    assert (0.55,0.40) in pairs
    assert (0.61,0.50) in pairs


def test_neighborhood_summary_requires_broad_positive_behavior():
    rows=[
        {
            "expectancy":0.01,
            "total_return":0.05,
            "max_drawdown":-0.12,
            "closed_trades":30,
        }
        for _ in range(8)
    ]
    summary=summarize_threshold_neighborhood(
        rows,
    )

    assert summary["stable"]
    assert summary["tested_neighbors"]==8
    assert summary["positive_expectancy_rate"]==1.0


def test_non_finite_or_thin_neighbor_makes_neighborhood_unstable():
    rows=[
        {
            "expectancy":0.01,
            "total_return":0.05,
            "max_drawdown":-0.12,
            "closed_trades":30,
        }
        for _ in range(8)
    ]
    rows[0]["expectancy"]=None
    rows[1]["closed_trades"]=4

    summary=summarize_threshold_neighborhood(
        rows,
    )

    assert not summary["stable"]
    assert not summary["conditions"]["all_expectancy_finite"]
    assert not summary["conditions"]["minimum_trade_count"]


class FakeRunner:
    def __init__(self,point):
        self.point=point

    def run(self,trade_dates):
        assert trade_dates==[
            "20260924",
            "20260925",
            "20260928",
        ]
        return SimpleNamespace(
            metrics={
                "total_return":0.04,
                "cagr":0.10,
                "max_drawdown":-0.10,
                "expectancy":0.01,
                "win_rate":0.55,
                "closed_trades":25,
                "signals":5,
            }
        )


def test_evaluator_records_all_neighbors_without_best_pick():
    points=build_threshold_neighborhood(
        base_confirmation=0.58,
        base_tradability=0.45,
    )
    rows,summary=evaluate_threshold_neighborhood(
        trade_dates=[
            "20260924",
            "20260925",
            "20260928",
        ],
        runner_factory=FakeRunner,
        points=points,
    )

    assert len(rows)==8
    assert summary["tested_neighbors"]==8
    assert summary["stable"]
    assert "best_neighbor" not in summary
