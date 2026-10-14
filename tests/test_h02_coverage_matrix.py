from copy import deepcopy

import pytest

from logic_b.h02_coverage_matrix import (
    CoverageMatrixInvalid,
    canonical_coverage_json,
    canonicalize_coverage_matrix,
)


def layer(*, ready=True):
    return {
        "present": ready,
        "structurally_valid": ready,
        "provenance_valid": ready,
        "PIT_certified": ready,
        "execution_ready": ready,
    }


def fixture_report():
    evidence = {name: layer() for name in (
        "calendar", "candidate_d_minus_1", "independent_daily_d",
        "reference_st_d", "reference_halt_d", "official_price_limits_d",
        "candidate_minute_1m_d",
    )}
    evidence["candidate_minute_1m_d"]["fill_certified"] = True
    evidence["candidate_minute_1m_d"]["direct_normalized_sha256"] = "0" * 64
    return {
        "schema_version": "h02-coverage-matrix-v1",
        "scope": {"trade_date": "2020-01-03", "protected_holdout_accessed": False},
        "rows": [{"trade_date": "2020-01-03", "symbol": "000998.SZ", "evidence": evidence,
                  "cross_provider_daily_minute": {"status": "MATCH_TICK_TOLERANCE"}}],
    }


def test_same_matrix_input_has_byte_identical_fixed_schema_output():
    report = fixture_report()
    first = canonical_coverage_json(report)
    second = canonical_coverage_json(deepcopy(report))
    assert first == second
    normalized = canonicalize_coverage_matrix(report)
    assert normalized["aggregate"]["execution_ready_rows"] == 1
    assert normalized["rows"][0]["execution_ready"] is True


def test_bad_official_limit_fixture_cannot_become_execution_ready():
    report = fixture_report()
    report["rows"][0]["evidence"]["official_price_limits_d"] = layer(ready=False)
    # Simulate a stale or malicious upstream claim; the serializer recomputes it.
    report["rows"][0]["execution_ready"] = True
    report["rows"][0]["evidence"]["official_price_limits_d"]["execution_ready"] = True
    result = canonicalize_coverage_matrix(report)
    assert result["rows"][0]["evidence"]["official_price_limits_d"]["execution_ready"] is False
    assert result["rows"][0]["execution_ready"] is False
    assert result["aggregate"]["execution_ready_rows"] == 0


def test_protected_holdout_dates_are_rejected():
    report = fixture_report()
    report["rows"][0]["trade_date"] = "2026-07-01"
    with pytest.raises(CoverageMatrixInvalid, match="protected holdout"):
        canonicalize_coverage_matrix(report)


def test_duplicate_symbol_days_are_rejected():
    report = fixture_report()
    report["rows"].append(deepcopy(report["rows"][0]))
    with pytest.raises(CoverageMatrixInvalid, match="duplicate symbol-day"):
        canonicalize_coverage_matrix(report)


def test_cross_provider_discrepancy_blocks_otherwise_ready_fixture():
    report = fixture_report()
    report["rows"][0]["cross_provider_daily_minute"]["status"] = "REVIEW_DAILY_MINUTE_MISMATCH"
    result = canonicalize_coverage_matrix(report)
    assert result["rows"][0]["execution_ready"] is False
    assert result["aggregate"]["execution_ready_rows"] == 0
