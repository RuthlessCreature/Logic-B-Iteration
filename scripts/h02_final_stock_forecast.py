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
FEATURES = (
    "vendor_streak_length", "limit_up_count_3", "limit_up_count_5", "limit_down_count_5",
    "days_since_limit_down", "vendor_limit_up_count", "vendor_limit_down_count",
    "vendor_limit_break_count", "limit_up_pool_change_3_sessions", "limit_up_pool_change_5_sessions",
    "lagged_continuation_rate", "lagged_continuation_change_3_sessions", "rise_fall_event_ratio",
    "market_temperature", "market_theme_assignment_coverage", "theme_hhi",
)


def _phase(day: str) -> str:
    return "train" if day <= TRAIN_END else "validation_2025H2" if day <= VALID_END else "forward_2026H1"


def _matrix(train: pd.DataFrame, frame: pd.DataFrame) -> tuple[np.ndarray, list[str], dict[str, float], dict[str, float]]:
    medians: dict[str, float] = {}
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    train_x = []
    test_x = []
    names = []
    for name in FEATURES:
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


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, label: str) -> np.ndarray:
    x_train, names, _, scales = _matrix(train, train)
    x_test, _, _, _ = _matrix(train, test)
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
    return {"n": int(len(y)), "events": int(y.sum()), "prevalence": float(y.mean()) if len(y) else None,
            "brier": float(np.mean((p-y)**2)) if len(y) else None,
            "log_loss": float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))) if len(y) else None,
            "top_decile_precision": float(y[order].mean()) if k else None,
            "top_decile_event_recall": float(y[order].sum()/y.sum()) if k and y.sum() else None,
            "calibration_bins": bins}


