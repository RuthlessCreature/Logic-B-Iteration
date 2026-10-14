from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("h02_final_strategy_research", SCRIPTS / "h02_final_strategy_research.py")
assert SPEC and SPEC.loader
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def _pool(n_sessions=5, per_day=6):
    rows = []
    for day in range(n_sessions):
        for i in range(per_day):
            rows.append({"outcome_date": f"202601{day+1:02}", "ts_code": f"S{i:03}",
                "continuation_D": i % 2, "down_next_D": (i + day) % 4 == 0,
                "down_three_D_to_D2": (i + day) % 3 == 0, "phase": "forward_2026H1",
                "p_continuation": i/10, "p_down_next": i/20, "p_down_three": i/15,
                "risk_score": i/20, "disagreement_down3": i/50,
                "vendor_streak_length": i % 4 + 1, "vendor_limit_up_count": 90,
                "lagged_continuation_change_3_sessions": 0.02,
                "vendor_streak_group": "1", "limit_up_count_5_group": "1", "breadth_group": "HIGH",
                "market_transition_group": "HIGH_TO_HIGH", "days_since_limit_down_group": ">5_OR_NEVER",
                "theme_hhi_group": "LOW", "streak_down5_group": "1|0"})
    return pd.DataFrame(rows)


def test_all_capped_rules_respect_three_per_session_and_have_full_calendar_ci():
    pool = _pool()
    thresholds = {"down3_probability_q75": .8, "down3_model_disagreement_range_q80": .8,
                  "market_breadth_q25": 70, "lagged_continuation_change_q25": -.02}
    selected = POLICY._select(pool, thresholds)
    for name, rows in selected.items():
        if name != "A_full_pool_reference":
            assert rows.groupby("outcome_date").size().max() <= 3
        stats = POLICY._rate_ci(rows, "down_three_D_to_D2", sorted(pool.outcome_date.unique()), reps=100)
        assert stats["n"] == len(rows)
        assert stats["ci_95"][0] <= stats["rate"] <= stats["ci_95"][1]


def test_train_rule_thresholds_are_provenanced_as_oof_only():
    frame = pd.DataFrame({"outcome_date": [f"2025{i:04}" for i in range(100)],
        "p_down_three": np.arange(100)/100,
        "disagreement_down3": np.arange(100)/100, "vendor_limit_up_count": np.arange(100),
        "lagged_continuation_change_3_sessions": np.arange(100)/100})
    thresholds = POLICY._fit_thresholds(frame)
    assert "train dates only" in thresholds["source"]
    assert np.isclose(thresholds["down3_probability_q75"], .7425)
    assert thresholds["selection_limit"]["final_candidate_max_per_session"] == 1


def test_full_pool_final_reference_uses_risk_score_rank_and_one_name():
    rows = pd.DataFrame({"outcome_date": ["d1", "d1", "d2", "d2"],
        "ts_code": ["A", "B", "A", "B"], "risk_score": [0.1, 0.9, 0.8, 0.2]})
    final = POLICY._final_candidates("A_full_pool_reference", rows)
    assert final.ts_code.tolist() == ["B", "A"]
    assert final.groupby("outcome_date").size().max() == 1
