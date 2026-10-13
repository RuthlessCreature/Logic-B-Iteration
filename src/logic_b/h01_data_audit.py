"""Independent consistency checks for Xuangubao market-wide event-list evidence.

File hashes catch corruption, not provider-side truncation. This second source
indicator check flags count mismatch; it cannot itself prove population coverage.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .h01_activity import H01DataBlocked
from .storage import LocalParquetStore


def audit_xgb_limit_up_counts(
    store: LocalParquetStore, trade_dates: Sequence[str],
) -> tuple[dict, pd.DataFrame]:
    if not trade_dates:
        raise H01DataBlocked("no dates to audit")
    rows = []
    for day in trade_dates:
        for ds in ("limit_up", "market_indicator"):
            if not store.exists(ds, day) or not store.verify(ds, day):
                raise H01DataBlocked(f"missing/corrupt {ds} partition {day}")
        pool = store.read_frame("limit_up", day)
        snap = store.read_frame("market_indicator", day)
        if snap.empty or "limit_up_count" not in snap.columns:
            rows.append({
                "trade_date": day, "pool_count": len(pool),
                "vendor_close_count": np.nan, "abs_difference": np.nan,
                "status": "BLOCKED_SUMMARY_MISSING",
            })
            continue
        order_col = ("timestamp" if "timestamp" in snap.columns
                     else "event_time" if "event_time" in snap.columns else None)
        if order_col is None:
            rows.append({
                "trade_date": day, "pool_count": len(pool),
                "vendor_close_count": np.nan, "abs_difference": np.nan,
                "status": "BLOCKED_SUMMARY_UNTIMED",
            })
            continue
        snap = snap.sort_values(order_col)
        values = pd.to_numeric(snap["limit_up_count"], errors="coerce")
        observed = values.iloc[-1]
        if not np.isfinite(observed) or observed < 0 or observed != int(observed):
            rows.append({
                "trade_date": day, "pool_count": len(pool),
                "vendor_close_count": np.nan, "abs_difference": np.nan,
                "status": "BLOCKED_COUNT_INVALID",
            })
            continue
        official = int(observed)
        rows.append({
            "trade_date": day, "pool_count": len(pool),
            "vendor_close_count": official,
            "abs_difference": abs(len(pool) - official),
            "status": "MATCH" if len(pool) == official else "SOURCE_DEFINITION_REVIEW",
        })
    out = pd.DataFrame(rows)
    counts = out["status"].value_counts().to_dict()
    mismatched = out.loc[out["status"] == "SOURCE_DEFINITION_REVIEW"]
    blocked = out.loc[out["status"].str.startswith("BLOCKED")]
    status = (
        "BLOCKED_SOURCE_SUMMARY_MISSING" if not blocked.empty
        else "REVIEW_POOL_COUNT_DISCREPANCY" if not mismatched.empty
        else "COUNT_CONSISTENT"
    )
    report = {
        "status": status,
        "trade_days": len(out),
        "count_consistent_days": int(counts.get("MATCH", 0)),
        "definition_review_days": int(counts.get("SOURCE_DEFINITION_REVIEW", 0)),
        "missing_or_invalid_summary_days": len(blocked),
        "max_abs_difference": (
            int(mismatched["abs_difference"].max()) if not mismatched.empty else 0
        ),
        "note": (
            "Agreement of a vendor event list and its market summary is NOT "
            "independent confirmation of complete market-wide coverage. "
            "Disagreement requires investigating definitions before using "
            "the repeat ratio as a population-wide proxy."
        ),
    }
    return report, out
