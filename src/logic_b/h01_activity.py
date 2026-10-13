"""H01-A: observable limit-up continuation and expanding-window hypothesis test.

IMPORTANT: close-to-close limit-up membership is a MARKET ACTIVITY PROXY,
not evidence identifying investors or their actual realized profits.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .storage import LocalParquetStore


class H01DataBlocked(ValueError):
    """Required point-in-time observations are unavailable or inconsistent."""


def limitup_continuation(
    store: LocalParquetStore, trade_dates: Sequence[str],
) -> pd.DataFrame:
    """Full historical limit-up membership -> next-day repeat fraction.

    Every date must have an existing, SHA-verified market-wide limit_up
    partition. Empty partitions are valid and distinct from missing ones.
    Output is descriptive and is not a strategy return.
    """
    days = list(trade_dates)
    if len(days) < 2 or days != sorted(set(days)):
        raise H01DataBlocked("calendar must have >=2 sorted unique YYYYMMDD dates")
    sets = []
    for day in days:
        if len(day) != 8 or not day.isdigit():
            raise H01DataBlocked(f"invalid trading date: {day}")
        if not store.exists("limit_up", day) or not store.verify("limit_up", day):
            raise H01DataBlocked(f"missing/invalid limit_up manifest: {day}")
        frame = store.read_frame("limit_up", day)
        if frame.empty:
            sets.append(set())
            continue
        if "ts_code" not in frame.columns:
            raise H01DataBlocked(f"ts_code missing in limit_up: {day}")
        codes = frame["ts_code"]
        if codes.isna().any() or (codes.astype(str).str.strip() == "").any():
            raise H01DataBlocked(f"invalid symbol in limit_up: {day}")
        if codes.astype(str).duplicated().any():
            raise H01DataBlocked(f"duplicate symbol in limit_up: {day}")
        if "trade_date" in frame:
            observed = pd.to_datetime(frame["trade_date"], errors="coerce")
            if observed.isna().any() or (observed.dt.strftime("%Y%m%d") != day).any():
                raise H01DataBlocked(f"date mismatch in limit_up: {day}")
        sets.append(set(codes.astype(str)))
    rows = []
    for i, day in enumerate(days):
        now = sets[i]
        prior = sets[i - 1] if i else set()
        denominator = len(prior)
        rows.append({
            "trade_date": pd.to_datetime(day, format="%Y%m%d").strftime("%Y-%m-%d"),
            "limitup_count": len(now),
            "prior_limitup_count": denominator if i else np.nan,
            "repeat_count": len(now & prior) if i else np.nan,
            "repeat_rate": len(now & prior) / denominator if i and denominator else np.nan,
            # Exchange-close-derived observation; source publication may be later.
            # At next day's 09:35 it is eligible only if the source is confirmed.
            "label_observed_at": (
                pd.to_datetime(day, format="%Y%m%d").strftime("%Y-%m-%d")
                + "T16:00:00+08:00"
            ),
        })
    return pd.DataFrame(rows)


def join_feedback_activity(
    feedback: pd.DataFrame, activity: pd.DataFrame, cohort_id: str,
) -> pd.DataFrame:
    """Join only lagged feedback with same-day, AFTER-CHECKPOINT outcome.

    'repeat_rate' on date D is a label NOT a D 09:35 trading input.
    Previous day's repeat rate is allowed, with label_observed_at audit.
    """
    required_f = {"cohort_id", "trade_date", "asof_at", "status"}
    if ("lagged_compound_return" not in feedback and
            "h01_experience_proxy" not in feedback):
        raise H01DataBlocked("missing explicitly named H01 experience feature")
    required_a = {
        "trade_date", "limitup_count", "prior_limitup_count",
        "repeat_rate", "label_observed_at",
    }
    if required_f - set(feedback) or required_a - set(activity):
        raise H01DataBlocked("required feature/activity fields missing")
    f = feedback[feedback["cohort_id"] == cohort_id].copy()
    if "h01_experience_proxy" not in f:
        f["h01_experience_proxy"] = f["lagged_compound_return"]
    if f.empty:
        raise H01DataBlocked(f"cohort not found: {cohort_id}")
    a = activity.copy().sort_values("trade_date")
    if f["trade_date"].duplicated().any() or a["trade_date"].duplicated().any():
        raise H01DataBlocked("duplicate feature or activity dates")
    if set(f["trade_date"]) != set(a["trade_date"]):
        raise H01DataBlocked("calendar mismatch; no implicit inner join")
    a["prior_repeat_rate"] = a["repeat_rate"].shift(1)
    a["prior_label_observed_at"] = a["label_observed_at"].shift(1)
    a["prior_day_limitup_count"] = a["limitup_count"].shift(1)
    merged = f.merge(a, on="trade_date", how="left", validate="one_to_one")
    asof = pd.to_datetime(merged["asof_at"], utc=True)
    label = pd.to_datetime(merged["label_observed_at"], utc=True)
    prior_label = pd.to_datetime(merged["prior_label_observed_at"], utc=True)
    if (label <= asof).any():
        raise H01DataBlocked("same-day future outcome is not future: clock/schema problem")
    ready = merged["status"].eq("READY")
    legal_prior = prior_label.notna() & (prior_label <= asof)
    # A row can only be evaluated if the prior observable activity is known.
    if (ready & ~legal_prior).any():
        raise H01DataBlocked("prior-day activity not published at checkpoint")
    merged["evaluation_ready"] = (
        ready &
        merged["repeat_rate"].notna() &
        merged["prior_repeat_rate"].notna() &
        merged["prior_day_limitup_count"].notna() &
        merged["h01_experience_proxy"].notna()
    )
    return merged


def _fit_predict(train: pd.DataFrame, test: pd.Series,
                 cols: list[str], ridge: float = 1.0) -> float:
    x = train[cols].to_numpy(dtype=float)
    mu = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-12] = 1.0
    design = np.column_stack((np.ones(len(train)), (x - mu) / scale))
    y = train["repeat_rate"].to_numpy(dtype=float)
    penalty = np.eye(design.shape[1], dtype=float) * ridge
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    z = np.r_[1.0, (test[cols].to_numpy(dtype=float) - mu) / scale]
    return float(np.clip(z @ beta, 0.0, 1.0))


def expanding_window_h01(
    joined: pd.DataFrame, *, min_train_days: int = 120, min_test_days: int = 40,
) -> tuple[dict, pd.DataFrame]:
    """Paired H01-A descriptive forecast test; NOT net-equity proof.

    Baseline: prior-day repeat rate and prior-day limit-up count.
    Enhanced: baseline + psychologically motivated lagged cohort return.
    Fits at D on rows with observed outcomes before D's 09:35 checkpoint.
    """
    if min_train_days < 10 or min_test_days < 5:
        raise ValueError("too-short split is unsuitable")
    x = joined.copy().sort_values("trade_date").reset_index(drop=True)
    if x["trade_date"].duplicated().any():
        raise H01DataBlocked("duplicate evaluation dates")
    x["log_prior_count"] = np.log1p(pd.to_numeric(
        x["prior_day_limitup_count"], errors="coerce"
    ))
    bcols = ["prior_repeat_rate", "log_prior_count"]
    hcols = bcols + ["h01_experience_proxy"]
    usable = x.loc[x["evaluation_ready"]].copy()
    for col in ["repeat_rate", *hcols]:
        if not np.isfinite(pd.to_numeric(usable[col], errors="coerce")).all():
            raise H01DataBlocked(f"non-finite input: {col}")
    if len(usable) < min_train_days + min_test_days:
        return ({
            "status": "BLOCKED_INSUFFICIENT_HISTORY",
            "ready_days": len(usable),
            "minimum_needed": min_train_days + min_test_days,
            "note": "No profitability or psychology claim possible.",
        }, pd.DataFrame())
    # Missing intermediate observations are reported; no synthetic zeros.
    pred = []
    for i in range(min_train_days, len(usable)):
        current = usable.iloc[i]
        prior = usable.iloc[:i]
        ctime = pd.to_datetime(current["asof_at"], utc=True)
        if (pd.to_datetime(prior["label_observed_at"], utc=True) > ctime).any():
            raise H01DataBlocked("outcome publication exceeds prediction time")
        baseline = _fit_predict(prior, current, bcols)
        enhanced = _fit_predict(prior, current, hcols)
        pred.append({
            "trade_date": current["trade_date"],
            "cohort_id": current["cohort_id"],
            "observed_repeat_rate": float(current["repeat_rate"]),
            "baseline_prediction": baseline,
            "h01_prediction": enhanced,
            "baseline_abs_error": abs(float(current["repeat_rate"]) - baseline),
            "h01_abs_error": abs(float(current["repeat_rate"]) - enhanced),
        })
    out = pd.DataFrame(pred)
    if len(out) < min_test_days:
        raise H01DataBlocked("insufficient held-forward days")
    bmae = float(out["baseline_abs_error"].mean())
    hmae = float(out["h01_abs_error"].mean())
    return ({
        "status": "EXPLORATORY_IMPROVEMENT" if hmae < bmae else "NO_IMPROVEMENT",
        "test_days": len(out),
        "ready_days": len(usable),
        "excluded_days": int(len(x) - len(usable)),
        "baseline_mae": bmae,
        "h01_mae": hmae,
        "paired_mae_improvement": bmae - hmae,
        "h01_better_fraction": float(
            (out["h01_abs_error"] < out["baseline_abs_error"]).mean()
        ),
        "scope": "historical limit-up repeat ratio ONLY; no identified people, no net-equity result",
        "statistical_claim": "exploratory; no causal claim, multiplicity adjustment, or untouched external holdout",
    }, out)


def write_h01_report(out_dir: str | Path, joined: pd.DataFrame,
                     metrics: dict, predictions: pd.DataFrame) -> None:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    joined.to_parquet(path / "h01_joined.parquet", index=False)
    predictions.to_parquet(path / "h01_predictions.parquet", index=False)
    (path / "h01_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
