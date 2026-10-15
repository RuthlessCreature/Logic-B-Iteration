"""Build leakage-safe H02 stock-day features from the five pinned Tier-D archives.

The row-level matrix is derived research data and must stay in ignored local
storage while provider redistribution terms are unresolved. Public outputs are
aggregate tables only. No provider calls, PIT certification, or trading returns.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
import statistics
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))
from h02_first_empirical_result import (  # noqa: E402
    END, START, EmpiricalDataError, load_market_events,
)
TRAIN_END = "20250630"
VALIDATION_END = "20251231"

_AUDITOR_PATH = SCRIPTS / "h02_audit_dev_artifact_coverage.py"
_SPEC = importlib.util.spec_from_file_location("h02_feature_archive_auditor", _AUDITOR_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("cannot load pinned archive auditor")
_AUDITOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_AUDITOR)

AUX_DATASETS = ("limit_break", "market_indicator", "theme_limit_up")
PIT_STATUS = "PIT_UNVERIFIED"
BOOTSTRAP_REPS = 1000
BLOCK_DAYS = 5

FIELD_DICTIONARY = {
    "candidate_date": "D-1 trading date; candidate belongs to that date's vendor limit_up event pool.",
    "outcome_date": "D trading date, the prediction target date.",
    "vendor_streak_length": "Consecutive prior calendar sessions ending D-1 with this code in vendor limit_up; not official close-limit board height.",
    "vendor_streak_group": "vendor_streak_length bucket: 1, 2, or 3+.",
    "limit_up_count_3": "Number of appearances in vendor limit_up over D-1 and prior two sessions.",
    "limit_up_count_5": "Number of appearances in vendor limit_up over D-1 and prior four sessions.",
    "limit_down_count_5": "Number of appearances in vendor limit_down over D-1 and prior four sessions.",
    "days_since_limit_down": "Trading-session distance from D-1 to most recent prior vendor limit_down event; null means none in retained history.",
    "recent_limit_up_acceleration": "limit_up appearances in the latest 3 sessions minus the preceding 3 sessions, all ending no later than D-1.",
    "vendor_limit_up_count": "Number of unique codes in D-1 vendor limit_up pool.",
    "vendor_limit_down_count": "Number of unique codes in D-1 vendor limit_down pool.",
    "vendor_limit_break_count": "Number of unique codes in D-1 vendor limit_break event pool.",
    "limit_up_pool_change_3_sessions": "D-1 vendor limit_up pool size minus size three sessions earlier.",
    "limit_up_pool_change_5_sessions": "D-1 vendor limit_up pool size minus size five sessions earlier.",
    "lagged_continuation_rate": "Prior-session vendor limit_up overlap divided by previous session's candidate pool size, available by event date only in the constructed chronology.",
    "lagged_continuation_change_3_sessions": "Mean of latest three prior-session continuation rates minus preceding three; no D or later outcomes.",
    "rise_fall_event_ratio": "D-1 final market_indicator rise_count / max(fall_count, 1).",
    "theme_hhi": "Herfindahl concentration of vendor theme assignments among D-1 candidate codes; multi-theme assignments split each code's weight evenly.",
    "continuation_D": "D vendor limit_up pool membership; outcome only.",
    "down_next_D": "D vendor limit_down pool membership; outcome only.",
    "down_three_D_to_D2": "Any vendor limit_down membership over D,D+1,D+2; null unless the entire window stays within its research phase.",
}


def _period(day: str) -> str:
    if day <= TRAIN_END:
        return "train"
    if day <= VALIDATION_END:
        return "validation_2025H2"
    return "forward_2026H1"


def _load_auxiliary(paths: list[Path]) -> dict[str, Any]:
    expected = set(_AUDITOR.TRUSTED_ARCHIVE_SHA256)
    if len({p.name for p in paths}) != len(paths) or {p.name for p in paths} != expected:
        raise EmpiricalDataError("input must be exactly the five trusted development archives")
    output: dict[str, Any] = {
        "limit_break": {}, "market_indicator": {}, "themes": {},
        "aux_hashes": {ds: {} for ds in AUX_DATASETS},
        "archive_sha256": {}, "archive_manifest_count": 0,
        "archive_manifest_verified": 0,
    }
    for path in sorted((Path(p) for p in paths), key=lambda p: p.name):
        raw_archive = _AUDITOR.trusted_archive_bytes(path)
        output["archive_sha256"][path.name] = hashlib.sha256(raw_archive).hexdigest()
        with zipfile.ZipFile(io.BytesIO(raw_archive)) as archive:
            members = set(archive.namelist())
            _AUDITOR.preflight_raw_member_names(members)
            for member in sorted(n for n in members if n.startswith("manifests/") and n.endswith(".json")):
                parts = member.split("/")
                if len(parts) != 3 or parts[1] not in AUX_DATASETS:
                    continue
                dataset = parts[1]
                manifest = json.loads(archive.read(member).decode("utf-8"))
                day = str(manifest.get("partition", ""))
                if len(day) != 8 or not day.isdigit() or day > END:
                    raise EmpiricalDataError("protected/post-development auxiliary partition")
                target_key = "themes" if dataset == "theme_limit_up" else dataset
                if day in output[target_key]:
                    raise EmpiricalDataError(f"duplicate auxiliary partition {dataset}/{day}")
                raw_name = f"raw/{dataset}/{day}.parquet"
                if raw_name not in members:
                    raise EmpiricalDataError(f"missing auxiliary raw partition: {raw_name}")
                raw = archive.read(raw_name)
                output["archive_manifest_count"] += 1
                digest = hashlib.sha256(raw).hexdigest()
                if digest != manifest.get("sha256"):
                    raise EmpiricalDataError(f"auxiliary partition hash mismatch: {raw_name}")
                output["archive_manifest_verified"] += 1
                frame = pd.read_parquet(io.BytesIO(raw))
                if len(frame) != int(manifest.get("rows", -1)):
                    raise EmpiricalDataError(f"auxiliary row count mismatch: {raw_name}")
                output["aux_hashes"][dataset][day] = digest
                if dataset == "limit_break":
                    if len(frame) and not {"trade_date", "ts_code"}.issubset(frame.columns):
                        raise EmpiricalDataError(f"limit_break schema mismatch: {day}")
                    if len(frame):
                        dates = set(frame.trade_date.astype(str))
                        codes = frame.ts_code.astype("string")
                        if dates != {day} or codes.isna().any() or codes.duplicated().any():
                            raise EmpiricalDataError(f"invalid limit_break rows: {day}")
                    output["limit_break"][day] = set(frame.ts_code.astype(str)) if len(frame) else set()
                elif dataset == "market_indicator":
                    required = {"trade_date", "limit_up_count", "limit_down_count", "limit_up_broken_count", "rise_count", "fall_count"}
                    if not required.issubset(frame.columns) or frame.empty:
                        raise EmpiricalDataError(f"market_indicator schema mismatch: {day}")
                    time_col = "event_time" if "event_time" in frame else "timestamp" if "timestamp" in frame else None
                    if time_col is None:
                        raise EmpiricalDataError(f"market_indicator timestamp missing: {day}")
                    times = pd.to_datetime(frame[time_col], errors="coerce", utc=True)
                    if times.isna().any() or times.duplicated().any():
                        raise EmpiricalDataError(f"invalid market_indicator timeline: {day}")
                    if set(frame.trade_date.astype(str)) != {day}:
                        raise EmpiricalDataError(f"market_indicator date mismatch: {day}")
                    final = frame.loc[times.idxmax()]
                    values = {}
                    for col in ("limit_up_count", "limit_down_count", "limit_up_broken_count", "rise_count", "fall_count", "market_temperature", "yesterday_limit_up_avg_pcp", "limit_up_broken_ratio"):
                        if col in frame:
                            value = pd.to_numeric(pd.Series([final[col]]), errors="coerce").iloc[0]
                            if pd.isna(value) or not math.isfinite(float(value)):
                                raise EmpiricalDataError(f"invalid market_indicator value {col}/{day}")
                            values[col] = float(value)
                    values["last_observed_at_shanghai"] = times.loc[times.idxmax()].tz_convert("Asia/Shanghai").isoformat()
                    output["market_indicator"][day] = values
                else:
                    if len(frame) and not {"trade_date", "ts_code", "theme"}.issubset(frame.columns):
                        raise EmpiricalDataError(f"theme_limit_up schema mismatch: {day}")
                    if len(frame):
                        if set(frame.trade_date.astype(str)) != {day} or frame.ts_code.isna().any():
                            raise EmpiricalDataError(f"invalid theme_limit_up rows: {day}")
                        for code, theme in zip(frame.ts_code.astype(str), frame.theme.astype("string")):
                            if pd.isna(theme) or not str(theme).strip():
                                continue
                            output["themes"].setdefault(day, {}).setdefault(code, set()).add(str(theme))
                    output["themes"].setdefault(day, {})
    for dataset in AUX_DATASETS:
        expected_days = set(output["aux_hashes"][dataset])
        if not expected_days:
            raise EmpiricalDataError(f"auxiliary dataset missing: {dataset}")
    return output


def _market_continuation(up: dict[str, set[str]], days: list[str], idx: int) -> float | None:
    if idx <= 0:
        return None
    prior = up[days[idx - 1]]
    if not prior:
        return None
    return len(prior & up[days[idx]]) / len(prior)


def _feature_rows(data: dict[str, Any], aux: dict[str, Any]) -> list[dict[str, Any]]:
    days = data["calendar_days"]
    if not isinstance(days, list) or days != sorted(set(days)) or any(not isinstance(d, str) or len(d) != 8 or not d.isdigit() or d > END for d in days):
        raise EmpiricalDataError("calendar is invalid or crosses the protected/post-development cutoff")
    if set(data["limit_up"]) != set(days) or set(data["limit_down"]) != set(days):
        raise EmpiricalDataError("event pool/calendar partition coverage mismatch")
    up, down = data["limit_up"], data["limit_down"]
    if not (set(days) <= set(aux["limit_break"]) and set(days) <= set(aux["market_indicator"]) and set(days) <= set(aux["themes"])):
        raise EmpiricalDataError("auxiliary event/calendar partition coverage mismatch")
    index = {day: i for i, day in enumerate(days)}
    all_cont = {d: _market_continuation(up, days, i) for i, d in enumerate(days)}
    result: list[dict[str, Any]] = []
    for outcome_day in days:
        if not START <= outcome_day <= END:
            continue
        i = index[outcome_day]
        if i < 6:
            raise EmpiricalDataError(f"insufficient historical context for {outcome_day}")
        prior_i = i - 1
        candidate_day = days[prior_i]
        cohort = up[candidate_day]
        if not cohort:
            continue
        segment = _period(outcome_day)
        segment_end = {"train": TRAIN_END, "validation_2025H2": VALIDATION_END, "forward_2026H1": END}[segment]
        future = days[i:i + 3]
        y3_ok = len(future) == 3 and future[-1] <= segment_end
        future_down = set().union(*(down[d] for d in future)) if y3_ok else set()
        market = aux["market_indicator"][candidate_day]
        market_up_n = len(cohort)
        market_down_n = len(down[candidate_day])
        themes = aux["themes"][candidate_day]
        assigned: dict[str, list[str]] = {}
        for code in cohort:
            ts = sorted(themes.get(code, set()))
            if ts:
                assigned[code] = ts
        theme_counts: defaultdict[str, float] = defaultdict(float)
        for labels in assigned.values():
            contribution = 1.0 / len(labels)
            for label in labels:
                theme_counts[label] += contribution
        total_theme_weight = sum(theme_counts.values())
        theme_hhi = (sum((v / total_theme_weight) ** 2 for v in theme_counts.values())
                     if total_theme_weight else None)
        candidate_up5_counts = []
        for code in cohort:
            count = sum(code in up[days[k]] for k in range(prior_i - 4, prior_i + 1))
            candidate_up5_counts.append(count)
        peer_up5_mean = statistics.fmean(candidate_up5_counts) if candidate_up5_counts else 0.0
        lag_last3 = [all_cont.get(days[k]) for k in range(prior_i - 2, prior_i + 1)]
        lag_prior3 = [all_cont.get(days[k]) for k in range(prior_i - 5, prior_i - 2)]
        clean_last3 = [v for v in lag_last3 if v is not None]
        clean_prior3 = [v for v in lag_prior3 if v is not None]
        lag_change = statistics.fmean(clean_last3) - statistics.fmean(clean_prior3) if clean_last3 and clean_prior3 else None
        for code in sorted(cohort):
            streak = 0
            for k in range(prior_i, -1, -1):
                if code not in up[days[k]]:
                    break
                streak += 1
            count_up3 = sum(code in up[days[k]] for k in range(prior_i - 2, prior_i + 1))
            count_up5 = sum(code in up[days[k]] for k in range(prior_i - 4, prior_i + 1))
            count_down5 = sum(code in down[days[k]] for k in range(prior_i - 4, prior_i + 1))
            days_since_down = next((prior_i - k for k in range(prior_i, -1, -1) if code in down[days[k]]), None)
            recent3 = count_up3
            previous3 = sum(code in up[days[k]] for k in range(prior_i - 5, prior_i - 2))
            acceleration = recent3 - previous3
            prior_streak = streak
            y3 = int(code in future_down) if y3_ok else None
            result.append({
                "ts_code": code,
                "outcome_date": outcome_day,
                "candidate_date": candidate_day,
                "phase": segment,
                "feature_last_session": candidate_day,
                "pit_status": PIT_STATUS,
                "historical_available_at": None,
                "vendor_streak_length": streak,
                "vendor_streak_group": "1" if streak == 1 else "2" if streak == 2 else "3+",
                "limit_up_count_3": int(count_up3),
                "limit_up_count_3_group": str(count_up3),
                "limit_up_count_5": int(count_up5),
                "limit_up_count_5_group": str(count_up5) if count_up5 < 3 else "3+",
                "limit_down_count_5": int(count_down5),
                "limit_down_count_5_group": "0" if count_down5 == 0 else "1+",
                "days_since_limit_down": days_since_down,
                "days_since_limit_down_group": "0-2" if days_since_down is not None and days_since_down <= 2 else "3-5" if days_since_down is not None and days_since_down <= 5 else ">5_OR_NEVER",
                "recent_limit_up_acceleration": int(acceleration),
                "recent_limit_up_acceleration_group": "WEAKENING" if acceleration < 0 else "STABLE" if acceleration == 0 else "ACCELERATING",
                "vendor_prior_nonconsecutive_entry": bool(prior_streak == 1),
                "market_relative_up5": float(count_up5 - peer_up5_mean),
                "market_relative_up5_group": "BELOW_PEER_MEAN" if count_up5 < peer_up5_mean else "AT_OR_ABOVE_PEER_MEAN",
                "market_transition_group": ("HIGH_TO_HIGH" if len(up[days[prior_i - 1]]) > 83 else "LOW_TO_HIGH") if market_up_n > 83 else ("HIGH_TO_LOW" if len(up[days[prior_i - 1]]) > 83 else "LOW_TO_LOW"),
                "vendor_limit_up_count": market_up_n,
                "vendor_limit_down_count": market_down_n,
                "vendor_limit_break_count": len(aux["limit_break"][candidate_day]),
                "limit_up_pool_change_3_sessions": market_up_n - len(up[days[prior_i - 3]]),
                "limit_up_pool_change_5_sessions": market_up_n - len(up[days[prior_i - 5]]),
                "lagged_continuation_rate": all_cont.get(candidate_day),
                "lagged_continuation_change_3_sessions": lag_change,
                "market_rise_count": market.get("rise_count"),
                "market_fall_count": market.get("fall_count"),
                "rise_fall_event_ratio": market["rise_count"] / max(market["fall_count"], 1.0),
                "market_temperature": market.get("market_temperature"),
                "market_snapshot_last_observed_at": market["last_observed_at_shanghai"],
                "market_theme_assignment_coverage": len(assigned) / len(cohort),
                "theme_hhi": theme_hhi,
                "continuation_D": int(code in up[outcome_day]),
                "down_next_D": int(code in down[outcome_day]),
                "down_three_D_to_D2": y3,
                "source_candidate_limit_up_sha256": data["partition_hashes"]["limit_up"][candidate_day],
                "source_history_limit_up_sha256": ";".join(data["partition_hashes"]["limit_up"][days[k]] for k in range(prior_i - 5, prior_i + 1)),
                "source_history_limit_down_sha256": ";".join(data["partition_hashes"]["limit_down"][days[k]] for k in range(prior_i - 4, prior_i + 1)),
                "source_limit_break_sha256": aux["aux_hashes"]["limit_break"][candidate_day],
                "source_market_indicator_sha256": aux["aux_hashes"]["market_indicator"][candidate_day],
                "source_theme_limit_up_sha256": aux["aux_hashes"]["theme_limit_up"][candidate_day],
            })
    return result


def _eligible(rows: list[dict], phase: str, label: str) -> list[dict]:
    return [r for r in rows if r["phase"] == phase and r[label] is not None]


def _rate(rows: list[dict], label: str) -> tuple[int, int, float | None]:
    n = len(rows)
    k = sum(int(r[label]) for r in rows)
    return k, n, k / n if n else None


def _block_bootstrap_rate(rows: list[dict], label: str, reps: int = BOOTSTRAP_REPS, calendar_days: list[str] | tuple[str, ...] | None = None) -> list[float]:
    if not rows:
        return []
    grouped: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        grouped[row["outcome_date"]][0] += int(row[label])
        grouped[row["outcome_date"]][1] += 1
    per_day = {day: tuple(values) for day, values in grouped.items()}
    days = list(calendar_days) if calendar_days is not None else sorted(per_day)
    if any(day not in set(days) for day in per_day):
        raise ValueError("calendar_days must include every observed outcome_date")
    rng = np.random.default_rng(20261014)
    block_count = math.ceil(len(days) / BLOCK_DAYS)
    starts = rng.integers(0, len(days), size=(reps, block_count))
    offsets = np.arange(BLOCK_DAYS)
    indices = ((starts[:, :, None] + offsets[None, None, :]) % len(days)).reshape(reps, -1)[:, :len(days)]
    daily_events = np.asarray([per_day.get(day, (0, 0))[0] for day in days], dtype=np.int64)
    daily_candidates = np.asarray([per_day.get(day, (0, 0))[1] for day in days], dtype=np.int64)
    events = daily_events[indices].sum(axis=1)
    candidates = daily_candidates[indices].sum(axis=1)
    return (events[candidates > 0] / candidates[candidates > 0]).astype(float).tolist()


def _conditional_table(rows: list[dict], label: str, groupers: dict[str, tuple[str, ...]], calendar_days: list[str] | tuple[str, ...] | None = None) -> dict:
    output = {}
    all_n = len(rows)
    for name, (field, levels) in groupers.items():
        groups = []
        for level in levels:
            part = [r for r in rows if r[field] == level]
            k, n, rate = _rate(part, label)
            draws = _block_bootstrap_rate(part, label, calendar_days=calendar_days)
            groups.append({
                "level": level, "events": k, "candidate_days": n,
                "coverage": n / all_n if all_n else None, "rate": rate,
                "delta_vs_phase_overall": rate - _rate(rows, label)[2] if rate is not None and all_n else None,
                "day_block_bootstrap_95pct_ci": [float(np.quantile(draws, .025)), float(np.quantile(draws, .975))] if draws else None,
            })
        output[name] = {"field": field, "groups": groups}
    return output


GROUPERS = {
    "vendor_streak": ("vendor_streak_group", ("1", "2", "3+")),
    "limit_up_count_3": ("limit_up_count_3_group", ("1", "2", "3")),
    "limit_up_count_5": ("limit_up_count_5_group", ("1", "2", "3+")),
    "limit_down_count_5": ("limit_down_count_5_group", ("0", "1+")),
    "days_since_limit_down": ("days_since_limit_down_group", ("0-2", "3-5", ">5_OR_NEVER")),
    "recent_acceleration": ("recent_limit_up_acceleration_group", ("WEAKENING", "STABLE", "ACCELERATING")),
    "market_relative_persistence": ("market_relative_up5_group", ("BELOW_PEER_MEAN", "AT_OR_ABOVE_PEER_MEAN")),
    "breadth_fixed_83": ("breadth_group", ("LOW", "HIGH")),
    "breadth_transition_fixed_83": ("market_transition_group", ("LOW_TO_LOW", "LOW_TO_HIGH", "HIGH_TO_LOW", "HIGH_TO_HIGH")),
    "theme_concentration_train_median": ("theme_hhi_group", ("LOW", "HIGH", "UNKNOWN")),
    "streak_x_down5": ("streak_down5_group", tuple(f"{s}|{d}" for s in ("1", "2", "3+") for d in ("0", "1+"))),
    "streak_x_breadth": ("streak_breadth_group", tuple(f"{s}|{b}" for s in ("1", "2", "3+") for b in ("LOW", "HIGH"))),
}


def analyze_features(data: dict[str, Any], aux: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if data.get("archive_hashes") != aux.get("archive_sha256"):
        raise EmpiricalDataError("base and auxiliary loaders disagree on pinned archive hashes")
    rows = _feature_rows(data, aux)
    if not rows:
        raise EmpiricalDataError("no feature rows in requested development interval")
    # Breadth cut 83 is frozen from the earlier training-only market pilot;
    # theme concentration is a separate descriptive cut fitted on training X only.
    train_theme = [r["theme_hhi"] for r in rows if r["phase"] == "train" and r["theme_hhi"] is not None]
    theme_median = float(statistics.median(train_theme)) if train_theme else None
    for row in rows:
        row["breadth_group"] = "HIGH" if row["vendor_limit_up_count"] > 83 else "LOW"
        row["theme_hhi_group"] = "UNKNOWN" if row["theme_hhi"] is None or theme_median is None else "HIGH" if row["theme_hhi"] > theme_median else "LOW"
        row["streak_down5_group"] = row["vendor_streak_group"] + "|" + row["limit_down_count_5_group"]
        row["streak_breadth_group"] = row["vendor_streak_group"] + "|" + row["breadth_group"]
    summary: dict[str, Any] = {
        "schema_version": "h02-final-stock-features-v1",
        "classification": "TIER_D_EXPLORATORY_VENDOR_EVENT_FEATURES_PIT_UNVERIFIED_NOT_TRADING_RETURNS",
        "study_dates": [START, END],
        "split": {"train_end": TRAIN_END, "validation_end": VALIDATION_END, "forward_end": END},
        "source_archive_sha256": data["archive_hashes"],
        "source_manifest_hashes_verified": aux["archive_manifest_verified"],
        "source_manifest_hashes_seen": aux["archive_manifest_count"],
        "event_source_manifest_hashes_verified": data["manifest_hashes_verified"],
        "event_source_manifest_hashes_seen": data["manifest_hashes_expected"],
        "theme_hhi_training_feature_median": theme_median,
        "feature_matrix_rows": len(rows),
        "feature_matrix_unique_symbol_days": len({(r["outcome_date"], r["ts_code"]) for r in rows}),
        "protected_holdout_accessed": False,
        "feature_matrix_contains_symbol_ids": True,
        "feature_matrix_redistribution": "LOCAL_IGNORED_ONLY; Xuangubao terms unresolved; do not publish raw rows",
        "field_dictionary": FIELD_DICTIONARY,
        "feature_time_contract": {
            "all_feature_last_session_is_strictly_before_outcome": all(r["feature_last_session"] < r["outcome_date"] for r in rows),
            "historical_publication_time_certified": False,
            "pit_status": PIT_STATUS,
            "same_day_or_future_target_used_as_feature": False,
            "D_minus_1_close_event_input_available_by_next_day_0935_proven": False,
        },
        "data_availability": {
            "available": ["vendor limit_up/limit_down/limit_break event pools", "vendor market_indicator snapshots", "vendor theme_limit_up labels"],
            "unavailable": ["independent OHLC", "official per-stock daily limit prices", "independent PIT ST/suspension", "candidate minute bars and order-level fills", "licensed point-in-time theme history proof"],
            "limit_up_pool_semantics": "Historical vendor event-pool membership; not certified close-only limit-up status.",
            "theme_semantics": "Vendor theme labels; no sector/core/leadership truth is implied.",
        },
        "periods": {},
        "outcomes": {},
        "feature_matrix_normalized_sha256": None,
    }
    for phase in ("train", "validation_2025H2", "forward_2026H1"):
        part = [r for r in rows if r["phase"] == phase]
        phase_days = [d for d in data["calendar_days"] if START <= d <= END and _period(d) == phase]
        summary["periods"][phase] = {
            "outcome_sessions": len(phase_days),
            "candidate_symbol_days": len(part),
            "days_with_no_candidates": sum(not data["limit_up"][d] for d in phase_days),
            "candidate_pool_coverage": len({r["outcome_date"] for r in part}) / len(phase_days) if phase_days else None,
        }
        summary["outcomes"][phase] = {}
        for label, target in (("continuation_D", "Y1_D_vendor_limit_up_pool"), ("down_next_D", "Y2_D_vendor_limit_down_pool"), ("down_three_D_to_D2", "Y3_D_to_D2_vendor_limit_down_pool")):
            eligible = _eligible(rows, phase, label)
            k, n, rate = _rate(eligible, label)
            draws = _block_bootstrap_rate(eligible, label, calendar_days=phase_days)
            summary["outcomes"][phase][target] = {
                "events": k, "candidate_symbol_days": n,
                "phase_eligible_candidate_coverage": n / len(part) if part else None,
                "rate": rate,
                "five_trading_day_block_bootstrap_95pct_ci": [float(np.quantile(draws, .025)), float(np.quantile(draws, .975))] if draws else None,
                "groups": _conditional_table(eligible, label, GROUPERS, calendar_days=phase_days),
            }
    return summary, rows


def write_outputs(summary: dict, rows: list[dict], out_json: Path, out_markdown: Path, matrix_out: Path) -> None:
    frame = pd.DataFrame(rows).sort_values(["outcome_date", "ts_code"], kind="mergesort")
    csv_bytes = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    matrix_out.parent.mkdir(parents=True, exist_ok=True)
    matrix_out.write_bytes(csv_bytes)
    summary["feature_matrix_normalized_sha256"] = hashlib.sha256(csv_bytes).hexdigest()
    summary["feature_matrix_output_path"] = "LOCAL_IGNORED_ONLY (path supplied by --matrix-out)"
    summary["feature_matrix_source_sha_scope"] = "Partition SHA256 values are stored per row; archive SHA256 values are recorded in the aggregate report."
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# H02 final stock-event feature and conditional-rate research",
        "",
        "**Classification:** TIER D exploratory vendor event data; all historical input availability is `PIT_UNVERIFIED`. This is not trading performance.",
        "",
        f"Study: {START} through {END}. Training ends {TRAIN_END}; validation ends {VALIDATION_END}; forward development ends {END}.",
        "",
        f"Generated {summary['feature_matrix_rows']:,} stock-day rows from five SHA-pinned archives. The row matrix is local ignored output only; normalized SHA256: `{summary['feature_matrix_normalized_sha256']}`.",
        "",
        "All feature rows use D-1 or earlier event pools. D outcomes are labels only. Historical publication time is not certified.",
        "",
        "## Outcome and group tables",
        "",
        "The group schema and every predeclared level are in the machine-readable JSON. Empty groups are retained. Confidence intervals use a deterministic 5-trading-day circular block bootstrap (1,000 replicates). They describe clustered event rates; overlapping labels and exposed development periods still limit inference.",
        "",
        "| Phase | Target | Events / eligible candidate symbol-days | Rate | 95% day-block interval |",
        "|---|---|---:|---:|---:|",
    ]
    for phase, targets in summary["outcomes"].items():
        for name, value in targets.items():
            ci = value["five_trading_day_block_bootstrap_95pct_ci"]
            ci_text = "n/a" if ci is None else f"{ci[0]:.4%}–{ci[1]:.4%}"
            lines.append(f"| {phase} | {name} | {value['events']:,}/{value['candidate_symbol_days']:,} | {value['rate']:.4%} | {ci_text} |" if value["rate"] is not None else f"| {phase} | {name} | 0/0 | n/a | n/a |")
    lines += [
        "",
        "## Feature availability and boundary",
        "",
        "The archives include vendor limit-break pools, market-indicator snapshots and theme labels, so those are summarized as vendor-derived features where structurally present. No turnover, capital-flow, order-book, or independent sector-core truth is inferred beyond fields present in the archive. `theme_hhi` is only concentration of vendor theme assignments.",
        "",
        "The source archive has no independent daily OHLC, official per-stock limit prices, independently PIT-timed ST/halt status, or candidate minute bars. No actual fill, return, drawdown, or net equity result can be computed.",
        "",
        "## Reproduction",
        "",
        "```powershell",
        "python scripts/h02_final_stock_features.py --artifacts <five approved h01-raw ZIP paths> --out-json runs/h02-final-research/features.json --out-markdown runs/h02-final-research/features.md --matrix-out runs/h02-final-research/feature-matrix.csv",
        "```",
        "",
    ]
    out_markdown.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", nargs=5, required=True, type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-markdown", type=Path, required=True)
    parser.add_argument("--matrix-out", type=Path, required=True)
    args = parser.parse_args()
    base = load_market_events(args.artifacts)
    aux = _load_auxiliary(args.artifacts)
    report, rows = analyze_features(base, aux)
    write_outputs(report, rows, args.out_json, args.out_markdown, args.matrix_out)
    print(json.dumps({"status": report["classification"], "rows": report["feature_matrix_rows"], "periods": report["periods"], "source_manifest_hashes": f"{aux['archive_manifest_verified']}/{aux['archive_manifest_count']}"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
