"""H02 fail-closed replay certification, separate from B0 structural readiness.

An empty ST/suspension table is only a verified negative observation when its
manifest attests an independent point-in-time status provider. Derived price
bands and D-1 name-inferred ST/halts are insufficient for net-equity claims.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .storage import LocalParquetStore


APPROVED_STATUS_PROVIDER = "TushareProvider"
APPROVED_LIMIT_PROVIDER = "TushareProvider"
CUT_OFF = "20260630"


def _manifest_source(store: LocalParquetStore, dataset: str, day: str) -> str | None:
    if not store.exists(dataset, day) or not store.verify(dataset, day):
        return None
    path = store.manifest_path(dataset, day)
    record = json.loads(path.read_text(encoding="utf-8"))
    return record.get("metadata", {}).get("source")


def inspect_h02_executable_provenance(
    store: LocalParquetStore, trade_dates: list[str]
) -> dict:
    if not trade_dates or trade_dates != sorted(set(trade_dates)):
        raise ValueError("nonempty sorted unique dates required")
    if any(len(x) != 8 or not x.isdigit() for x in trade_dates):
        raise ValueError("invalid date token")
    if trade_dates[-1] > CUT_OFF:
        raise ValueError("protected B0 holdout: H02 execution cannot read dates after 2026-06-30")

    reasons = []
    candidate_days = 0
    checked_minutes = 0
    unmatched_limits = 0

    for i, day in enumerate(trade_dates):
        for ds, allowed in (
            ("limit_prices", APPROVED_LIMIT_PROVIDER),
            ("stock_st", APPROVED_STATUS_PROVIDER),
            ("suspend", APPROVED_STATUS_PROVIDER),
        ):
            actual = _manifest_source(store, ds, day)
            if actual != allowed:
                reasons.append({
                    "date": day, "dataset": ds,
                    "issue": "missing_or_unapproved_provenance",
                    "actual_source": actual,
                    "required_source": allowed
                })
        if not i:
            continue
        prior = trade_dates[i - 1]
        if not store.exists("limit_up", prior) or not store.verify("limit_up", prior):
            reasons.append({"date": prior, "dataset": "limit_up", "issue": "missing_previous_pool"})
            continue
        pool = store.read_frame("limit_up", prior)
        if pool.empty:
            continue
        if "ts_code" not in pool or pool["ts_code"].isna().any() or pool["ts_code"].duplicated().any():
            reasons.append({"date": prior, "dataset": "limit_up", "issue": "invalid_candidate_ids"})
            continue
        if _manifest_source(store, "limit_prices", day) == APPROVED_LIMIT_PROVIDER:
            lp = store.read_frame("limit_prices", day)
            available = set(lp.ts_code.astype(str)) if "ts_code" in lp else set()
        else:
            available = set()
        for code in pool.ts_code.astype(str):
            candidate_days += 1
            if code not in available:
                unmatched_limits += 1
            part = f"{day}/{code}"
            if not store.exists("minute_1m", part) or not store.verify("minute_1m", part):
                reasons.append({"date": day, "symbol": code, "dataset": "minute_1m", "issue": "missing_or_invalid_manifest"})
                continue
            b = store.read_frame("minute_1m", part)
            if b.empty or "trade_time" not in b:
                reasons.append({"date": day, "symbol": code, "dataset": "minute_1m", "issue": "missing_timed_bars"})
                continue
            t = pd.to_datetime(b.trade_time, errors="coerce")
            if t.isna().any() or (t.dt.strftime("%Y%m%d") != day).any() or not t.is_unique:
                reasons.append({"date": day, "symbol": code, "dataset": "minute_1m", "issue": "wrong_or_duplicate_timestamps"})
                continue
            checked_minutes += 1

    if unmatched_limits:
        reasons.append({"dataset": "limit_prices", "issue": "candidate_official_limit_rows_missing",
                        "symbol_days": unmatched_limits})
    return {
        "status": "READY_FOR_FURTHER_EXECUTION_AUDIT" if not reasons else "BLOCKED_UNCERTIFIED_EXECUTION_INPUTS",
        "trade_days": len(trade_dates),
        "candidate_symbol_days": candidate_days,
        "minute_date_verified_symbol_days": checked_minutes,
        "candidate_official_limit_rows_missing": unmatched_limits,
        "failed_evidence_items": len(reasons),
        "first_blockers": reasons[:30],
        "source_provenance_gate_passed": not reasons,
        "net_equity_validated": False,
        "caution": "Provenance readiness only; do not mistake it for complete simulated trading proof.",
        "source_allowlist": {
            "stk_limit": APPROVED_LIMIT_PROVIDER, "stock_st": APPROVED_STATUS_PROVIDER,
            "suspend": APPROVED_STATUS_PROVIDER
        },
    }