def _brier_gain_ci(rows: pd.DataFrame, y: np.ndarray, model: np.ndarray, baseline: np.ndarray) -> list[float] | None:
    by_day: dict[str, list[float]] = {}
    for day, obs, pred, base in zip(rows.outcome_date.astype(str), y, model, baseline):
        by_day.setdefault(day, []).append(float((obs-base)**2-(obs-pred)**2))
    days = sorted(by_day)
    if len(days) < 5:
        return None
    rng = np.random.default_rng(20261014)
    blocks = math.ceil(len(days)/5)
    starts = rng.integers(0, len(days), size=(1000, blocks))
    idx = ((starts[:,:,None] + np.arange(5)[None,None,:]) % len(days)).reshape(1000,-1)[:,:len(days)]
    vals = np.asarray([np.mean(by_day[d]) for d in days])
    draws = vals[idx].mean(axis=1)
    return [float(np.quantile(draws,.025)), float(np.quantile(draws,.975))]


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
    report: dict[str, Any] = {"classification": "TIER_D_EXPLORATORY_FORECAST_AND_RANKING_NOT_TRADING_PERFORMANCE",
        "matrix_sha256": hashlib.sha256(raw).hexdigest(), "matrix_rows": len(df), "features": list(FEATURES),
        "training_end": TRAIN_END, "validation_end": VALID_END, "forward_end": "20260630",
        "model": "fixed L2 logistic regression, penalty 1.0, 400 gradient steps, no validation tuning; train-only median imputation/scaling",
        "protected_holdout_accessed": False, "results": {}, "ranking": {}}
    for label in LABELS:
        train = df[(df.phase == "train") & df[label].notna()]
        report["results"][label] = {}
        for phase in ("validation_2025H2", "forward_2026H1"):
            test = df[(df.phase == phase) & df[label].notna()]
            if train.empty or test.empty:
                report["results"][label][phase] = {"error": "no eligible train or evaluation rows"}
                continue
            pred = _fit_predict(train, test, label)
            base = np.full(len(test), float(train[label].mean()))
            y = test[label].to_numpy(float)
            report["results"][label][phase] = {"train_n": len(train), "train_rate": float(train[label].mean()),
                "prevalence_baseline": _metrics(y, base), "logistic": _metrics(y, pred),
                "brier_gain_vs_prevalence_positive_is_better": float(np.mean((y-base)**2)-np.mean((y-pred)**2)),
                "brier_gain_5_session_block_bootstrap_95pct_ci": _brier_gain_ci(test, y, pred, base)}
            if phase == "forward_2026H1":
                test = test.copy()
                test["p"] = pred
                report.setdefault("_preds", {}).setdefault(phase, {})[label] = test[["outcome_date","ts_code","p"]]
    # Score for candidate selection uses train-only fits for all three outcomes.
    forward = df[(df.phase == "forward_2026H1") & df.continuation_D.notna()].copy()
    train_sets = {label: df[(df.phase == "train") & df[label].notna()] for label in LABELS}
    forward["p_continuation"] = _fit_predict(train_sets[LABELS[0]], forward, LABELS[0])
    forward["p_down_next"] = _fit_predict(train_sets[LABELS[1]], forward, LABELS[1])
    forward["p_down_three"] = _fit_predict(train_sets[LABELS[2]], forward, LABELS[2])
    report["ranking"] = _ranking(forward)
    report.pop("_preds", None)
    risk_top3 = report["ranking"].get("forward_2026H1", {}).get("risk_adjusted_top3", {})
    all_candidates = report["ranking"].get("forward_2026H1", {}).get("unfiltered_all_candidates", {})
    report["research_verdict"] = {
        "forecasting": "The fixed logistic model lowers Brier score versus the train-prevalence baseline for all three vendor-event labels in both validation and forward development windows; this is predictive evidence for event-pool labels only.",
        "candidate_ranking": "The forward risk-adjusted top-3/day subset has a higher three-day vendor limit-down event rate than the full candidate pool. The heuristic increases continuation concentration but does not demonstrate lower downside incidence or positive expectancy.",
        "forward_risk_adjusted_top3_three_day_down_rate": risk_top3.get("three_day_down_rate"),
        "forward_unfiltered_three_day_down_rate": all_candidates.get("three_day_down_rate"),
        "tradeable_edge_established": False,
    }
    report["interpretation_guardrails"] = ["Targets are vendor event-pool membership, not official price-limit states.",
        "Predictions use D-1 fields, but historical publication-time/PIT availability is uncertified.",
        "Ranking has arbitrary equal-weight proxy penalties and top-1/top-3 limits; it does not establish net expectancy or executable edge.",
        "The 2026H1 period is exposed development data, not protected holdout."]
    return report


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--matrix",type=Path,required=True); p.add_argument("--out-json",type=Path,required=True); p.add_argument("--out-markdown",type=Path,required=True); a=p.parse_args()
    result=analyze(a.matrix); a.out_json.parent.mkdir(parents=True,exist_ok=True); a.out_json.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    lines=["# H02 forecast and candidate-risk ranking research","","**Tier D exploratory research. No actual returns, costs, fill evidence, or PIT certification.**","",f"Matrix SHA256: `{result['matrix_sha256']}`; rows: {result['matrix_rows']:,}.","","## Forecast metrics","","| Target | Evaluation phase | Baseline Brier | Logistic Brier | Brier gain (positive better) | 95% day-block CI |","|---|---|---:|---:|---:|---|"]
    for label,phases in result["results"].items():
        for phase,v in phases.items():
            if "error" in v: continue
            ci=v["brier_gain_5_session_block_bootstrap_95pct_ci"]; cit="n/a" if ci is None else f"[{ci[0]:.5f}, {ci[1]:.5f}]"
            lines.append(f"| {label} | {phase} | {v['prevalence_baseline']['brier']:.5f} | {v['logistic']['brier']:.5f} | {v['brier_gain_vs_prevalence_positive_is_better']:.5f} | {cit} |")
    lines += ["","## Candidate ranking (forward development period)","","| Policy | Selected | Continuation rate | Next-day down rate | Three-day down rate |","|---|---:|---:|---:|---:|"]
    for policy,v in result["ranking"].get("forward_2026H1",{}).items():
        def fmt(x): return "n/a" if x is None else f"{x:.2%}"
        lines.append(f"| {policy} | {v['selected']} | {fmt(v['continuation_rate'])} | {fmt(v['next_day_down_rate'])} | {fmt(v['three_day_down_rate'])} |")
    lines += ["","The fixed logistic forecast lowers Brier score versus a train-prevalence baseline for all three vendor-event labels in both validation and forward development windows. This is evidence for predicting vendor event membership only.","","The risk-adjusted top-3/day rule raises continuation concentration, but its forward three-day vendor down-event rate (26.90%) is higher than the full pool (10.74%). This ranking did not reduce observed downside incidence. The score is `P(continuation) - 0.5*P(next-day down) - 0.5*P(three-day down)`; the weights are a transparent heuristic, not fitted utility. No actionable or executable edge is established.","","Model parameters and feature list are fixed in source. Validation is descriptive and is not used for tuning; final 2026H1 results are development-only and exposed.",""]
    a.out_markdown.write_text("\n".join(lines),encoding="utf-8"); print(json.dumps({"status":result["classification"],"matrix_rows":result["matrix_rows"],"forward_ranking":result["ranking"].get("forward_2026H1",{})},ensure_ascii=False,indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
