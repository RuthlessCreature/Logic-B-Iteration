from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from scripts.h02_audit_dev_artifact_coverage import ArtifactAuditError, audit_artifacts


PERIOD_DATES = {
    "2024h1": "20240102",
    "2024h2": "20240701",
    "2025h1": "20250102",
    "2025h2": "20250701",
    "2026dev": "20260105",
}


def parquet_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.BytesIO()
    frame.to_parquet(stream, index=False)
    return stream.getvalue()


def write_period(path: Path, period: str, day: str, *, duplicate=False, corrupt=False) -> None:
    calendar = parquet_bytes(pd.DataFrame({"cal_date": [day], "source": ["fixture"]}))
    symbols = ["600000.SH", "600000.SH"] if duplicate else ["600000.SH"]
    candidates = parquet_bytes(pd.DataFrame({"trade_date": [day] * len(symbols), "ts_code": symbols}))
    manifest_candidates = candidates if not corrupt else candidates + b"tampered"
    indicator = parquet_bytes(pd.DataFrame({
        "trade_date": [day], "timestamp": [f"{day}T15:00:00"], "limit_up_count": [len(symbols)]
    }))
    members = {
        "batch_metadata/" + period + ".json": json.dumps({
            "part": period,
            "data_is_not_net_equity_performance": True,
        }).encode(),
        "raw/calendar/" + day + "_" + day + ".parquet": calendar,
        "raw/limit_up/" + day + ".parquet": candidates,
        "raw/market_indicator/" + day + ".parquet": indicator,
    }
    manifests = {
        "manifests/calendar/" + day + "_" + day + ".json": {
            "dataset": "calendar", "partition": day + "_" + day,
            "rows": 1, "sha256": hashlib.sha256(calendar).hexdigest(),
        },
        "manifests/limit_up/" + day + ".json": {
            "dataset": "limit_up", "partition": day,
            "rows": len(symbols), "sha256": hashlib.sha256(manifest_candidates).hexdigest(),
        },
        "manifests/market_indicator/" + day + ".json": {
            "dataset": "market_indicator", "partition": day,
            "rows": 1, "sha256": hashlib.sha256(indicator).hexdigest(),
        },
    }
    members.update({name: json.dumps(value).encode() for name, value in manifests.items()})
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in members.items():
            archive.writestr(name, body)


def make_artifacts(root: Path, *, duplicate_period=None, corrupt_period=None) -> list[Path]:
    paths = []
    for period, day in PERIOD_DATES.items():
        path = root / f"h01-raw-{period}.zip"
        write_period(
            path, period, day,
            duplicate=period == duplicate_period,
            corrupt=period == corrupt_period,
        )
        paths.append(path)
    return paths


def test_audit_reports_hash_verified_candidate_coverage_and_blocks_tier_e(tmp_path):
    report = audit_artifacts(make_artifacts(tmp_path))
    assert report["status"] == "TIER_D_INVENTORY_COMPLETE_TIER_E_BLOCKED"
    assert report["coverage"]["calendar_sessions"] == 5
    assert report["coverage"]["candidate_partitions"] == 5
    assert report["coverage"]["limit_up_event_symbol_days"] == 5
    assert report["coverage"]["unique_symbol_days"] == 5
    assert report["coverage"]["vendor_count_matches"] == 5
    assert report["coverage"]["execution_eligible_symbol_days"] == 0
    assert report["coverage"]["minute_partition_denominator"].startswith("UNKNOWN")
    assert "MISSING_CANDIDATE_MINUTE_1M_D" not in report["coverage"]["preselection_blocked_candidate_rows_by_reason"]
    assert report["execution_dataset_inventory"]["required_H02_dataset_status"]["candidate_minute_1m_d"] == "NOT_PRESENT_IN_SELECTED_ARTIFACTS"
    assert report["daily_candidate_diagnostics_columns"][2] == "candidate_partition_sha256"
    assert len(report["daily_candidate_diagnostics"][0][2]) == 64
    assert report["daily_candidate_diagnostics"][0][4] == 31


def test_duplicate_symbol_day_fails_closed(tmp_path):
    with pytest.raises(ArtifactAuditError, match="duplicate candidate symbols"):
        audit_artifacts(make_artifacts(tmp_path, duplicate_period="2024h1"))


def test_raw_hash_mismatch_fails_closed(tmp_path):
    with pytest.raises(ArtifactAuditError, match="raw hash mismatch"):
        audit_artifacts(make_artifacts(tmp_path, corrupt_period="2024h1"))


def test_protected_period_partition_is_rejected_before_reading_data(tmp_path):
    path = tmp_path / "h01-raw-2024h1.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("raw/limit_up/20260701.parquet", b"must not read")
    with pytest.raises(ArtifactAuditError, match="post-development"):
        audit_artifacts([path])
