"""Train-only frozen A-G candidate rules and tail-risk diagnostics for H02.

Outputs are research event-label summaries. They are not executable signals,
return estimates, or trading recommendations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import h02_final_stock_forecast as forecast

PHASES = ("validation_2025H2", "forward_2026H1")
RULE_NAMES = ("A_full_pool_reference", "B_continuation_top3", "C_transparent_risk_score_top3",
              "D_C_plus_train_oof_down3_cap", "E_B_veto_streak_3plus", "F_B_abstain_compounded_weak_market",
              "G_C_abstain_model_disagreement")
LABELS = ("continuation_D", "down_next_D", "down_three_D_to_D2")


def _quantile(values: pd.Series | np.ndarray, q: float) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.quantile(arr, q)) if len(arr) else 0.0


def _rolling_oof(df: pd.DataFrame) -> pd.DataFrame:
    """Expanding-origin training predictions, in five-session scored blocks."""
    train = df[df.outcome_date <= forecast.TRAIN_END].copy()
    days = sorted(train.outcome_date.unique().tolist())
    warmup = 60
    scored: list[pd.DataFrame] = []
    for start in range(warmup, len(days), 5):
        test_days = days[start:start + 5]
        # Y3 labels reach two sessions beyond the candidate outcome date.
        fit_days = days[:max(0, start - 2)]
        fit = train[train.outcome_date.isin(fit_days)]
        test = train[train.outcome_date.isin(test_days) & train.down_three_D_to_D2.notna()].copy()
        if len(fit) < 500 or test.empty:
            continue
        scored_test = test.copy()
        for label, col in zip(forecast.LABELS, ("p_continuation", "p_down_next", "p_down_three")):
            eligible_fit = fit[fit[label].notna()]
            for model_name, feature_set in (("market", forecast.MARKET_FEATURES), ("stock", forecast.STOCK_FEATURES), ("joint", forecast.JOINT_FEATURES)):
                scored_test.loc[:, f"{col}_{model_name}"] = forecast._fit_predict(eligible_fit, scored_test, label, feature_set)
            scored_test.loc[:, col] = scored_test[f"{col}_joint"]
        scored.append(scored_test)
    if not scored:
        raise RuntimeError("rolling-origin training OOF produced no eligible rows")
    result = pd.concat(scored, ignore_index=True)
    result["disagreement_down3"] = result[["p_down_three_market", "p_down_three_stock", "p_down_three_joint"]].max(axis=1) - result[["p_down_three_market", "p_down_three_stock", "p_down_three_joint"]].min(axis=1)
    return result


def _fit_thresholds(oof: pd.DataFrame) -> dict[str, Any]:
    train = oof
    down_cap = _quantile(train.p_down_three, .75)
    disagreement = _quantile(train.disagreement_down3, .80)
    q25_breadth = _quantile(train.vendor_limit_up_count, .25)
    q25_change = _quantile(train.lagged_continuation_change_3_sessions, .25)
    return {
        "source": "expanding-origin 5-session blocked OOF predictions from train dates only; each fit purges the latest 2 sessions for Y3 overlap",
        "oof_rows": len(train), "oof_start": str(train.outcome_date.min()), "oof_end": str(train.outcome_date.max()),
        "down3_probability_q75": down_cap,
        "down3_model_disagreement_range_q80": disagreement,
        "market_breadth_q25": q25_breadth,
        "lagged_continuation_change_q25": q25_change,
        "breadth_fixed_83": 83,
        "model_feature_sets": {"market": list(forecast.MARKET_FEATURES), "stock": list(forecast.STOCK_FEATURES), "joint": list(forecast.JOINT_FEATURES)},
        "rule_definitions": {
            "A_full_pool_reference": "all candidate rows; descriptive benchmark, uncapped",
            "B_continuation_top3": "rank by train-fitted joint p(Y1), then ts_code; retain at most 3 per outcome session",
            "C_transparent_risk_score_top3": "rank by p(Y1)-0.5*p(Y2)-0.5*p(Y3), then ts_code; retain at most 3",
            "D_C_plus_train_oof_down3_cap": "C then abstain where joint p(Y3) exceeds train OOF q75; retain at most 3",
            "E_B_veto_streak_3plus": "B with predeclared streak >=3 veto; retain at most 3",
            "F_B_abstain_compounded_weak_market": "B abstains when breadth < train OOF q25 AND lagged continuation change < train OOF q25; retain at most 3",
            "G_C_abstain_model_disagreement": "C abstains where range of three fixed model p(Y3) scores exceeds train OOF q80; retain at most 3",
        },
        "selection_limit": {"research_shortlist_max_per_session": 3, "final_candidate_max_per_session": 1,
            "final_candidate_is_highest_ranked_shortlist_item": True},
    }


def _add_predictions(df: pd.DataFrame) -> pd.DataFrame:
    train = {label: df[(df.outcome_date <= forecast.TRAIN_END) & df[label].notna()] for label in forecast.LABELS}
    out = df.copy()
    for label, col in zip(forecast.LABELS, ("p_continuation", "p_down_next", "p_down_three")):
        eligible = out[label].notna()
        for name, features in (("market", forecast.MARKET_FEATURES), ("stock", forecast.STOCK_FEATURES), ("joint", forecast.JOINT_FEATURES)):
            out.loc[eligible, f"{col}_{name}"] = forecast._fit_predict(train[label], out.loc[eligible], label, features)
        out.loc[eligible, col] = out.loc[eligible, f"{col}_joint"]
    out["disagreement_down3"] = out[["p_down_three_market", "p_down_three_stock", "p_down_three_joint"]].max(axis=1) - out[["p_down_three_market", "p_down_three_stock", "p_down_three_joint"]].min(axis=1)
    out["risk_score"] = out.p_continuation - .5*out.p_down_next - .5*out.p_down_three
    return out


def _moving_weights(day_count: int, reps: int, rng: np.random.Generator) -> np.ndarray:
    blocks = math.ceil(day_count/5)
    starts = rng.integers(0, day_count, size=(reps, blocks))
    sampled = ((starts[:, :, None] + np.arange(5)[None, None, :]) % day_count).reshape(reps, -1)[:, :day_count]
    return np.stack([np.bincount(row, minlength=day_count) for row in sampled])


def _rate_ci(frame: pd.DataFrame, label: str, calendar: list[str], reps: int = 1000) -> dict[str, Any]:
    valid = frame[frame[label].notna()]
    if valid.empty:
        return {"n": 0, "events": 0, "rate": None, "ci_95": None}
    grouped = valid.groupby("outcome_date")[label].agg(["sum", "count"])
    ev = np.asarray([grouped.loc[d, "sum"] if d in grouped.index else 0 for d in calendar], float)
    n = np.asarray([grouped.loc[d, "count"] if d in grouped.index else 0 for d in calendar], float)
    rng = np.random.default_rng(20261014)
    w = _moving_weights(len(calendar), reps, rng)
    den = w @ n
    draw = (w @ ev)[den > 0] / den[den > 0]
    return {"n": len(valid), "events": int(valid[label].sum()), "rate": float(valid[label].mean()),
            "ci_95": [float(np.quantile(draw, .025)), float(np.quantile(draw, .975))] if len(draw) else None}


def _daily_tail(frame: pd.DataFrame, label: str, calendar: list[str]) -> dict[str, Any]:
    valid = frame[frame[label].notna()]
    by_day = valid.groupby("outcome_date")[label].agg(["sum", "count"])
    rates = np.asarray([by_day.loc[d, "sum"] / by_day.loc[d, "count"] if d in by_day.index else np.nan for d in calendar], float)
    rolling = pd.Series(rates).rolling(5, min_periods=5).mean().dropna()
    symbols = valid.groupby("ts_code")[label].agg(["sum", "count"]).sort_values(["sum", "count"], ascending=False)
    total_events = int(valid[label].sum())
    top_events = int(symbols.head(10)["sum"].sum()) if len(symbols) else 0
    return {"sessions_with_labels": int(np.isfinite(rates).sum()),
            "empty_selected_sessions": int(sum(not (valid.outcome_date == d).any() for d in calendar)),
            "session_rate_q90": float(np.nanquantile(rates, .90)) if np.isfinite(rates).any() else None,
            "session_rate_q95": float(np.nanquantile(rates, .95)) if np.isfinite(rates).any() else None,
            "worst_session_rate": float(np.nanmax(rates)) if np.isfinite(rates).any() else None,
            "worst_rolling_5_session_mean": float(rolling.min()) if len(rolling) else None,
            "top10_symbols_share_of_events": top_events / total_events if total_events else None,
            "top10_symbols_event_count": top_events}


def _paired_rate_difference_ci(selected: pd.DataFrame, full_pool: pd.DataFrame, label: str, calendar: list[str], reps: int = 1000) -> dict[str, Any]:
    def daily_counts(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        valid = frame[frame[label].notna()]
        grouped = valid.groupby("outcome_date")[label].agg(["sum", "count"])
        events = np.asarray([grouped.loc[d, "sum"] if d in grouped.index else 0 for d in calendar], float)
        count = np.asarray([grouped.loc[d, "count"] if d in grouped.index else 0 for d in calendar], float)
        return events, count
    se, sn = daily_counts(selected)
    pe, pn = daily_counts(full_pool)
    if not sn.sum() or not pn.sum():
        return {"selected_minus_full_pool": None, "ci_95": None}
    rng = np.random.default_rng(20261014)
    weights = _moving_weights(len(calendar), reps, rng)
    sd, pdn = weights @ sn, weights @ pn
    eligible = (sd > 0) & (pdn > 0)
    draws = (weights[eligible] @ se) / sd[eligible] - (weights[eligible] @ pe) / pdn[eligible]
    point = float(se.sum()/sn.sum() - pe.sum()/pn.sum())
    return {"selected_minus_full_pool": point,
            "ci_95": [float(np.quantile(draws, .025)), float(np.quantile(draws, .975))] if len(draws) else None}


def _select(frame: pd.DataFrame, thresholds: dict[str, Any]) -> dict[str, pd.DataFrame]:
    selected = {name: [] for name in RULE_NAMES}
    for _, day in frame.groupby("outcome_date", sort=True):
        day = day.sort_values("ts_code", kind="mergesort")
        selected["A_full_pool_reference"].extend(day.to_dict("records"))
        ranked_b = day.sort_values(["p_continuation", "ts_code"], ascending=[False, True], kind="mergesort")
        ranked_c = day.sort_values(["risk_score", "ts_code"], ascending=[False, True], kind="mergesort")
        selected["B_continuation_top3"].extend(ranked_b.head(3).to_dict("records"))
        selected["C_transparent_risk_score_top3"].extend(ranked_c.head(3).to_dict("records"))
        selected["D_C_plus_train_oof_down3_cap"].extend(ranked_c[ranked_c.p_down_three <= thresholds["down3_probability_q75"]].head(3).to_dict("records"))
        selected["E_B_veto_streak_3plus"].extend(ranked_b[ranked_b.vendor_streak_length < 3].head(3).to_dict("records"))
        weak = (ranked_b.vendor_limit_up_count < thresholds["market_breadth_q25"]) & (ranked_b.lagged_continuation_change_3_sessions < thresholds["lagged_continuation_change_q25"])
        selected["F_B_abstain_compounded_weak_market"].extend(ranked_b[~weak].head(3).to_dict("records"))
        selected["G_C_abstain_model_disagreement"].extend(ranked_c[ranked_c.disagreement_down3 <= thresholds["down3_model_disagreement_range_q80"]].head(3).to_dict("records"))
    return {name: pd.DataFrame(rows) for name, rows in selected.items()}


def analyze(matrix: Path) -> dict[str, Any]:
    raw = matrix.read_bytes()
    df = pd.read_csv(matrix, dtype={"ts_code": str, "outcome_date": str})
    train = df[df.outcome_date <= forecast.TRAIN_END]
    oof = _rolling_oof(df)
    thresholds = _fit_thresholds(oof)
    predicted = _add_predictions(df)
    report: dict[str, Any] = {
        "classification": "TIER_D_EXPOSED_VENDOR_EVENT_POLICY_RESEARCH_NOT_TRADING_PERFORMANCE",
        "matrix_sha256": hashlib.sha256(raw).hexdigest(), "matrix_rows": len(df),
        "train_rows": len(train), "train_sessions": int(train.outcome_date.nunique()),
        "protected_holdout_accessed": False, "thresholds_and_preregistered_rules": thresholds,
        "periods": {}, "interpretation": {
            "decision_edge": "NOT_DEMONSTRATED; policies are evaluated only on exposed vendor event labels and cannot establish actionable/fillable decisions",
            "economic_edge": "INSUFFICIENT_EVIDENCE; no OHLC/official limits/minute data/fees applied to observed market fills or after-cost returns",
            "pit": "UNVERIFIED; D-1 source publication time before the 09:35 decision is not certified",
            "behavioral_reinforcement": "BEHAVIORAL_REINFORCEMENT_NOT_IDENTIFIED; no direct investor-account, order-flow, or feedback-loop evidence",
        },
    }
    for phase in PHASES:
        pool = predicted[(predicted.phase == phase) & predicted.continuation_D.notna()].copy()
        calendar = sorted(pool.outcome_date.astype(str).unique().tolist())
        strategies = _select(pool, thresholds)
        phase_data = {"sessions": len(calendar), "pool_candidates": len(pool), "rules": {}}
        for rule, chosen in strategies.items():
            eligible = chosen[chosen.continuation_D.notna()] if len(chosen) else chosen
            metrics = {label: _rate_ci(eligible, label, calendar) for label in LABELS}
            day_counts = eligible.groupby("outcome_date").size() if len(eligible) else pd.Series(dtype=int)
            # At most one final candidate is the highest-ranked name in each daily shortlist.
            final = eligible.groupby("outcome_date", sort=True).head(1) if len(eligible) else eligible
            phase_data["rules"][rule] = {
                "selected_symbol_days": len(eligible), "pool_coverage": len(eligible)/len(pool) if len(pool) else None,
                "sessions_with_selection": int(day_counts.size), "empty_sessions": len(calendar)-int(day_counts.size),
                "shortlist_per_session_max": int(day_counts.max()) if len(day_counts) else 0,
                "final_candidates": len(final), "final_candidate_sessions": int(final.outcome_date.nunique()) if len(final) else 0,
                "final_max_per_session": int(final.groupby("outcome_date").size().max()) if len(final) else 0,
                "final_candidate_outcomes": {label: _rate_ci(final, label, calendar) for label in LABELS},
                "missed_Y1_events_vs_full_pool": int(pool.continuation_D.sum()-eligible.continuation_D.sum()) if len(eligible) else int(pool.continuation_D.sum()),
                "Y1_opportunity_loss_fraction": (float(pool.continuation_D.sum()-eligible.continuation_D.sum())/float(pool.continuation_D.sum())) if pool.continuation_D.sum() else None,
                "outcomes": metrics, "tail": {label: _daily_tail(eligible, label, calendar) for label in LABELS},
                "market_state": {},
            }
            # Retain outcomes by fixed training-origin market regimes, including adverse cells.
            for regime, mask in (("low_breadth", eligible.vendor_limit_up_count <= thresholds["market_breadth_q25"]),
                                 ("weakening", eligible.lagged_continuation_change_3_sessions <= thresholds["lagged_continuation_change_q25"]),
                                 ("high_streak_3plus", eligible.vendor_streak_length >= 3)):
                cell = eligible[mask]
                phase_data["rules"][rule]["market_state"][regime] = {label: _rate_ci(cell, label, calendar) for label in LABELS}
        # Predeclared interaction/tail tables for the full pool and each selected policy.
        phase_data["stability_strata"] = {}
        for rule, chosen in strategies.items():
            phase_data["stability_strata"][rule] = {}
            if not len(chosen):
                continue
            for field in ("vendor_streak_group", "limit_up_count_5_group", "breadth_group", "market_transition_group", "days_since_limit_down_group", "theme_hhi_group", "streak_down5_group"):
                phase_data["stability_strata"][rule][field] = {}
                for level, cell in chosen.groupby(field, dropna=False, sort=True):
                    phase_data["stability_strata"][rule][field][str(level)] = {"n": len(cell), "retained_share": len(cell)/len(chosen), **{label: _rate_ci(cell, label, calendar) for label in LABELS}}
        baseline = strategies["A_full_pool_reference"]
        for rule, chosen in strategies.items():
            differences = {label: _paired_rate_difference_ci(chosen, baseline, label, calendar) for label in LABELS}
            phase_data["rules"][rule]["paired_delta_vs_full_pool"] = differences
            y2, y3 = differences["down_next_D"], differences["down_three_D_to_D2"]
            phase_data["rules"][rule]["predeclared_decision_edge_rule_pass"] = bool(
                y2["ci_95"] and y3["ci_95"] and y2["ci_95"][1] < 0 and y3["ci_95"][1] < 0)
        phase_data["decision_rule"] = "Decision edge requires both Y2 and Y3 paired candidate-weighted rate differences vs full pool to have 5-session block 95% intervals entirely below zero; all comparisons retain missed Y1 opportunities."
        report["periods"][phase] = phase_data
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--out-markdown", required=True, type=Path)
    args = parser.parse_args()
    result = analyze(args.matrix)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    lines = ["# H02 frozen A–G strategy and tail-risk comparison", "", "**Research-only vendor event labels. PIT_UNVERIFIED; no realized returns, fill quality, costs, or executable edge.**", "",
        f"Matrix SHA256 `{result['matrix_sha256']}`; rows {result['matrix_rows']:,}; thresholds were fitted using training dates only.", "",
        "Rules A–G and their exact train-only definitions/cut points are in the JSON. Validation 2025H2 and 2026H1 are exposed development windows. Every capped rule selects at most three research shortlist names per session; a separate highest-ranked name is counted as the one-name final candidate.", "",
        "## Policy outcomes", "", "| Phase | Rule | Selected | Empty sessions | Coverage | Y1 rate | Y2 rate | Y3 rate | ΔY2 vs pool | ΔY3 vs pool | Missed Y1 | Y1 loss | Worst 5-session Y3 | Decision gate |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for phase, p in result["periods"].items():
        for rule, v in p["rules"].items():
            fmt = lambda x: "n/a" if x is None else f"{x:.2%}"
            y1, y2, y3 = (v["outcomes"][label]["rate"] for label in LABELS)
            loss = v["Y1_opportunity_loss_fraction"]
            d2, d3 = v["paired_delta_vs_full_pool"]["down_next_D"], v["paired_delta_vs_full_pool"]["down_three_D_to_D2"]
            worst5 = v["tail"]["down_three_D_to_D2"]["worst_rolling_5_session_mean"]
            lines.append(f"| {phase} | {rule} | {v['selected_symbol_days']} | {v['empty_sessions']} | {fmt(v['pool_coverage'])} | {fmt(y1)} | {fmt(y2)} | {fmt(y3)} | {fmt(d2['selected_minus_full_pool'])} | {fmt(d3['selected_minus_full_pool'])} | {v['missed_Y1_events_vs_full_pool']} | {fmt(loss)} | {fmt(worst5)} | {'PASS' if v['predeclared_decision_edge_rule_pass'] else 'FAIL'} |")
    lines += ["", "All rules preserve the same candidate-weighted 5-session moving-block estimand for event rates and include 95% intervals in JSON. Tail tables report session q90/q95, worst single session, worst rolling five-session rate, and top-ten symbol event concentration. Fixed regime and interaction tables retain adverse/empty groups; they are descriptive and not multiplicity-adjusted.", "", "## Limits", "", "Vendor event-pool membership is not independently verified official price-limit status. Features are D-1 but publication-time availability at 09:35 is uncertified. The source archive lacks independent OHLC, official limit prices, PIT ST/halt, minute bars and executable fills. Therefore these comparisons cannot demonstrate economic edge.", "", "`BEHAVIORAL_REINFORCEMENT_NOT_IDENTIFIED`: no direct investor account, order-flow, or feedback-loop data are present.", ""]
    args.out_markdown.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": result["classification"], "periods": {k: {"sessions": v["sessions"], "rules": len(v["rules"])} for k,v in result["periods"].items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
