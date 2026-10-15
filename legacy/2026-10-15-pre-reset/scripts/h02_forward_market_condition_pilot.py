"""Frozen train-only market-state predictive pilot from retained H02 Tier-D daily aggregates.

Uses D-1 limit-up pool size and D-1 observed pool continuation to predict the
D membership outcomes. These vendor event labels are NOT executable returns or
PIT-certified signals. Never train on 2026-07-01..2026-09-28 holdout.

No parameter search. Fixed train 2024-09-30..2025-06-30; validation 2025H2;
forward development check 2026H1. Three-day labels are purged at train boundary.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

SOURCE = Path(__file__).parents[1] / "research/experiments/h02-stage0-20261013/H02_FIRST_EMPIRICAL_RESULT_20261014.json"
TRAIN_END = "20250630"
VALIDATION_END = "20251231"
DEV_END = "20260630"
PSEUDO_COUNT = 200
LABELS = {
    "continuation": ("next_day_limit_up_pool_matches", "prior_limit_up_candidates"),
    "next_day_down_event": ("next_day_limit_down_pool_matches", "prior_limit_up_candidates"),
    "three_day_down_event": ("three_trade_day_limit_down_pool_touches", "three_day_denominator"),
}


def _period(day: str) -> str:
    if day <= TRAIN_END:
        return "train"
    if day <= VALIDATION_END:
        return "validation_2025H2"
    return "forward_2026H1"


def _prepare(source: dict) -> list[dict]:
    if source.get("classification") != "TIER_D_HISTORICAL_MARKET_EVENT_OBSERVATION_NOT_TRADING_PERFORMANCE":
        raise ValueError("requires the pinned Tier-D event observation schema")
    if source.get("protected_holdout_accessed") is not False:
        raise ValueError("protected holdout flag must be false")
    raw = source.get("daily")
    if not isinstance(raw, list) or not raw:
        raise ValueError("missing source daily records")
    rows: list[dict] = []
    seen: set[str] = set()
    for original in raw:
        day = original["outcome_date"]
        if not isinstance(day, str) or len(day) != 8 or not day.isdigit() or not ("20240930" <= day <= DEV_END):
            raise ValueError("record outside allowed development date window")
        if day in seen:
            raise ValueError("duplicate day")
        seen.add(day)
        row = dict(original)
        count = row["prior_limit_up_candidates"]
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("invalid candidate count")
        for label, (numerator, denominator) in LABELS.items():
            k, n = row[numerator], row[denominator]
            if label == "three_day_down_event" and (k is None or n is None):
                if not (k is None and n is None):
                    raise ValueError("incomplete three-day pair")
                continue
            if isinstance(k, bool) or isinstance(n, bool) or not isinstance(k, int) or not isinstance(n, int) or not (0 <= k <= n) or n <= 0:
                raise ValueError("invalid event numerator/denominator")
            if label != "three_day_down_event" and n != count:
                raise ValueError("event denominator does not match candidate count")
            if label == "three_day_down_event" and n != count:
                raise ValueError("three-day denominator mismatch")
        row["period"] = _period(day)
        row["breadth"] = count  # count of vendor events at D-1 close; PIT NOT certified
        row["lag_continuation"] = None
        rows.append(row)
    if [x["outcome_date"] for x in rows] != sorted(seen):
        raise ValueError("dates not strictly increasing")
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        # D-1 outcome, never today's label. The source's historical publication
        # before today's 09:35 is NOT certified; classify only as Tier D.
        rows[i]["lag_continuation"] = (
            prev["next_day_limit_up_pool_matches"] / prev["prior_limit_up_candidates"]
        )
    if sum(r["period"] == "train" for r in rows) < 10 or not any(r["period"] == "validation_2025H2" for r in rows) or not any(r["period"] == "forward_2026H1" for r in rows):
        raise ValueError("need train, validation, and forward development slices")
    return rows


def _rate(rows: list[dict], label: str) -> dict:
    kfield, nfield = LABELS[label]
    eligible = [r for r in rows if r[nfield] is not None]
    k = sum(r[kfield] for r in eligible)
    n = sum(r[nfield] for r in eligible)
    return {"numerator": k, "denominator": n, "rate": k / n if n else None, "days": len(eligible)}


def _brier(rows: list[dict], label: str, predict) -> dict:
    kfield, nfield = LABELS[label]
    nsum = 0
    loss = 0.0
    for r in rows:
        n, k = r[nfield], r[kfield]
        if n is None:
            continue
        p = predict(r)
        if not isinstance(p, (float, int)) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("invalid predicted probability")
        loss += k * (1 - p) ** 2 + (n - k) * p ** 2
        nsum += n
    return {"brier": loss / nsum if nsum else None, "candidate_observations": nsum}


def analyze(source: dict) -> dict:
    rows = _prepare(source)
    train = [r for r in rows if r["period"] == "train"]
    valid = [r for r in rows if r["period"] == "validation_2025H2"]
    forward = [r for r in rows if r["period"] == "forward_2026H1"]
    median_breadth = statistics.median(r["breadth"] for r in train)
    median_lag = statistics.median(r["lag_continuation"] for r in train if r["lag_continuation"] is not None)

    def breadth_group(r: dict) -> str:
        return "LOW" if r["breadth"] <= median_breadth else "HIGH"

    def dual_group(r: dict) -> str:
        lag = r["lag_continuation"]
        return breadth_group(r) + "_" + ("LAG_UNKNOWN" if lag is None else "LOW_LAG" if lag <= median_lag else "HIGH_LAG")

    segments = {"train": train, "validation_2025H2": valid, "forward_2026H1": forward}
    model_out: dict = {}
    for label in LABELS:
        # Labels D..D+2 must not cross into first validation day. Exclude
        # the last two training dates from fitting the 3-day outcome.
        train_fit = train[:-2] if label == "three_day_down_event" else train
        train_fit = [r for r in train_fit if r[LABELS[label][1]] is not None]
        base = _rate(train_fit, label)
        if not base["denominator"]:
            raise ValueError("training event denominator missing")
        p0 = base["rate"]

        def fitted(groups, rule):
            result = {}
            for r in train_fit:
                group = rule(r)
                stats = result.setdefault(group, {"numerator": 0, "denominator": 0})
                stats["numerator"] += r[LABELS[label][0]]
                stats["denominator"] += r[LABELS[label][1]]
            return {g: (s["numerator"] + PSEUDO_COUNT * p0) / (s["denominator"] + PSEUDO_COUNT) for g, s in result.items()}

        p_breadth = fitted(train_fit, breadth_group)
        p_dual = fitted(train_fit, dual_group)
        per_segment: dict = {}
        for part, segment in segments.items():
            b0 = _brier(segment, label, lambda _: p0)
            b1 = _brier(segment, label, lambda r: p_breadth.get(breadth_group(r), p0))
            b2 = _brier(segment, label, lambda r: p_dual.get(dual_group(r), p0))
            groups = {}
            for group in ("LOW", "HIGH"):
                grp = [r for r in segment if breadth_group(r) == group]
                groups[group] = _rate(grp, label)
            per_segment[part] = {
                "observed": _rate(segment, label), "breadth_groups": groups,
                "baseline_brier": b0["brier"], "breadth_brier": b1["brier"],
                "breadth_plus_lag_brier": b2["brier"],
                "breadth_brier_gain": (b0["brier"] - b1["brier"]) if b0["brier"] is not None else None,
                "breadth_plus_lag_brier_gain": (b0["brier"] - b2["brier"]) if b0["brier"] is not None else None,
            }
        model_out[label] = {
            "fitted_train_rate": base, "fitted_breadth_probabilities": p_breadth,
            "fitted_breadth_plus_lag_probabilities": p_dual,
            "training_fit_days": len(train_fit), "by_period": per_segment,
        }
    return {
        "classification": "TIER_D_EXPLORATORY_MARKET_STATE_FORECAST_NOT_PIT_OR_TRADING_RETURNS",
        "status": "EXPLORE_FORWARD_DEV_ONLY",
        "source_report_classification": source["classification"],
        "source_run_id": source.get("source_run_id"),
        "source_archive_hashes": source.get("archive_hashes_sha256"),
        "source_holdout_accessed": False,
        "split": {"train": [train[0]["outcome_date"], train[-1]["outcome_date"]],
                  "validation": [valid[0]["outcome_date"], valid[-1]["outcome_date"]],
                  "forward_development": [forward[0]["outcome_date"], forward[-1]["outcome_date"]]},
        "train_only_frozen_thresholds": {"prior_limitup_breadth_median": median_breadth,
                                        "lagged_continuation_median": median_lag},
        "model": "Laplace-smoothed fixed 2-bin breadth / four-bin breadth+lag, 200 pseudo-candidates, no optimization",
        "features": ["D_minus_1_vendor_limitup_count", "D_minus_1_vendor_continuation_rate"],
        "known_limitations": [
            "Vendor pool membership may represent intraday touches rather than close-limit.",
            "Historical source availability before 09:35 is NOT verified.",
            "Day-level breadth exposures share outcomes and are not independent symbol-level samples.",
            "Validation and forward periods are exposed development data, never untouched external holdout.",
            "Observational probability forecasts do not constitute stock selection or executable profit.",
        ],
        "outcomes": model_out,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=Path("runs/h02-forward-market-pilot/report.json"))
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    report = analyze(source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "classification": report["classification"],
        "split": report["split"],
        "frozen_thresholds": report["train_only_frozen_thresholds"],
        "outcomes": {name: {
            part: {
                "base": record["baseline_brier"],
                "breadth": record["breadth_brier"],
                "breadth_plus_lag": record["breadth_plus_lag_brier"],
                "gain_breadth": record["breadth_brier_gain"],
                "gain_dual": record["breadth_plus_lag_brier_gain"],
                "observed_rate": record["observed"]["rate"],
                "N": record["observed"]["denominator"],
                "low_breadth": record["breadth_groups"]["LOW"],
                "high_breadth": record["breadth_groups"]["HIGH"],
            } for part, record in outcome["by_period"].items()
        } for name, outcome in report["outcomes"].items()}
    }, ensure_ascii=False, allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
