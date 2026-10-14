"""Reproduce H02 Tier-D event-pool transition and downside observations.

No provider calls are made. Five whole ZIPs must match the pinned SHA allowlist
before any archive member is read. Outputs contain aggregate daily counts/hashes,
never symbol-level rows, and are explicitly not strategy performance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


_AUDITOR_PATH = Path(__file__).with_name("h02_audit_dev_artifact_coverage.py")
_SPEC = importlib.util.spec_from_file_location("h02_trusted_artifact_auditor", _AUDITOR_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load trusted artifact auditor: {_AUDITOR_PATH}")
_AUDITOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_AUDITOR)

START = "20240930"
END = "20260630"
DATASETS = ("calendar", "limit_up", "limit_down")


class EmpiricalDataError(ValueError):
    """Inputs are incomplete, ambiguous, or outside the authorized window."""


def _day(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise EmpiricalDataError(f"invalid date value: {value!r}")
    result = parsed.strftime("%Y%m%d")
    if result > END:
        raise EmpiricalDataError("protected/post-development date is forbidden")
    return result


def _read_manifest(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EmpiricalDataError(f"invalid or missing manifest: {name}") from exc
    if not isinstance(value, dict):
        raise EmpiricalDataError(f"manifest must be an object: {name}")
    return value


def _date_set(frame: pd.DataFrame, *, dataset: str, partition: str) -> tuple[set[str], int]:
    if frame.empty and len(frame.columns) == 0:
        # The vendor uses a zero-column Parquet as an explicit empty event pool.
        # Its raw-byte SHA and manifest row count have already been verified.
        _day(partition)
        return set(), 0
    if "ts_code" not in frame.columns:
        raise EmpiricalDataError(f"{dataset} missing ts_code: {partition}")
    if "trade_date" not in frame.columns:
        raise EmpiricalDataError(f"{dataset} missing trade_date: {partition}")
    dates = {_day(x) for x in frame["trade_date"].tolist()}
    expected = _day(partition)
    if dates and dates != {expected}:
        raise EmpiricalDataError(f"{dataset} partition date mismatch: {partition}")
    codes = frame["ts_code"].astype("string")
    if codes.isna().any() or codes.str.strip().eq("").any():
        raise EmpiricalDataError(f"{dataset} has blank symbols: {partition}")
    if codes.duplicated().any():
        raise EmpiricalDataError(f"duplicate {dataset} symbol-day: {partition}")
    return set(codes.astype(str)), len(frame)


def load_market_events(paths: list[Path]) -> dict[str, Any]:
    """Load only calendar/limit_up/limit_down after strict archive preflight."""
    expected_names = set(_AUDITOR.TRUSTED_ARCHIVE_SHA256)
    names = [Path(path).name for path in paths]
    if len(names) != len(set(names)) or set(names) != expected_names:
        raise EmpiricalDataError("input must be exactly the five trusted development archives")

    calendars: dict[str, str] = {}
    up: dict[str, set[str]] = {}
    down: dict[str, set[str]] = {}
    partition_hashes: dict[str, dict[str, str]] = {name: {} for name in DATASETS}
    archive_hashes: dict[str, str] = {}
    manifest_verified = 0
    manifest_expected = 0

    for path in sorted((Path(p) for p in paths), key=lambda p: p.name):
        raw_archive = _AUDITOR.trusted_archive_bytes(path)
        archive_hashes[path.name] = hashlib.sha256(raw_archive).hexdigest()
        # ZIP central directory access is permitted only after exact whole-file SHA.
        with zipfile.ZipFile(io.BytesIO(raw_archive)) as archive:
            members = set(archive.namelist())
            _AUDITOR.preflight_raw_member_names(members)
            period = path.stem.removeprefix("h01-raw-")
            metadata = _read_manifest(archive, f"batch_metadata/{period}.json")
            if metadata.get("part") != period:
                raise EmpiricalDataError(f"unexpected batch metadata: {period}")

            manifests: dict[str, dict[str, dict[str, Any]]] = {ds: {} for ds in DATASETS}
            for member in sorted(m for m in members if m.startswith("manifests/") and m.endswith(".json")):
                parts = member.split("/")
                if len(parts) != 3 or parts[1] not in DATASETS:
                    continue
                value = _read_manifest(archive, member)
                dataset = parts[1]
                partition = str(value.get("partition", ""))
                if not partition or partition in manifests[dataset]:
                    raise EmpiricalDataError(f"duplicate/empty manifest partition: {member}")
                if value.get("dataset") != dataset:
                    raise EmpiricalDataError(f"manifest dataset mismatch: {member}")
                manifests[dataset][partition] = value

            for dataset in DATASETS:
                for partition, manifest in manifests[dataset].items():
                    raw_name = f"raw/{dataset}/{partition}.parquet"
                    if raw_name not in members:
                        raise EmpiricalDataError(f"missing raw partition: {raw_name}")
                    raw = archive.read(raw_name)
                    digest = hashlib.sha256(raw).hexdigest()
                    manifest_expected += 1
                    if digest != manifest.get("sha256"):
                        raise EmpiricalDataError(f"raw partition hash mismatch: {raw_name}")
                    manifest_verified += 1
                    frame = pd.read_parquet(io.BytesIO(raw))
                    if len(frame) != int(manifest.get("rows", -1)):
                        raise EmpiricalDataError(f"manifest row count mismatch: {raw_name}")
                    partition_hashes[dataset][partition] = digest
                    if dataset == "calendar":
                        date_col = "cal_date" if "cal_date" in frame else "trade_date"
                        if date_col not in frame:
                            raise EmpiricalDataError(f"calendar date column missing: {partition}")
                        for value in frame[date_col].tolist():
                            day = _day(value)
                            if day in calendars:
                                raise EmpiricalDataError(f"duplicate calendar day across archives: {day}")
                            calendars[day] = digest
                    else:
                        codes, _ = _date_set(frame, dataset=dataset, partition=partition)
                        target = up if dataset == "limit_up" else down
                        if partition in target:
                            raise EmpiricalDataError(f"duplicate {dataset} partition: {partition}")
                        target[partition] = codes

    days = sorted(calendars)
    if not days or days != sorted(set(days)):
        raise EmpiricalDataError("calendar is empty or duplicated")
    if set(up) != set(days):
        missing = sorted(set(days) - set(up))[:5]
        extra = sorted(set(up) - set(days))[:5]
        raise EmpiricalDataError(f"limit_up/calendar coverage mismatch; missing={missing}, extra={extra}")
    if set(down) != set(days):
        missing = sorted(set(days) - set(down))[:5]
        extra = sorted(set(down) - set(days))[:5]
        raise EmpiricalDataError(f"limit_down/calendar coverage mismatch; missing={missing}, extra={extra}")
    if manifest_verified != manifest_expected or not manifest_expected:
        raise EmpiricalDataError("manifest hash coverage incomplete")
    return {
        "calendar_days": days,
        "calendar_hashes": calendars,
        "limit_up": up,
        "limit_down": down,
        "partition_hashes": partition_hashes,
        "archive_hashes": archive_hashes,
        "manifest_hashes_verified": manifest_verified,
        "manifest_hashes_expected": manifest_expected,
    }


def _bucket(day: str) -> tuple[str, str]:
    year = day[:4]
    half = "H1" if day[4:6] <= "06" else "H2"
    return year, f"{year}{half}"


def _ratio_summary(rows: list[dict[str, Any]], numerator: str, denominator: str) -> dict[str, Any]:
    n = sum(int(row[numerator]) for row in rows)
    d = sum(int(row[denominator]) for row in rows)
    ratios = [row[numerator] / row[denominator] for row in rows if row[denominator] > 0]
    return {
        "numerator": n,
        "denominator": d,
        "pooled_rate": n / d if d else None,
        "pooled_percent": 100.0 * n / d if d else None,
        "daily_ratio_mean": statistics.fmean(ratios) if ratios else None,
        "daily_ratio_median": statistics.median(ratios) if ratios else None,
        "days_with_nonzero_denominator": len(ratios),
    }


def compute_statistics(data: dict[str, Any], start: str = START, end: str = END) -> dict[str, Any]:
    start, end = _day(start), _day(end)
    if start > end:
        raise EmpiricalDataError("start must be <= end")
    days = [_day(value) for value in data["calendar_days"]]
    if days != sorted(set(days)):
        raise EmpiricalDataError("calendar must be sorted and unique")
    index = {day: i for i, day in enumerate(days)}
    scoped = [day for day in days if start <= day <= end]
    if not scoped:
        raise EmpiricalDataError("no outcome sessions in requested development range")
    up, down = data["limit_up"], data["limit_down"]
    hashes = data["partition_hashes"]
    daily: list[dict[str, Any]] = []
    skipped: defaultdict[str, int] = defaultdict(int)
    overlap_symbol_days = 0
    cross_half_year_pairs = 0
    for day in scoped:
        i = index[day]
        if i == 0:
            skipped["NO_PRIOR_TRADING_SESSION"] += 1
            continue
        prior = days[i - 1]
        if _bucket(prior)[1] != _bucket(day)[1]:
            cross_half_year_pairs += 1
        if prior not in up or day not in up or day not in down:
            raise EmpiricalDataError(f"missing single-day event partition around {day}")
        cohort = up[prior]
        denom = len(cohort)
        if denom == 0:
            skipped["EMPTY_PRIOR_LIMIT_UP_POOL"] += 1
            continue
        up_now = up[day]
        down_now = down[day]
        overlap_symbol_days += len(up_now & down_now)
        continuation = len(cohort & up_now)
        down_one = len(cohort & down_now)
        future_days = days[i:i + 3]
        three_complete = len(future_days) == 3 and future_days[-1] <= end
        if three_complete:
            if any(future not in down for future in future_days):
                raise EmpiricalDataError(f"missing three-day risk partition around {day}")
            down_union = set().union(*(down[future] for future in future_days))
            down_three = len(cohort & down_union)
        else:
            down_three = None
            skipped["THREE_DAY_WINDOW_NOT_FULLY_WITHIN_DEVELOPMENT_RANGE"] += 1
        year, half = _bucket(day)
        daily.append({
            "outcome_date": day,
            "prior_candidate_date": prior,
            "year": year,
            "half_year": half,
            "prior_limit_up_candidates": denom,
            "next_day_limit_up_pool_matches": continuation,
            "next_day_limit_down_pool_matches": down_one,
            "three_trade_day_limit_down_pool_touches": down_three,
            "three_day_denominator": denom if three_complete else None,
            "same_day_up_down_pool_overlap": len(up_now & down_now),
            "calendar_partition_sha256": data["calendar_hashes"][day],
            "prior_limit_up_partition_sha256": hashes["limit_up"][prior],
            "outcome_limit_up_partition_sha256": hashes["limit_up"][day],
            "outcome_limit_down_partition_sha256": hashes["limit_down"][day],
            "three_day_limit_down_partition_sha256": [hashes["limit_down"][x] for x in future_days] if three_complete else [],
        })
    if not daily:
        raise EmpiricalDataError("no complete candidate observations in requested range")

    result: dict[str, Any] = {
        "overall": {
            "outcome_date_first": daily[0]["outcome_date"],
            "outcome_date_last": daily[-1]["outcome_date"],
            "outcome_trade_days": len(daily),
            "candidate_symbol_days": sum(row["prior_limit_up_candidates"] for row in daily),
            "continuation": _ratio_summary(daily, "next_day_limit_up_pool_matches", "prior_limit_up_candidates"),
            "next_day_down_event": _ratio_summary(daily, "next_day_limit_down_pool_matches", "prior_limit_up_candidates"),
            "three_day_down_event": _ratio_summary(
                [row for row in daily if row["three_day_denominator"] is not None],
                "three_trade_day_limit_down_pool_touches", "three_day_denominator",
            ),
            "three_day_observation_days": sum(row["three_day_denominator"] is not None for row in daily),
            "same_day_up_down_pool_overlap_symbol_days": overlap_symbol_days,
            "cross_half_year_calendar_pairs": cross_half_year_pairs,
        },
        "by_year": {},
        "by_half_year": {},
        "coverage": {
            "requested_outcome_sessions": len(scoped),
            "complete_candidate_observation_days": len(daily),
            "calendar_sessions_available": len(days),
            "limit_up_partitions": len(up),
            "limit_down_partitions": len(down),
            "manifest_hashes_verified": data["manifest_hashes_verified"],
            "manifest_hashes_expected": data["manifest_hashes_expected"],
            "whole_archive_hashes_verified": len(data["archive_hashes"]),
            "whole_archive_hashes_expected": len(_AUDITOR.TRUSTED_ARCHIVE_SHA256),
            "missing_limit_up_partitions": 0,
            "missing_limit_down_partitions": 0,
        },
        "quality_checks": {
            "duplicate_calendar_days": 0,
            "duplicate_limit_up_symbol_days": 0,
            "duplicate_limit_down_symbol_days": 0,
            "cross_half_year_pairs_in_scope": cross_half_year_pairs,
            "same_day_up_down_pool_overlap_symbol_days": overlap_symbol_days,
            "three_day_windows_extending_beyond_cutoff_excluded": skipped.get(
                "THREE_DAY_WINDOW_NOT_FULLY_WITHIN_DEVELOPMENT_RANGE", 0
            ),
            "inference_intervals_calculated": False,
            "reason_intervals_not_inferred": (
                "descriptive full-coverage vendor event-pool observations; repeated symbol-days are not independent samples"
            ),
        },
        "skipped_or_limited_days": dict(sorted(skipped.items())),
        "daily": daily,
        "archive_hashes_sha256": data["archive_hashes"],
        "source_run_id": _AUDITOR.TRUSTED_SOURCE_RUN_ID,
        "source_semantics": {
            "status": "EVENT_POOL_SEMANTICS_UNCONFIRMED",
            "interpretation": "same-vendor limit_up/limit_down pool membership transitions; not certified close-limit or intraday touch semantics",
        },
        "classification": "TIER_D_HISTORICAL_MARKET_EVENT_OBSERVATION_NOT_TRADING_PERFORMANCE",
        "tier_e_status": "BLOCKED_UNVERIFIED_EXECUTION_PIT_AND_SOURCE_TERMS",
        "decision_time_inputs_used": False,
        "future_data_used_as_decision_input": False,
        "protected_holdout_accessed": False,
        "sample_observations_are_independent": False,
    }

    for key_name, field in (("by_year", "year"), ("by_half_year", "half_year")):
        groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in daily:
            groups[row[field]].append(row)
        for group, rows in sorted(groups.items()):
            result[key_name][group] = {
                "outcome_trade_days": len(rows),
                "candidate_symbol_days": sum(row["prior_limit_up_candidates"] for row in rows),
                "continuation": _ratio_summary(rows, "next_day_limit_up_pool_matches", "prior_limit_up_candidates"),
                "next_day_down_event": _ratio_summary(rows, "next_day_limit_down_pool_matches", "prior_limit_up_candidates"),
                "three_day_down_event": _ratio_summary(
                    [row for row in rows if row["three_day_denominator"] is not None],
                    "three_trade_day_limit_down_pool_touches", "three_day_denominator",
                ),
            }
    return result


def _markdown(report: dict[str, Any]) -> str:
    overall = report["overall"]
    lines = [
        "# H02 FIRST EMPIRICAL RESULT — TIER D, NOT TRADING PERFORMANCE",
        "",
        "Scope: 2024-09-30 through 2026-06-30. These are same-vendor event-pool membership observations, not strategy signals, trade outcomes, or investor-psychology evidence.",
        "",
        "## Three observed statistics",
        "",
    ]
    labels = [
        ("Next-session limit-up-pool continuation", overall["continuation"]),
        ("Next-session limit-down-pool event", overall["next_day_down_event"]),
        ("Limit-down-pool event within next three trading sessions", overall["three_day_down_event"]),
    ]
    for label, item in labels:
        lines.append(f"- **{label}:** {item['numerator']:,} / {item['denominator']:,} = {item['pooled_percent']:.4f}% (pooled symbol-day rate). Daily mean {item['daily_ratio_mean'] * 100:.4f}%; daily median {item['daily_ratio_median'] * 100:.4f}%.")
    lines += [
        "",
        "The three-day risk denominator includes only outcome days with all three subsequent sessions inside the development cutoff. Duplicated symbol-days across dates are not independent observations.",
        "",
        "## Annual and half-year splits",
        "",
        "| Period | Outcome days | Prior-pool symbol-days | Next-day up-pool | Next-day down-pool | 3-session down-pool |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for group, stats in report["by_year"].items():
        lines.append(_period_line(group, stats))
    lines.append("| **Half-year** | | | | | |")
    for group, stats in report["by_half_year"].items():
        lines.append(_period_line(group, stats))
    lines += [
        "",
        "## Provenance, coverage, and interpretation",
        "",
        f"- Source: [H01 artifact run {report['source_run_id']}](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/{report['source_run_id']}); whole ZIP SHA verified {report['coverage']['whole_archive_hashes_verified']}/{report['coverage']['whole_archive_hashes_expected']}; selected calendar/limit_up/limit_down manifest hashes verified {report['coverage']['manifest_hashes_verified']}/{report['coverage']['manifest_hashes_expected']}.",
        f"- Coverage: {report['coverage']['complete_candidate_observation_days']}/{report['coverage']['requested_outcome_sessions']} requested outcome sessions have a prior candidate pool; {report['coverage']['limit_up_partitions']}/{report['coverage']['calendar_sessions_available']} limit_up and {report['coverage']['limit_down_partitions']}/{report['coverage']['calendar_sessions_available']} limit_down partitions are present.",
        "- The 2024-09-30 observation uses 2024-09-27 only as D-1 context. Three-session risk stops before any window extending past 2026-06-30. No protected holdout data were opened.",
        f"- The event calculation crosses {report['quality_checks']['cross_half_year_pairs_in_scope']} half-year archive seams using the verified combined trading calendar. Missing in-scope up/down partitions: 0/0.",
        "- `limit_up` / `limit_down` are Xuangubao provider event pools. The retained project artifact and provider adapter do not establish whether membership means closing at the limit or an intraday event; results therefore remain same-vendor pool transition rates.",
        "- This adds the correct frozen development-range slice, a same-day downside proxy, and a three-session downside proxy to the prior H01 continuation proxy. It does not establish causality or strategy edge.",
        "- No inferential confidence interval is reported: this is a descriptive census of archived vendor observations, with repeated securities across days and no independence assumption.",
        "- Tier E remains BLOCKED by absent official per-stock limits, PIT status/timestamps, execution-time semantics, verified fills, and unresolved source license/availability terms. No B0 signal, win rate, returns, or equity curve were evaluated.",
        "",
        "## Whole archive SHA256",
        "",
    ]
    for name, digest in sorted(report["archive_hashes_sha256"].items()):
        lines.append(f"- `{name}`: `{digest}`")
    lines += ["", "Daily aggregate counts and partition SHA256 references are in the companion JSON. No symbol-level rows are included.", ""]
    return "\n".join(lines)


def _period_line(group: str, stats: dict[str, Any]) -> str:
    def cell(key: str) -> str:
        item = stats[key]
        return f"{item['numerator']:,}/{item['denominator']:,} ({item['pooled_percent']:.2f}%)"
    down3 = stats["three_day_down_event"]
    down3_cell = f"{down3['numerator']:,}/{down3['denominator']:,} ({down3['pooled_percent']:.2f}%)" if down3["denominator"] else "—"
    return f"| {group} | {stats['outcome_trade_days']} | {stats['candidate_symbol_days']:,} | {cell('continuation')} | {cell('next_day_down_event')} | {down3_cell} |"


def write_reports(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", nargs="+", required=True, type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    data = load_market_events(args.artifacts)
    report = compute_statistics(data)
    write_reports(report, args.json, args.markdown)
    print(json.dumps({"status": "TIER_D_RESULT_WRITTEN", "overall": report["overall"], "coverage": report["coverage"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

