from __future__ import annotations

import importlib.util
from pathlib import Path

PATH = Path(__file__).parents[1] / "scripts" / "h02_final_stock_features.py"
SPEC = importlib.util.spec_from_file_location("h02_final_stock_features_bootstrap", PATH)
assert SPEC and SPEC.loader
FEATURES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FEATURES)


def test_subgroup_bootstrap_retains_zero_candidate_sessions():
    rows = [
        {"outcome_date": "d1", "y": 1, "g": "A"},
        {"outcome_date": "d3", "y": 0, "g": "A"},
        {"outcome_date": "d5", "y": 1, "g": "A"},
    ]
    draws = FEATURES._block_bootstrap_rate(rows, "y", reps=100,
        calendar_days=[f"d{i}" for i in range(1, 8)])
    compressed = FEATURES._block_bootstrap_rate(rows, "y", reps=100)
    assert len(draws) == len(compressed) == 100
    # The fixed seed plus three explicit zero sessions changes sampled blocks.
    assert draws != compressed


def test_conditional_table_passes_calendar_through_to_group_bootstrap():
    rows = [{"outcome_date": "d1", "y": 1, "g": "A"},
            {"outcome_date": "d3", "y": 0, "g": "A"}]
    table = FEATURES._conditional_table(rows, "y", {"g": ("g", ("A", "B"))},
        calendar_days=[f"d{i}" for i in range(1, 8)])
    assert table["g"]["groups"][0]["day_block_bootstrap_95pct_ci"] is not None
    assert table["g"]["groups"][1]["events"] == 0
    assert table["g"]["groups"][1]["candidate_days"] == 0
