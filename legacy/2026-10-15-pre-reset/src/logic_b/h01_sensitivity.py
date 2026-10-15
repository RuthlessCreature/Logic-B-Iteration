"""Locked H01-A sensitivity analysis: isolate source-count anomalies and quantify error.

Anomaly exclusion is a robustness *diagnostic*, not permission to promote the
psychology factor. Original preregistered source mismatch cap remains 2%.
Study ends 2026-06-30; original holdout is never read or scored.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .h01_activity import H01DataBlocked, expanding_window_h01
from .h01_quarantine import quarantine_count_days

DEV_END = "2026-06-30"
FROZEN_SOURCE_MISMATCH_CAP = 0.02
FROZEN_TRAIN_DAYS = 120


def paired_block_interval(differences: np.ndarray, block: int, *, draws: int = 5000) -> list[float]:
    """Circular block bootstrap, seeded; does NOT establish causal inference."""
    x = np.asarray(differences, dtype=float)
    if len(x) < block or not np.isfinite(x).all():
        raise H01DataBlocked("insufficient finite paired errors")
    rng = np.random.default_rng(20261013 + block)
    n = len(x)
    starts = rng.integers(0, n, size=(draws, int(np.ceil(n / block))))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    estimates = x[idx.reshape(draws, -1)[:, :n]].mean(axis=1)
    return [float(v) for v in np.quantile(estimates, [0.025, 0.975])]


def analyze(joined: pd.DataFrame, audit: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(joined["trade_date"]).dt.strftime("%Y-%m-%d")
    if len(joined) < 160 or dates.max() > DEV_END:
        raise H01DataBlocked("insufficient development data or protected holdout included")
    if audit.empty or not set(audit["status"]).issubset({"MATCH", "SOURCE_DEFINITION_REVIEW"}):
        raise H01DataBlocked("missing or unexpected vendor-count audit statuses")
    x = quarantine_count_days(joined, audit, after=3)
    mismatches = int((audit["status"] != "MATCH").sum())
    mismatch_fraction = mismatches / len(audit)
    qdays = int(x["count_audit_quarantine"].sum())
    scores, pred = expanding_window_h01(x, min_train_days=FROZEN_TRAIN_DAYS, min_test_days=40)
    if scores["status"].startswith("BLOCKED"):
        raise H01DataBlocked(str(scores))
    pred = pred.copy()
    pred["year"] = pred["trade_date"].str[:4]
    pred["paired_improvement"] = pred["baseline_abs_error"] - pred["h01_abs_error"]
    years = pred.groupby("year", as_index=False).agg(
        sample_days=("paired_improvement", "size"),
        baseline_mae=("baseline_abs_error", "mean"),
        h01_mae=("h01_abs_error", "mean"),
        paired_mae_improvement=("paired_improvement", "mean"),
        h01_better_fraction=("paired_improvement", lambda s: float((s > 0).mean())),
    )
    bootstrap = {
        "5_trading_days": paired_block_interval(pred["paired_improvement"], 5),
        "20_trading_days": paired_block_interval(pred["paired_improvement"], 20),
    }
    report = {
        "status": "BLOCKED_PROMOTION_SOURCE_COUNT_MISMATCH"
            if mismatch_fraction > FROZEN_SOURCE_MISMATCH_CAP
            else "EXPLORATORY_NOT_VALIDATED",
        "first_prediction": pred["trade_date"].iloc[0],
        "last_prediction": pred["trade_date"].iloc[-1],
        "audited_dates": len(audit),
        "source_count_mismatch_days": mismatches,
        "source_mismatch_fraction": mismatch_fraction,
        "frozen_source_mismatch_cap": FROZEN_SOURCE_MISMATCH_CAP,
        "quarantined_days": qdays,
        "quarantine_rule": "exclude disputed date and next three trading sessions",
        "forecast": scores,
        "paired_block_bootstrap_ci": bootstrap,
        "confidence_interval_contains_zero": {
            k: a <= 0 <= b for k, (a, b) in bootstrap.items()
        },
        "holdout_2026_07_01_to_09_28_used": False,
        "equity_backtest_performed": False,
        "actual_investor_profit_observed": False,
        "causal_psychology_proven": False,
        "interpretation": (
            "This robustness run remains exploratory. A source-quality "
            "threshold breach blocks strategy promotion even if model MAE improves. "
            "No after-cost executable buy/sell strategy is tested."
        ),
    }
    return report, pred, years, x


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--joined", required=True)
    p.add_argument("--audit", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        joined = pd.read_parquet(args.joined)
        audit = pd.read_csv(args.audit, dtype={"trade_date": str})
        report, pred, years, joined_quarantined = analyze(joined, audit)
        pred.to_csv(out / "h01_quarantined_predictions.csv", index=False)
        years.to_csv(out / "h01_quarantined_by_year.csv", index=False)
        joined_quarantined.loc[
            joined_quarantined["count_audit_quarantine"],
            ["trade_date", "count_audit_quarantine"],
        ].to_csv(out / "h01_quarantined_dates.csv", index=False)
        result = report
    except (H01DataBlocked, ValueError, KeyError, FileNotFoundError) as exc:
        result = {"status": "BLOCKED_NO_VALID_FORECAST", "reason": str(exc)}
    (out / "h01_robustness_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if result["status"] == "BLOCKED_NO_VALID_FORECAST" else 0


if __name__ == "__main__":
    raise SystemExit(main())
