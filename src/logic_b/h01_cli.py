"""Run H01-A on audited local XGB historical evidence.

Usage:
  python -m logic_b.h01_cli --data-root data-xgb \
      --start 2024-09-30 --end 2026-06-30 --out runs/h01-a
  # Once a *separately engineered and executable* synthetic cohort ledger exists:
  python -m logic_b.h01_cli --data-root data-xgb \
      --start 2024-09-30 --end 2026-06-30 --out runs/h01-a \
      --cohort-equity runs/cohort/momentum_equity.parquet --cohort-id momentum_proxy
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .behavioral import build_feedback_features
from .b0_feedback import b0_equity_to_feedback_ledger
from .h01_data_audit import audit_xgb_limit_up_counts
from .h01_activity import (
    H01DataBlocked, expanding_window_h01, join_feedback_activity,
    limitup_continuation, write_h01_report,
)
from .storage import LocalParquetStore


FROZEN_DEV_END = "2026-06-30"


def _calendar(store: LocalParquetStore, start: str, end: str) -> list[str]:
    cal = store.read_all_parts("calendar")
    if cal.empty:
        raise H01DataBlocked("calendar missing: fetch-xgb-evidence first")
    col = "cal_date" if "cal_date" in cal else "trade_date"
    if col not in cal:
        raise H01DataBlocked("calendar has no recognized date field")
    values = pd.to_datetime(cal[col], errors="raise").dt.strftime("%Y%m%d")
    s = start.replace("-", "")
    e = end.replace("-", "")
    days = sorted(set(value for value in values if s <= value <= e))
    if len(days) < 2:
        raise H01DataBlocked("not enough trading sessions in requested range")
    return days


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="H01-A prequential psychology-proxy test")
    parser.add_argument("--data-root", default="data-xgb")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out", default="runs/h01-a")
    parser.add_argument("--audit-market-summary", action="store_true", help="check pool counts against vendor closing indicator; block mismatches")
    parser.add_argument("--cohort-equity", help="Versioned, executable cohort daily ledger (.csv/.parquet)")
    parser.add_argument("--b0-daily-equity", help="B0 daily_equity.parquet as limited follower proxy")
    parser.add_argument("--initial-cash", type=float, help="Original B0 starting cash; mandatory with --b0-daily-equity")
    parser.add_argument("--cohort-id", default="momentum_proxy")
    parser.add_argument("--lookback", type=int, default=3)
    parser.add_argument("--min-train", type=int, default=120)
    parser.add_argument("--min-test", type=int, default=40)
    args = parser.parse_args(argv)
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)

    try:
        if (pd.to_datetime(args.end) > pd.Timestamp(FROZEN_DEV_END)
                or pd.to_datetime(args.start) > pd.to_datetime(args.end)):
            raise H01DataBlocked(
                "development-only; original 2026-07-01..2026-09-28 holdout "
                "cannot be quietly unlocked for new H01 tuning"
            )
        store = LocalParquetStore(args.data_root)
        days = _calendar(store, args.start, args.end)
        activity = limitup_continuation(store, days)
        activity.to_parquet(root / "h01_market_activity.parquet", index=False)
        if args.audit_market_summary:
            scope_report, scope_table = audit_xgb_limit_up_counts(store, days)
            scope_table.to_parquet(root / "h01_source_count_audit.parquet", index=False)
            (root / "h01_source_count_audit.json").write_text(
                json.dumps(scope_report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if scope_report["status"] != "COUNT_CONSISTENT":
                raise H01DataBlocked(
                    "market scope count audit failed: " + scope_report["status"]
                )
        if not args.cohort_equity and not args.b0_daily_equity:
            status = {
                "status": "BLOCKED_MISSING_EXECUTABLE_COHORT_LEDGER",
                "audited_limitup_days": len(days),
                "last_day": days[-1],
                "activity_artifact": str(root / "h01_market_activity.parquet"),
                "note": (
                    "Limit-up continuation is not identifiable investor psychology. "
                    "A separately time-correct, fee-inclusive and executable "
                    "strategy-cohort return ledger is mandatory before H01 testing."
                ),
            }
            (root / "h01_readiness.json").write_text(
                json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 2

        if args.cohort_equity and args.b0_daily_equity:
            raise H01DataBlocked("choose one cohort ledger source")
        if args.b0_daily_equity:
            if args.initial_cash is None:
                raise H01DataBlocked("B0 conversion requires explicit --initial-cash")
            ledger_path = Path(args.b0_daily_equity)
            daily_equity = pd.read_parquet(ledger_path)
            cohort_id = "B0_SIMULATED_FOLLOWERS"
            ledger = b0_equity_to_feedback_ledger(
                daily_equity, initial_cash=args.initial_cash, cohort_id=cohort_id
            )
        else:
            ledger_path = Path(args.cohort_equity)
            cohort_id = args.cohort_id
            ledger = (pd.read_parquet(ledger_path)
                      if ledger_path.suffix.lower() == ".parquet"
                      else pd.read_csv(ledger_path))
        iso = pd.to_datetime(days, format="%Y%m%d").strftime("%Y-%m-%d").tolist()
        ledger = ledger.loc[
            ledger["cohort_id"].eq(cohort_id)
            & pd.to_datetime(ledger["trade_date"]).dt.strftime("%Y-%m-%d").isin(iso)
        ].copy()
        features = build_feedback_features(ledger, iso, lookback=args.lookback)
        joined = join_feedback_activity(features, activity, cohort_id)
        metrics, predictions = expanding_window_h01(
            joined, min_train_days=args.min_train, min_test_days=args.min_test
        )
        metrics["data_root"] = args.data_root
        metrics["cohort_source"] = str(ledger_path)
        metrics["cohort_id"] = cohort_id
        metrics["cohort_is_actual_investor_pnl"] = False
        write_h01_report(root, joined, metrics, predictions)
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return 2 if metrics["status"].startswith("BLOCKED") else 0
    except (H01DataBlocked, ValueError, KeyError, FileNotFoundError) as exc:
        report = {"status": "BLOCKED_DATA_INVALID", "reason": str(exc)}
        (root / "h01_readiness.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
