"""Fit frozen low-complexity event forecasts and evaluate research-only rankings."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

TRAIN_END = "20250630"
VALID_END = "20251231"
LABELS = ("continuation_D", "down_next_D", "down_three_D_to_D2")
MARKET_FEATURES = (
    "vendor_limit_up_count", "vendor_limit_down_count", "vendor_limit_break_count",
    "limit_up_pool_change_3_sessions", "limit_up_pool_change_5_sessions",
    "lagged_continuation_rate", "lagged_continuation_change_3_sessions",
    "rise_fall_event_ratio", "market_temperature", "market_theme_assignment_coverage", "theme_hhi",
)
STOCK_FEATURES = (
    "vendor_streak_length", "limit_up_count_3", "limit_up_count_5", "limit_down_count_5",
    "days_since_limit_down", "recent_limit_up_acceleration", "vendor_prior_nonconsecutive_entry", "market_relative_up5",
)
JOINT_FEATURES = MARKET_FEATURES + STOCK_FEATURES
FEATURES = JOINT_FEATURES


def _phase(day: str) -> str:
    return "train" if day <= TRAIN_END else "validation_2025H2" if day <= VALID_END else "forward_2026H1"


def _matrix(train: pd.DataFrame, frame: pd.DataFrame, feature_names: tuple[str, ...] = FEATURES) -> tuple[np.ndarray, list[str], dict[str, float], dict[str, float]]:
    medians: dict[str, float] = {}
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    train_x = []
    test_x = []
    names = []
    for name in feature_names:
        a = pd.to_numeric(train[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
        b = pd.to_numeric(frame[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
        med = float(a.median()) if a.notna().any() else 0.0
        av, bv = a.fillna(med).to_numpy(float), b.fillna(med).to_numpy(float)
        mu, sd = float(av.mean()), float(av.std())
        if not math.isfinite(sd) or sd < 1e-8:
            continue
        medians[name], means[name], scales[name] = med, mu, sd
        train_x.append((av - mu) / sd)
        test_x.append((bv - mu) / sd)
        names.append(name)
    return np.column_stack(test_x), names, {**medians, **{f"mean:{k}": v for k, v in means.items()}}, {f"scale:{k}": v for k, v in scales.items()}


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, label: str, feature_names: tuple[str, ...] = FEATURES) -> np.ndarray:
    x_train, names, _, _ = _matrix(train, train, feature_names)
    x_test, _, _, _ = _matrix(train, test, feature_names)
    y = train[label].to_numpy(float)
    prevalence = float(y.mean())
    if not names:
        return np.full(len(test), prevalence)
    # Deterministic L2 logistic regression, fixed penalty, no validation tuning.
    x = np.column_stack([np.ones(len(x_train)), x_train])
    z = np.column_stack([np.ones(len(x_test)), x_test])
    beta = np.zeros(x.shape[1], dtype=float)
    beta[0] = math.log(np.clip(prevalence, 1e-5, 1-1e-5) / (1 - np.clip(prevalence, 1e-5, 1-1e-5)))
    penalty = 1.0
    step = 0.15
    for _ in range(400):
        logits = np.clip(x @ beta, -30, 30)
        prob = 1 / (1 + np.exp(-logits))
        grad = (x.T @ (prob - y)) / len(y)
        grad[1:] += penalty * beta[1:] / len(y)
        beta -= step * grad
    return np.clip(1 / (1 + np.exp(-np.clip(z @ beta, -30, 30))), 1e-6, 1-1e-6)


def _metrics(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    p = np.clip(p, 1e-8, 1-1e-8)
    bins = []
    edges = np.linspace(0, 1, 11)
    for i in range(10):
        mask = (p >= edges[i]) & ((p < edges[i+1]) if i < 9 else (p <= edges[i+1]))
        if mask.any():
            bins.append({"lo": float(edges[i]), "hi": float(edges[i+1]), "n": int(mask.sum()), "mean_prediction": float(p[mask].mean()), "observed_rate": float(y[mask].mean())})
    k = max(1, int(math.ceil(len(y) * .1))) if len(y) else 0
    order = np.argsort(-p, kind="stable")[:k] if k else np.array([], dtype=int)
    sorted_y = y[np.argsort(-p, kind="stable")]
    cumulative_precision = np.cumsum(sorted_y) / np.arange(1, len(sorted_y)+1) if len(sorted_y) else np.array([])
    average_precision = float(np.sum(cumulative_precision * sorted_y) / y.sum()) if y.sum() else None
    ece = sum(b["n"] * abs(b["mean_prediction"]-b["observed_rate"]) for b in bins) / len(y) if len(y) else None
    calibration = _calibration_intercept_slope(y, p)
    return {"n": int(len(y)), "events": int(y.sum()), "prevalence": float(y.mean()) if len(y) else None,
            "brier": float(np.mean((p-y)**2)) if len(y) else None,
            "log_loss": float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))) if len(y) else None,
            "average_precision": average_precision,
            "expected_calibration_error_equal_width_10_bins": ece,
            "calibration_intercept_slope_descriptive": calibration,
            "top_decile_precision": float(y[order].mean()) if k else None,
            "top_decile_event_recall": float(y[order].sum()/y.sum()) if k and y.sum() else None,
            "calibration_bins": bins}


def _calibration_intercept_slope(y: np.ndarray, p: np.ndarray) -> dict[str, float | None]:
    """Descriptive logistic recalibration of evaluation outcomes on logit scores."""
    if len(y) == 0 or len(np.unique(y)) < 2:
        return {"intercept": None, "slope": None}
    x = np.column_stack([np.ones(len(p)), np.log(np.clip(p, 1e-8, 1-1e-8) / np.clip(1-p, 1e-8, 1))])
    beta = np.zeros(2, dtype=float)
    for _ in range(100):
        q = 1 / (1 + np.exp(-np.clip(x @ beta, -30, 30)))
        w = np.maximum(q * (1-q), 1e-9)
        hessian = x.T @ (w[:, None] * x) + np.eye(2) * 1e-8
        step = np.linalg.solve(hessian, x.T @ (np.asarray(y, dtype=float)-q))
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    if not np.all(np.isfinite(beta)):
        return {"intercept": None, "slope": None}
    return {"intercept": float(beta[0]), "slope": float(beta[1])}


def _moving_block_day_weights(day_count: int, reps: int, rng: np.random.Generator) -> np.ndarray:
    blocks = math.ceil(day_count/5)
    starts = rng.integers(0, day_count, size=(reps, blocks))
    sample = ((starts[:, :, None] + np.arange(5)[None, None, :]) % day_count).reshape(reps, -1)[:, :day_count]
    return np.stack([np.bincount(row, minlength=day_count) for row in sample])


def _brier_gain_bootstrap(rows: pd.DataFrame, y: np.ndarray, model: np.ndarray, baseline: np.ndarray, *, calendar_days: list[str] | tuple[str, ...] | None = None, reps: int = 1000) -> dict[str, Any] | None:
    """Candidate-weighted Brier gain, resampling contiguous 5-session blocks.

    Each replicate is sum(candidate-level Brier gains) / sum(candidate rows),
    matching the point estimate. Days with more candidate rows retain their
    candidate weight; the day is the dependence cluster.
    """
    if not len(rows):
        return None
    observed_days = rows.outcome_date.astype(str).to_numpy()
    day_values = list(calendar_days) if calendar_days is not None else sorted(set(observed_days))
    day_lookup = {day: i for i, day in enumerate(day_values)}
    if any(day not in day_lookup for day in observed_days):
        raise ValueError("calendar_days must include every observed outcome_date")
    day_index = np.asarray([day_lookup[d] for d in observed_days], dtype=int)
    daily_gain = np.bincount(day_index, weights=(y-baseline)**2-(y-model)**2, minlength=len(day_values))
    daily_n = np.bincount(day_index, minlength=len(day_values)).astype(float)
    if len(day_values) < 5:
        return None
    rng = np.random.default_rng(20261014)
    weights = _moving_block_day_weights(len(day_values), reps, rng)
    numerator = weights @ daily_gain
    denominator = weights @ daily_n
    gain_draws = numerator / denominator
    # Two-way cluster sensitivity: keep the moving time blocks and independently
    # resample security identities. This addresses persistent symbol repetition.
    codes, symbol_index = np.unique(rows.ts_code.astype(str).to_numpy(), return_inverse=True)
    obs_gain = (y-baseline)**2-(y-model)**2
    multiway = np.empty(reps, dtype=float)
    symbol_n = len(codes)
    for i in range(reps):
        symbol_weights = np.bincount(rng.integers(0, symbol_n, size=symbol_n), minlength=symbol_n)
        observation_weights = weights[i, day_index] * symbol_weights[symbol_index]
        denom = observation_weights.sum()
        multiway[i] = np.dot(observation_weights, obs_gain)/denom if denom else gain_draws[i]
    return {
        "method": "5-session circular moving-block bootstrap; candidate-weighted ratio per replicate",
        "replicates": reps,
        "day_block_candidate_weighted_95pct_ci": [float(np.quantile(gain_draws,.025)), float(np.quantile(gain_draws,.975))],
        "day_plus_symbol_cluster_sensitivity_95pct_ci": [float(np.quantile(multiway,.025)), float(np.quantile(multiway,.975))],
        "point_estimate_candidate_weighted": float(obs_gain.mean()),
        "sessions": int(len(day_values)),
        "unique_symbols": int(symbol_n),
    }


def _ranking(frame: pd.DataFrame) -> dict[str, Any]:
    f = frame.copy()
    f["risk_adjusted_score"] = f["p_continuation"] - .5*f["p_down_next"] - .5*f["p_down_three"]
    f["rule_streak"] = (f.vendor_streak_length >= 2).astype(int)
    output = {}
    for phase in ("validation_2025H2", "forward_2026H1"):
        part = f[f.phase == phase]
        output[phase] = {}
        for policy in ("unfiltered_all_candidates", "streak_2plus_top3", "risk_adjusted_top3", "risk_adjusted_top1"):
            selected = []
            if policy == "unfiltered_all_candidates":
                selected.extend(part.to_dict("records"))
                day_groups = []
            else:
                day_groups = part.groupby("outcome_date", sort=True)
            for _, day in day_groups:
                if policy.startswith("streak"):
                    day = day[day.rule_streak == 1]
                if policy.startswith("risk"):
                    day = day.sort_values(["risk_adjusted_score", "ts_code"], ascending=[False, True], kind="mergesort")
                else:
                    day = day.sort_values("ts_code", kind="mergesort")
                count = 1 if policy.endswith("top1") else 3
                selected.extend(day.head(count).to_dict("records"))
            if not selected:
                output[phase][policy] = {"selected": 0, "coverage": 0.0, "continuation_rate": None, "next_day_down_rate": None, "three_day_down_rate": None}
                continue
            out = pd.DataFrame(selected)
            output[phase][policy] = {"selected": len(out), "candidate_symbol_day_coverage": len(out)/len(part) if len(part) else None,
                "continuation_rate": float(out.continuation_D.mean()), "next_day_down_rate": float(out.down_next_D.mean()),
                "three_day_down_rate": float(out.down_three_D_to_D2.mean()) if out.down_three_D_to_D2.notna().any() else None,
                "sessions": int(out.outcome_date.nunique()), "scoring": "vendor-event research proxy; no return, cost, capacity, or fill meaning"}
    return output


def analyze(matrix: Path) -> dict[str, Any]:
    raw = matrix.read_bytes()
    df = pd.read_csv(matrix, dtype={"ts_code": str, "outcome_date": str})
    df["phase"] = df.outcome_date.map(_phase)
    model_sets = {"market_state_logistic": MARKET_FEATURES, "stock_structure_logistic": STOCK_FEATURES, "joint_logistic": JOINT_FEATURES}
    report: dict[str, Any] = {"classification": "TIER_D_EXPLORATORY_FORECAST_AND_RANKING_NOT_TRADING_PERFORMANCE",
        "matrix_sha256": hashlib.sha256(raw).hexdigest(), "matrix_rows": len(df), "features": list(FEATURES), "model_feature_sets": {k:list(v) for k,v in model_sets.items()},
        "training_end": TRAIN_END, "validation_end": VALID_END, "forward_end": "20260630",
        "model": "three fixed L2 logistic specifications, penalty 1.0, 400 gradient steps, no validation tuning; train-only median imputation/scaling",
        "protected_holdout_accessed": False, "results": {}, "ranking": {}}
    for label in LABELS:
        train = df[(df.phase == "train") & df[label].notna()]
        train_y = train[label].to_numpy(float)
        training_models = {"prevalence_baseline": {"metrics":_metrics(train_y,np.full(len(train),float(train[label].mean())))}}
        for model_name, feature_set in model_sets.items():
            training_models[model_name] = {"metrics":_metrics(train_y,_fit_predict(train,train,label,feature_set))}
        report["results"][label] = {"training_resubstitution": {"n":len(train), "events":int(train[label].sum()), "prevalence":float(train[label].mean()), "models":training_models, "warning":"apparent fit on training rows; not generalization evidence"}}
        for phase in ("validation_2025H2", "forward_2026H1"):
            test = df[(df.phase == phase) & df[label].notna()]
            if train.empty or test.empty:
                report["results"][label][phase] = {"error": "no eligible train or evaluation rows"}
                continue
            base = np.full(len(test), float(train[label].mean()))
            y = test[label].to_numpy(float)
            models = {"prevalence_baseline": {"metrics":_metrics(y,base), "train_n":len(train), "train_rate":float(train[label].mean())}}
            for model_name, feature_set in model_sets.items():
                pred = _fit_predict(train, test, label, feature_set)
                phase_days = sorted(df.loc[df.phase == phase, "outcome_date"].astype(str).unique().tolist())
                boot = _brier_gain_bootstrap(test, y, pred, base, calendar_days=phase_days)
                models[model_name] = {"metrics":_metrics(y,pred), "brier_gain_vs_prevalence_candidate_weighted":float(np.mean((y-base)**2)-np.mean((y-pred)**2)),
                    "brier_gain_bootstrap":boot}
            report["results"][label][phase] = {"train_n":len(train), "train_rate":float(train[label].mean()), "eligible_test_n":len(test), "models":models}
    # Train-only fitted probabilities for the descriptive candidate ranking.
    def eval_frame(phase: str) -> pd.DataFrame:
        target = df[(df.phase == phase) & df.continuation_D.notna()].copy()
        train_sets = {label: df[(df.phase == "train") & df[label].notna()] for label in LABELS}
        for label, column in zip(LABELS, ("p_continuation","p_down_next","p_down_three")):
            target[column] = _fit_predict(train_sets[label], target, label, JOINT_FEATURES)
        return target
    forward = eval_frame("forward_2026H1")
    validation = eval_frame("validation_2025H2")
    report["ranking"] = _ranking(forward)
    report["ranking"]["validation_2025H2"] = _ranking(validation).get("validation_2025H2", {})
    risk_top3 = report["ranking"].get("forward_2026H1", {}).get("risk_adjusted_top3", {})
    all_candidates = report["ranking"].get("forward_2026H1", {}).get("unfiltered_all_candidates", {})
    report["research_verdict"] = {
        "forecasting": "Model-family comparisons are descriptive evidence on vendor event-pool labels only; PIT availability and outcome-source semantics remain uncertified.",
        "candidate_ranking": "Candidate ranking is exploratory and does not establish a decision rule, lower downside incidence, returns, or positive expectancy.",
        "forward_risk_adjusted_top3_three_day_down_rate": risk_top3.get("three_day_down_rate"),
        "forward_unfiltered_three_day_down_rate": all_candidates.get("three_day_down_rate"),
        "tradeable_edge_established": False,
    }
    report["uncertainty_note"] = "Day-block bootstrap preserves candidate weighting for pooled Brier improvement and resamples contiguous five-session blocks. A day-plus-symbol two-way cluster sensitivity interval is also reported; 2025H2/2026H1 are exposed research periods, not independent holdouts."
    report["interpretation_guardrails"] = ["Targets are vendor event-pool membership, not official price-limit states.",
        "Predictions use D-1 fields, but historical publication-time/PIT availability is uncertified.",
        "The prior ranking uses a heuristic event probability score and top-1/top-3 limits; it does not establish net expectancy or executable edge.",
        "The 2026H1 period is exposed development data, not protected holdout."]
    return report


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--matrix",type=Path,required=True); p.add_argument("--out-json",type=Path,required=True); p.add_argument("--out-markdown",type=Path,required=True); a=p.parse_args()
    result=analyze(a.matrix); a.out_json.parent.mkdir(parents=True,exist_ok=True); a.out_json.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    lines=["# H02 forecast and candidate-risk ranking research","","**Tier D exploratory research. No actual returns, costs, fill evidence, or PIT certification.**","",f"Matrix SHA256: `{result['matrix_sha256']}`; rows: {result['matrix_rows']:,}.","","## Forecast model comparison","","| Target | Evaluation phase | Model | Brier | Log loss | AP | Brier gain vs prevalence | 95% candidate-weighted day-block CI | Two-way day/symbol CI |","|---|---|---|---:|---:|---:|---:|---|---|"]
    for label,phases in result["results"].items():
        for phase,v in phases.items():
            if phase == "training_resubstitution":
                continue
            if "error" in v: continue
            for model_name, model in v["models"].items():
                m=model["metrics"]; gain=model.get("brier_gain_vs_prevalence_candidate_weighted")
                boot=model.get("brier_gain_bootstrap")
                ci="—" if boot is None else f"[{boot['day_block_candidate_weighted_95pct_ci'][0]:.5f}, {boot['day_block_candidate_weighted_95pct_ci'][1]:.5f}]"
                tw="—" if boot is None else f"[{boot['day_plus_symbol_cluster_sensitivity_95pct_ci'][0]:.5f}, {boot['day_plus_symbol_cluster_sensitivity_95pct_ci'][1]:.5f}]"
                ap = "n/a" if m["average_precision"] is None else f"{m['average_precision']:.4f}"
                gain_text = "n/a" if gain is None else f"{gain:.5f}"
                lines.append(f"| {label} | {phase} | {model_name} | {m['brier']:.5f} | {m['log_loss']:.5f} | {ap} | {gain_text} | {ci} | {tw} |")
    lines += ["","## Candidate ranking (forward development period)","","| Policy | Selected | Continuation rate | Next-day down rate | Three-day down rate |","|---|---:|---:|---:|---:|"]
    for policy,v in result["ranking"].get("forward_2026H1",{}).items():
        def fmt(x): return "n/a" if x is None else f"{x:.2%}"
        lines.append(f"| {policy} | {v['selected']} | {fmt(v['continuation_rate'])} | {fmt(v['next_day_down_rate'])} | {fmt(v['three_day_down_rate'])} |")
    lines += ["","Bootstrap intervals use a candidate-weighted Brier gain ratio in every five-session moving-block replicate. The sensitivity interval resamples day blocks and symbol clusters. Average precision supplements Brier/Log Loss for rare down-event labels; calibration bins and ECE are present in JSON.","","Validation and 2026H1 are exposed research windows, not independent holdouts. Training metrics are resubstitution diagnostics only. The 2026H1 data are not used to set features, model parameters, or risk gates.","","No high-capacity nonlinear model was added: the fixed model-family comparisons are the market-only, stock-only, and joint regularized logistic specifications. This avoids adding complexity without a preregistered reason.","","The prior ranking remains exploratory and is superseded by the frozen risk-policy comparison report. No actionable or executable edge is established.",""]
    a.out_markdown.write_text("\n".join(lines),encoding="utf-8"); print(json.dumps({"status":result["classification"],"matrix_rows":result["matrix_rows"],"forward_ranking":result["ranking"].get("forward_2026H1",{})},ensure_ascii=False,indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
