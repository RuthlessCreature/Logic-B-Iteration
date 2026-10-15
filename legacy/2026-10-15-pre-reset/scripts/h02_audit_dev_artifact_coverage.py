"""Audit retained H01 development-period Xuangubao artifacts for H02 readiness.

This is an offline artifact auditor. It does not contact providers and rejects
any archive containing a partition after 2026-06-30 before reading its data.
It reports aggregate counts only; source symbol rows are never copied to output.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


DEV_CUTOFF = "20260630"
ALLOWED_PERIODS = {"2024h1", "2024h2", "2025h1", "2025h2", "2026dev"}
TRUSTED_SOURCE_RUN_ID = 38358815302
TRUSTED_ARCHIVE_SHA256 = {
    "h01-raw-2024h1.zip": "1abfc7022075958537e635b107c0919a68122dc0ff6b7a97cec6132f9ab6fec8",
    "h01-raw-2024h2.zip": "ddd770f7f0dc1322c2d782ae1925d43df302570277c0b53af0bde8bef674c1ad",
    "h01-raw-2025h1.zip": "cb9bca81e71fa42ed85659564e5a6a7f446f25cbfc1bc7005d734529dbdc0c67",
    "h01-raw-2025h2.zip": "8c4a9c90acfc9b7e841a453b127b2dcfb6dcc68e43566ca9f5838d1dcbcb0144",
    "h01-raw-2026dev.zip": "7da9da754fb7d976b03a371666fd9d27fec0fcaf4f4f784dbecae01e978e857c",
}
HASHED_DATASETS = {
    "calendar", "limit_up", "limit_down", "limit_break",
    "market_indicator", "theme_limit_up",
}
REQUIRED_EXECUTION_DATASETS = {
    "independent_daily_d": "daily",
    "reference_st_d": "stock_st",
    "reference_halt_d": "suspend",
    "official_price_limits_d": "limit_prices",
    "candidate_minute_1m_d": "minute_1m",
}


class ArtifactAuditError(ValueError):
    """An artifact is malformed, ambiguous, or crosses the protected cutoff."""


def trusted_archive_bytes(path: Path) -> bytes:
    """Return bytes only for an exact, whole-archive SHA256 allowlist match."""
    expected = TRUSTED_ARCHIVE_SHA256.get(Path(path).name)
    if expected is None:
        raise ArtifactAuditError(f"unapproved archive name: {Path(path).name}")
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ArtifactAuditError(f"untrusted archive SHA256: {Path(path).name}")
    return raw


def preflight_raw_member_names(names: set[str]) -> set[str]:
    """Validate every raw partition path/date before any Parquet is read."""
    raw_datasets: set[str] = set()
    for name in names:
        if not name.startswith("raw/"):
            continue
        parts = name.split("/")
        if len(parts) != 3 or parts[1] not in HASHED_DATASETS:
            raise ArtifactAuditError(f"unexpected raw dataset/member path: {name}")
        raw_datasets.add(parts[1])
        match = re.fullmatch(r"(\d{8})(?:_(\d{8}))?\.parquet", parts[2])
        if match is None:
            raise ArtifactAuditError(f"invalid raw partition path: {name}")
        partition_dates = [value for value in match.groups() if value is not None]
        if max(partition_dates) > DEV_CUTOFF:
            raise ArtifactAuditError("artifact contains a post-development partition")
    return raw_datasets


def _date_text(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ArtifactAuditError(f"invalid date value: {value!r}")
    return parsed.strftime("%Y%m%d")


def _json_member(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except KeyError as exc:
        raise ArtifactAuditError(f"missing manifest: {name}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactAuditError(f"invalid manifest: {name}") from exc
    if not isinstance(value, dict):
        raise ArtifactAuditError(f"manifest is not an object: {name}")
    return value


def _read_frame(raw: bytes, name: str) -> pd.DataFrame:
    try:
        return pd.read_parquet(io.BytesIO(raw))
    except Exception as exc:  # pragma: no cover - exception wording is engine-specific
        raise ArtifactAuditError(f"invalid Parquet member: {name}") from exc


def audit_artifacts(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ArtifactAuditError("at least one development artifact ZIP is required")
    supplied_names = [Path(path).name for path in paths]
    if len(supplied_names) != len(set(supplied_names)):
        raise ArtifactAuditError("duplicate artifact filename")
    if set(supplied_names) != set(TRUSTED_ARCHIVE_SHA256):
        raise ArtifactAuditError("archives must exactly match the five trusted development artifacts")

    period_reports: list[dict[str, Any]] = []
    all_calendar: set[str] = set()
    daily_candidate_rows: dict[str, int] = {}
    daily_candidate_hashes: dict[str, str] = {}
    daily_vendor_counts: dict[str, int] = {}
    hash_totals: Counter[str] = Counter()
    source_dataset_rows: Counter[str] = Counter()
    artifact_raw_datasets: set[str] = set()
    used_periods: set[str] = set()

    for path in sorted(paths):
        period = path.stem.removeprefix("h01-raw-")
        if period not in ALLOWED_PERIODS:
            raise ArtifactAuditError(f"non-development artifact is not allowed: {path.name}")
        if period in used_periods:
            raise ArtifactAuditError(f"duplicate artifact period: {period}")
        used_periods.add(period)

        archive_bytes = trusted_archive_bytes(path)
        archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
        # No ZIP member listing, decompression, or Parquet parsing occurs before
        # the complete archive bytes match the trusted source-run allowlist.
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = set(archive.namelist())
            # Check member names only. Do not decompress or read any protected data.
            artifact_raw_datasets.update(preflight_raw_member_names(names))

            metadata_paths = [n for n in names if n == f"batch_metadata/{period}.json"]
            if len(metadata_paths) != 1:
                raise ArtifactAuditError(f"missing batch metadata for {period}")
            batch = _json_member(archive, metadata_paths[0])
            if batch.get("part") != period or batch.get("data_is_not_net_equity_performance") is not True:
                raise ArtifactAuditError(f"unexpected batch metadata for {period}")

            manifests = sorted(
                n for n in names
                if n.startswith("manifests/") and n.endswith(".json")
            )
            ds_stats: dict[str, dict[str, Any]] = {}
            manifest_sha_by_dataset_partition: dict[tuple[str, str], str] = {}
            frames: dict[str, list[tuple[str, pd.DataFrame]]] = {
                "calendar": [], "limit_up": [], "market_indicator": [],
            }
            for manifest_name in manifests:
                parts = manifest_name.split("/")
                if len(parts) != 3:
                    continue
                dataset = parts[1]
                if dataset not in HASHED_DATASETS:
                    continue
                manifest = _json_member(archive, manifest_name)
                partition = str(manifest.get("partition", ""))
                raw_name = f"raw/{dataset}/{partition}.parquet"
                stats = ds_stats.setdefault(dataset, {
                    "partitions": 0, "hash_verified": 0,
                    "manifest_rows": 0, "missing_raw": 0,
                    "row_count_mismatch": 0,
                })
                stats["partitions"] += 1
                if raw_name not in names:
                    stats["missing_raw"] += 1
                    continue
                raw = archive.read(raw_name)
                actual_hash = hashlib.sha256(raw).hexdigest()
                if actual_hash != manifest.get("sha256"):
                    raise ArtifactAuditError(f"raw hash mismatch: {raw_name}")
                manifest_sha_by_dataset_partition[(dataset, partition)] = actual_hash
                stats["hash_verified"] += 1
                manifest_rows = int(manifest.get("rows", -1))
                stats["manifest_rows"] += max(0, manifest_rows)
                source_dataset_rows[dataset] += max(0, manifest_rows)

                if dataset in frames:
                    frame = _read_frame(raw, raw_name)
                    if len(frame) != manifest_rows:
                        stats["row_count_mismatch"] += 1
                        raise ArtifactAuditError(f"manifest row count mismatch: {raw_name}")
                    frames[dataset].append((partition, frame))

            for dataset, stats in ds_stats.items():
                if stats["partitions"] != stats["hash_verified"] or stats["missing_raw"]:
                    raise ArtifactAuditError(f"incomplete hash coverage in {period}/{dataset}")
                hash_totals[dataset] += stats["hash_verified"]

            calendar_parts = frames["calendar"]
            if len(calendar_parts) != 1:
                raise ArtifactAuditError(f"expected one calendar partition in {period}")
            calendar = calendar_parts[0][1]
            date_col = "cal_date" if "cal_date" in calendar.columns else "trade_date"
            if date_col not in calendar.columns:
                raise ArtifactAuditError(f"calendar date field missing in {period}")
            period_days = [_date_text(v) for v in calendar[date_col].tolist()]
            if len(period_days) != len(set(period_days)):
                raise ArtifactAuditError(f"duplicate calendar dates in {period}")
            all_calendar.update(period_days)

            candidate_days: set[str] = set()
            duplicate_rows = 0
            candidate_rows = 0
            for partition, frame in frames["limit_up"]:
                day = _date_text(partition)
                if day in candidate_days:
                    raise ArtifactAuditError(f"duplicate candidate partition: {day}")
                candidate_days.add(day)
                if not {"trade_date", "ts_code"}.issubset(frame.columns):
                    raise ArtifactAuditError(f"candidate schema incomplete: {day}")
                observed_dates = {_date_text(v) for v in frame["trade_date"].tolist()}
                if observed_dates and observed_dates != {day}:
                    raise ArtifactAuditError(f"candidate date mismatch: {day}")
                symbols = frame["ts_code"].astype("string")
                if symbols.isna().any() or symbols.str.strip().eq("").any():
                    raise ArtifactAuditError(f"invalid symbol in candidate partition: {day}")
                duplicate_rows += int(symbols.duplicated().sum())
                if duplicate_rows:
                    raise ArtifactAuditError(f"duplicate candidate symbols in {period}")
                candidate_rows += len(frame)
                daily_candidate_rows[day] = len(frame)
                daily_candidate_hashes[day] = manifest_sha_by_dataset_partition[("limit_up", day)]

            vendor_days: set[str] = set()
            for partition, frame in frames["market_indicator"]:
                day = _date_text(partition)
                vendor_days.add(day)
                if "trade_date" not in frame or "limit_up_count" not in frame:
                    raise ArtifactAuditError(f"market indicator schema incomplete: {day}")
                if frame.empty:
                    raise ArtifactAuditError(f"market indicator is empty: {day}")
                order_col = "timestamp" if "timestamp" in frame else "event_time"
                if order_col not in frame:
                    raise ArtifactAuditError(f"market indicator timestamp missing: {day}")
                ordered = frame.assign(_order=pd.to_datetime(frame[order_col], errors="coerce"))
                if ordered["_order"].isna().any():
                    raise ArtifactAuditError(f"invalid market indicator timestamp: {day}")
                observed_dates = {_date_text(v) for v in ordered["trade_date"].tolist()}
                if observed_dates != {day}:
                    raise ArtifactAuditError(f"market indicator date mismatch: {day}")
                count = pd.to_numeric(ordered.sort_values("_order").iloc[-1]["limit_up_count"], errors="coerce")
                if pd.isna(count) or count < 0 or int(count) != count:
                    raise ArtifactAuditError(f"invalid vendor limit-up count: {day}")
                daily_vendor_counts[day] = int(count)

            if candidate_days != set(period_days):
                raise ArtifactAuditError(f"candidate/calendar partition mismatch in {period}")
            if vendor_days != set(period_days):
                raise ArtifactAuditError(f"vendor-count/calendar partition mismatch in {period}")
            matches = sum(
                daily_vendor_counts[d] == daily_candidate_rows[d]
                for d in period_days
            )
            period_reports.append({
                "period": period,
                "artifact_name": path.name,
                "artifact_bytes": path.stat().st_size,
                "artifact_sha256": archive_sha256,
                "calendar_sessions": len(period_days),
                "first_session": min(period_days),
                "last_session": max(period_days),
                "candidate_partitions": len(candidate_days),
                "candidate_list_rows": candidate_rows,
                "duplicate_symbol_days": duplicate_rows,
                "vendor_count_matches": matches,
                "vendor_count_days": len(period_days),
                "dataset_manifests": ds_stats,
            })

    if used_periods != ALLOWED_PERIODS:
        missing = sorted(ALLOWED_PERIODS - used_periods)
        raise ArtifactAuditError(f"missing development periods: {missing}")
    sorted_days = sorted(all_calendar)
    if len(sorted_days) != len(all_calendar) or any(d > DEV_CUTOFF for d in sorted_days):
        raise ArtifactAuditError("calendar overlaps protected or duplicate dates")
    if not sorted_days:
        raise ArtifactAuditError("no development calendar sessions found")

    symbols_days = sum(daily_candidate_rows.values())
    vendor_matches = sum(
        daily_vendor_counts[d] == daily_candidate_rows[d]
        for d in daily_candidate_rows
    )
    aggregate_reasons = {
        "XGB_LICENSE_TERMS_NOT_DOCUMENTED": symbols_days,
        "HISTORICAL_AVAILABLE_AT_UNVERIFIED": symbols_days,
    }
    for reason in (
        "independent_daily_d", "reference_st_d", "reference_halt_d",
        "official_price_limits_d",
    ):
        aggregate_reasons["MISSING_" + reason.upper()] = symbols_days

    return {
        "schema_version": "h02-dev-artifact-inventory-v1",
        "status": "TIER_D_INVENTORY_COMPLETE_TIER_E_BLOCKED",
        "scope": {
            "start": sorted_days[0],
            "end": sorted_days[-1],
            "protected_holdout_accessed": False,
            "protected_holdout_included": False,
            "periods": sorted(used_periods),
        },
        "source": {
            "provider": "xuangubao",
            "data_class": "market-wide limit_up event-list, not B0-filtered candidates",
            "source_terms": "UNRESOLVED",
            "retrieved_at": "2026-10-13 (artifact manifests; not historical availability)",
            "artifact_sha256_by_period": {
                item["period"]: item["artifact_sha256"] for item in period_reports
            },
            "raw_sha256_verified_against_manifest": dict(hash_totals),
            "manifest_row_totals": dict(source_dataset_rows),
        },
        "execution_dataset_inventory": {
            "raw_datasets_present": sorted(artifact_raw_datasets),
            "required_H02_dataset_status": {
                key: ("PRESENT" if dataset in artifact_raw_datasets else "NOT_PRESENT_IN_SELECTED_ARTIFACTS")
                for key, dataset in REQUIRED_EXECUTION_DATASETS.items()
            },
        },
        "coverage": {
            "calendar_sessions": len(sorted_days),
            "candidate_partitions": len(daily_candidate_rows),
            "candidate_partition_coverage": f"{len(daily_candidate_rows)}/{len(sorted_days)}",
            "limit_up_event_symbol_days": symbols_days,
            "unique_symbol_days": symbols_days,
            "duplicate_symbol_days": 0,
            "vendor_count_matches": vendor_matches,
            "vendor_count_denominator": len(daily_candidate_rows),
            "official_price_limits_verified_symbol_days": 0,
            "PIT_ST_verified_symbol_days": 0,
            "PIT_halt_verified_symbol_days": 0,
            "minute_partitions_present": 0,
            "minute_partition_denominator": "UNKNOWN: selected B0 symbol-days cannot be determined without execution-day evidence",
            "execution_eligible_symbol_days": 0,
            "execution_candidate_denominator": "UNKNOWN: frozen B0 filters cannot be replayed without execution-day evidence",
            "preselection_blocked_candidate_rows_by_reason": aggregate_reasons,
        },
        "periods": period_reports,
        "preselection_blocker_mask": {
            "1": "SOURCE_LICENSE_UNRESOLVED",
            "2": "HISTORICAL_AVAILABLE_AT_UNVERIFIED",
            "4": "OFFICIAL_LIMITS_MISSING",
            "8": "PIT_ST_MISSING",
            "16": "PIT_HALT_MISSING",
        },
        "daily_candidate_diagnostics_columns": [
            "candidate_date_d_minus_1", "candidate_rows",
            "candidate_partition_sha256", "same_provider_count_match",
            "preselection_blocked_layer_mask",
        ],
        "daily_candidate_diagnostics": [
            [
                d,
                daily_candidate_rows[d],
                daily_candidate_hashes[d],
                daily_vendor_counts[d] == daily_candidate_rows[d],
                31,
            ]
            for d in sorted(daily_candidate_rows)
        ],
        "notes": [
            "limit_up rows are raw provider event-list entries before frozen B0 filtering.",
            "Calendar, candidate list, and matching market_indicator are from the same provider; their count agreement is not independent completeness proof.",
            "Artifacts contain no daily OHLC, official price-limit, stock_st, suspend, or minute_1m datasets.",
            "Missing execution inputs are not imputed; no replay or return calculation was performed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", nargs="+", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = audit_artifacts(args.artifacts)
    except (OSError, zipfile.BadZipFile, ArtifactAuditError) as exc:
        report = {"schema_version": "h02-dev-artifact-inventory-v1", "status": "BLOCKED", "reason": str(exc)}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    report["status"] = "TIER_D_INVENTORY_COMPLETE_TIER_E_BLOCKED"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "out": str(args.out), "coverage": report["coverage"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

