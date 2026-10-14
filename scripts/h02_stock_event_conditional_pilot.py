"""Stock-event conditional probabilities from five SHA-pinned historical H01 archives.

Only prior closed-session pool membership is used as hypothetical features.
No historical publication/PIT/fill certification; not a strategy backtest.
Trains through 2025H1, validates 2025H2, checks 2026H1 development period.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from h02_first_empirical_result import load_market_events

START = "20240930"
TRAIN_END = "20250630"
VALIDATION_END = "20251231"
END = "20260630"
BREADTH_TRAIN_MEDIAN = 83  # frozen by preceding train-only market pilot
PSEUDO_COUNT = 200
LABELS = ("continuation", "down_next", "down_three")


def phase(day: str) -> str:
    if day <= TRAIN_END:
        return "train"
    if day <= VALIDATION_END:
        return "validation_2025H2"
    return "forward_2026H1"


def _check(data: dict):
    days = data.get("calendar_days")
    if not isinstance(days, list) or days != sorted(set(days)):
        raise ValueError("calendar must be unique and strictly sorted")
    if not days or any(not isinstance(d, str) or len(d) != 8 or not d.isdigit() or d > END for d in days):
        raise ValueError("unapproved or protected date in calendar")
    if not (any(START <= d <= TRAIN_END for d in days)
            and any(TRAIN_END < d <= VALIDATION_END for d in days)
            and any(VALIDATION_END < d <= END for d in days)):
        raise ValueError("development calendar has no complete train/validation/forward slices")
    for ds in ("limit_up", "limit_down"):
        if set(data[ds]) != set(days):
            raise ValueError(f"{ds} partition coverage does not match calendar")


def _stats(rows: list[dict], label: str):
    nfield = "n3" if label == "down_three" else "n"
    k = sum(r[label] or 0 for r in rows)
    n = sum(r[nfield] for r in rows)
    return {"numerator": k, "denominator": n, "rate": k / n if n else None}


def _brier(rows: list[dict], label: str, predict):
    nfield = "n3" if label == "down_three" else "n"
    loss, denom = 0.0, 0
    for row in rows:
        n = row[nfield]
        if not n:
            continue
        k = row[label]
        p = predict(row)
        if p is None or not 0 <= p <= 1:
            raise ValueError("invalid predicted probability")
        loss += k * (1 - p) ** 2 + (n - k) * p ** 2
        denom += n
    return loss / denom if denom else None


def analyze(data: dict) -> dict:
    _check(data)
    days = data["calendar_days"]
    up, down = data["limit_up"], data["limit_down"]
    valid_start = days.index("20250701") if "20250701" in days else next((i for i,d in enumerate(days) if d > TRAIN_END), None)
    if valid_start is None:
        raise ValueError("validation date boundary missing")
    rows = []
    for i, d in enumerate(days):
        if not (START <= d <= END):
            continue
        if i < 3:
            raise ValueError("insufficient D-1/D-2/D-3 context")
        prev = days[i-1]
        cohort = up[prev]
        risk_complete = i+2 < len(days) and days[i+2] <= END
        down_three = set().union(down[d], down[days[i+1]], down[days[i+2]]) if risk_complete else set()
        # Only prior closed sessions determine streak and breadth.
        features: dict[tuple[str,str], dict] = {}
        for code in cohort:
            streak = "REPEAT2PLUS" if code in up[days[i-2]] else "FIRST"
            breadth = "HIGH" if len(cohort) > BREADTH_TRAIN_MEDIAN else "LOW"
            key = (streak, breadth)
            record = features.setdefault(key, {
                "outcome_date": d, "period": phase(d),
                "streak": streak, "breadth": breadth,
                "n": 0, "n3": 0, "continuation": 0,
                "down_next": 0, "down_three": 0,
                "three_day_train_purge": phase(d) == "train" and i+2 >= valid_start,
            })
            record["n"] += 1
            record["continuation"] += int(code in up[d])
            record["down_next"] += int(code in down[d])
            if risk_complete:
                record["n3"] += 1
                record["down_three"] += int(code in down_three)
        rows.extend(features.values())
    if not rows:
        raise ValueError("no candidate events in development range")
    segments = {
        "train": [r for r in rows if r["period"] == "train"],
        "validation_2025H2": [r for r in rows if r["period"] == "validation_2025H2"],
        "forward_2026H1": [r for r in rows if r["period"] == "forward_2026H1"],
    }
    for period, part in segments.items():
        if not part:
            raise ValueError(f"empty {period}")
    report = {
        "classification": "TIER_D_EXPLORATORY_STOCK_EVENT_STRATIFICATION_NOT_EXECUTABLE_RETURNS",
        "source_run_id": data.get("source_run_id"),
        "fixed_prior_limitup_breadth_cut": BREADTH_TRAIN_MEDIAN,
        "known_limitations": [
            "Pool membership is historical vendor event data; close-only semantics and 09:35 availability are unverified.",
            "Validation and forward periods are exposed development periods, not the protected holdout.",
            "Overlapping stock event-days are not independent; no confidence intervals or strategy profitability claims.",
            "A second consecutive pool appearance is a vendor event streak, not necessarily two official close limit-ups.",
        ],
        "periods": {},
        "outcomes": {},
        "archive_sha256": data.get("archive_hashes"),
        "protected_holdout_accessed": False,
    }
    for period, part in segments.items():
        report["periods"][period] = {
            "days": len({r["outcome_date"] for r in part}),
            "candidate_symbol_days": sum(r["n"] for r in part),
            "first_event": sum(r["n"] for r in part if r["streak"]=="FIRST"),
            "repeat_event": sum(r["n"] for r in part if r["streak"]=="REPEAT2PLUS"),
        }
    for label in LABELS:
        train = segments["train"]
        if label == "down_three":
            train = [r for r in train if not r["three_day_train_purge"]]
        overall = _stats(train, label)
        if not overall["denominator"]:
            raise ValueError("empty training denominator")
        baseline = overall["rate"]
        nfield = "n3" if label=="down_three" else "n"

        def _fit(by):
            pool = defaultdict(lambda: [0, 0])
            for r in train:
                group = by(r)
                pool[group][0] += r[label]
                pool[group][1] += r[nfield]
            return {
                key: (k + PSEUDO_COUNT * baseline) / (n + PSEUDO_COUNT)
                for key, (k,n) in pool.items()
            }
        p_streak = _fit(lambda r: r["streak"])
        p_joint = _fit(lambda r: r["streak"] + "_" + r["breadth"])
        by_period = {}
        for period, part in segments.items():
            by_streak = {
                s: _stats([r for r in part if r["streak"]==s],label)
                for s in ("FIRST","REPEAT2PLUS")
            }
            by_joint = {
                s+"_"+b: _stats([r for r in part if r["streak"]==s and r["breadth"]==b],label)
                for s in ("FIRST","REPEAT2PLUS") for b in ("LOW","HIGH")
            }
            p0 = _brier(part,label,lambda _:baseline)
            ps = _brier(part,label,lambda r:p_streak.get(r["streak"],baseline))
            pj = _brier(part,label,lambda r:p_joint.get(r["streak"]+"_"+r["breadth"],baseline))
            by_period[period] = {
                "observed": _stats(part,label),
                "by_streak": by_streak,
                "by_streak_and_breadth": by_joint,
                "brier_baseline": p0,
                "brier_streak": ps,
                "brier_joint": pj,
                "joint_brier_gain_vs_baseline": p0-pj if p0 is not None and pj is not None else None,
            }
        report["outcomes"][label] = {
            "training_pooled_probability": baseline,
            "training_fit_candidate_denominator": overall["denominator"],
            "trained_streak_probabilities": p_streak,
            "trained_joint_probabilities": p_joint,
            "by_period": by_period,
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", nargs=5, required=True, type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = load_market_events(args.artifacts)
    report = analyze(data)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "classification":report["classification"],
        "periods":report["periods"],
        "outcomes": {
            k:{p:{
                "baseline":q["brier_baseline"],
                "joint":q["brier_joint"],
                "gain":q["joint_brier_gain_vs_baseline"],
                "streak":q["by_streak"],
            }for p,q in v["by_period"].items()} for k,v in report["outcomes"].items()
        },
    },ensure_ascii=False,indent=2,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
