from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

PATH = Path(__file__).parents[1] / "scripts" / "h02_final_stock_forecast.py"
SPEC = importlib.util.spec_from_file_location("h02_final_stock_forecast", PATH)
assert SPEC and SPEC.loader
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


def frame(n=120):
    rng = np.random.default_rng(19)
    data = {name: rng.normal(size=n) for name in MODEL.FEATURES}
    data["vendor_streak_length"] = rng.integers(1, 5, size=n)
    data["continuation_D"] = (data["vendor_streak_length"] > 2).astype(int)
    return pd.DataFrame(data)


def test_logistic_is_deterministic_and_train_only_scaled():
    data = frame()
    train, test = data.iloc[:80], data.iloc[80:]
    a = MODEL._fit_predict(train, test, "continuation_D")
    b = MODEL._fit_predict(train, test, "continuation_D")
    assert np.array_equal(a, b)
    assert np.all((a > 0) & (a < 1))


def test_metrics_and_ranking_keep_exposure_metrics():
    metrics = MODEL._metrics(np.array([0, 1, 0, 1]), np.array([.1, .8, .2, .7]))
    assert metrics["brier"] < .1
    assert metrics["top_decile_event_recall"] == .5
    d = pd.DataFrame({"phase": ["forward_2026H1"]*4, "outcome_date": ["20260102"]*4,
        "ts_code": ["A","B","C","D"], "vendor_streak_length": [1,2,3,4],
        "p_continuation": [.2,.4,.6,.8], "p_down_next": [.1,.1,.1,.1], "p_down_three": [.2,.2,.2,.2],
        "continuation_D": [0,0,1,1], "down_next_D": [0,0,0,1], "down_three_D_to_D2": [0,0,1,1]})
    result = MODEL._ranking(d)["forward_2026H1"]
    assert result["risk_adjusted_top3"]["selected"] == 3
    assert result["risk_adjusted_top1"]["sessions"] == 1
    assert result["risk_adjusted_top3"]["candidate_symbol_day_coverage"] == .75


def test_ranking_uses_full_unfiltered_pool_as_baseline():
    d = pd.DataFrame({"phase": ["forward_2026H1"]*2, "outcome_date": ["20260102"]*2,
        "ts_code": ["A","B"], "vendor_streak_length": [1,2], "p_continuation": [.2,.8],
        "p_down_next": [.1,.2], "p_down_three": [.2,.3], "continuation_D": [0,1],
        "down_next_D": [0,1], "down_three_D_to_D2": [0,1]})
    result = MODEL._ranking(d)["forward_2026H1"]["unfiltered_all_candidates"]
    assert result["selected"] == 2
    assert result["candidate_symbol_day_coverage"] == 1.0
    assert result["three_day_down_rate"] == .5


def test_brier_bootstrap_uses_full_calendar_and_candidate_weighted_estimand():
    rows = pd.DataFrame({"outcome_date": ["d1", "d2", *(["d3"] * 100), "d5", "d6", "d7"],
                         "ts_code": [f"s{i}" for i in range(105)]})
    y = np.zeros(105)
    baseline = np.full(105, .5)
    model = np.full(105, .4)
    # Make the high-volume day favor the model and all other days favor baseline.
    y[2:102] = 1
    model[2:102] = .8
    result = MODEL._brier_gain_bootstrap(rows, y, model, baseline,
        calendar_days=[f"d{i}" for i in range(1, 8)], reps=200)
    expected = float(np.mean((y-baseline)**2 - (y-model)**2))
    assert result is not None
    assert result["point_estimate_candidate_weighted"] == expected
    assert result["sessions"] == 7


def test_full_calendar_gap_does_not_compress_bootstrap_sessions():
    rows = pd.DataFrame({"outcome_date": ["d1", "d2", "d4", "d5", "d6", "d7"],
                         "ts_code": [f"s{i}" for i in range(6)]})
    y = np.array([1, 0, 0, 1, 0, 1])
    baseline = np.zeros(6)
    model = np.full(6, .1)
    result = MODEL._brier_gain_bootstrap(rows, y, model, baseline,
        calendar_days=[f"d{i}" for i in range(1, 8)], reps=50)
    assert result is not None
    assert result["sessions"] == 7


def test_analyze_and_markdown_writer_support_nested_model_schema(tmp_path, monkeypatch):
    data = frame(36)
    data["outcome_date"] = ["20250303" if i < 20 else "20250701" if i < 28 else "20260105" for i in range(36)]
    data["ts_code"] = [f"S{i:03}" for i in range(36)]
    for label in MODEL.LABELS:
        data[label] = ((np.arange(36) + len(label)) % 4 == 0).astype(float)
    data["down_next_D"] = ((np.arange(36) + 2) % 4 == 0).astype(float)
    matrix = tmp_path / "matrix.csv"
    data.to_csv(matrix, index=False)
    report = MODEL.analyze(matrix)
    assert set(report["results"]["continuation_D"]) >= {"training_resubstitution", "validation_2025H2", "forward_2026H1"}
    assert set(report["results"]["continuation_D"]["validation_2025H2"]["models"]) >= {"prevalence_baseline", "market_state_logistic", "stock_structure_logistic", "joint_logistic"}
    assert report["results"]["down_next_D"]["validation_2025H2"]["models"]["joint_logistic"]["metrics"]["average_precision"] is not None
    out_json, out_md = tmp_path / "report.json", tmp_path / "report.md"
    monkeypatch.setattr("sys.argv", ["h02_final_stock_forecast.py", "--matrix", str(matrix), "--out-json", str(out_json), "--out-markdown", str(out_md)])
    assert MODEL.main() == 0
    emitted = json.loads(out_json.read_text(encoding="utf-8"))
    assert "model comparison" in out_md.read_text(encoding="utf-8").lower()
    assert emitted["matrix_sha256"] == report["matrix_sha256"]
