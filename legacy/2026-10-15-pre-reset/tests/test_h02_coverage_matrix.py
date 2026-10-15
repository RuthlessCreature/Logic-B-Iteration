from copy import deepcopy
import json
from pathlib import Path

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
        "scope": {"candidate_date": "2020-01-02", "trade_date": "2020-01-03", "protected_holdout_accessed": False,
                  "sample_size_symbol_days": 1, "sample_symbols": ["000998.SZ"]},
        "rows": [{"candidate_date": "2020-01-02", "trade_date": "2020-01-03", "symbol": "000998.SZ", "evidence": evidence,
                  "cross_provider_daily_minute": {"status": "MATCH_TICK_TOLERANCE"}}],
    }


def test_same_matrix_input_has_byte_identical_fixed_schema_output():
    report = fixture_report()
    first = canonical_coverage_json(report)
    second = canonical_coverage_json(deepcopy(report))
    assert first == second
    normalized = canonicalize_coverage_matrix(report)
    assert normalized["aggregate"]["execution_ready_rows"] == 0
    assert normalized["aggregate"]["overall_gate"] == "BLOCKED_UNVERIFIED_EXECUTION_CERTIFICATION"
    assert normalized["rows"][0]["execution_ready"] is False
    assert normalized["rows"][0]["evidence"]["candidate_minute_1m_d"]["fill_certified"] is False
    assert normalized["aggregate"]["independently_verified_PIT_rows"] == 0


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


@pytest.mark.parametrize("claim", ["PIT_certified", "fill_certified", "execution_ready"])
def test_upstream_claims_and_placeholder_hash_never_certify_execution(claim):
    report = fixture_report()
    row = report["rows"][0]
    if claim == "fill_certified":
        row["evidence"]["candidate_minute_1m_d"][claim] = True
    elif claim == "execution_ready":
        row["execution_ready"] = True
    else:
        for state in row["evidence"].values():
            state[claim] = True
    row["evidence"]["candidate_minute_1m_d"]["direct_normalized_sha256"] = "0" * 64
    row["cross_provider_daily_minute"]["status"] = "MATCH_TICK_TOLERANCE"
    result = canonicalize_coverage_matrix(report)
    assert result["rows"][0]["execution_ready"] is False
    assert result["aggregate"]["execution_ready_rows"] == 0
    assert result["aggregate"]["overall_gate"] != "READY"
    assert result["aggregate"]["independently_verified_PIT_rows"] == 0
    assert result["aggregate"]["PIT_certified_rows"] == 0
    assert result["aggregate"]["fill_verified_rows"] == 0
    assert result["aggregate"]["minute_normalized_sha_verified_rows"] == 0
    if claim == "PIT_certified":
        assert result["aggregate"]["claimed_PIT_rows"] == 1
        assert result["rows"][0]["evidence"]["calendar"]["PIT_claimed"] is True
        assert result["rows"][0]["evidence"]["calendar"]["PIT_certified"] is False
    if claim == "fill_certified":
        assert result["aggregate"]["fill_claimed_rows"] == 1


def test_top_level_and_row_dates_must_match():
    report = fixture_report()
    report["scope"]["candidate_date"] = "2020-01-01"
    with pytest.raises(CoverageMatrixInvalid, match="candidate_date conflicts"):
        canonicalize_coverage_matrix(report)


def test_scope_candidate_date_is_validated_and_protected():
    report = fixture_report()
    report["scope"]["candidate_date"] = "2026-07-01"
    with pytest.raises(CoverageMatrixInvalid, match="protected holdout"):
        canonicalize_coverage_matrix(report)


@pytest.mark.parametrize("scope_key,value", [
    ("sample_size_symbol_days", 2),
    ("sample_symbols", ["600000.SH"]),
])
def test_declared_sample_denominator_must_match_rows(scope_key, value):
    report = fixture_report()
    report["scope"][scope_key] = value
    with pytest.raises(CoverageMatrixInvalid, match="conflicts with rows|conflicts with row symbols"):
        canonicalize_coverage_matrix(report)


def test_retained_p2a_sample_remains_blocked():
    path = Path(__file__).parents[1] / "research/experiments/h02-stage0-20261013/P2A_COVERAGE_MATRIX_20261014.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    result = canonicalize_coverage_matrix(report)
    assert result["aggregate"]["candidate_symbol_days_in_sample"] == 3
    assert result["aggregate"]["execution_ready_rows"] == 0
    assert result["aggregate"]["overall_gate"] == "BLOCKED_UNVERIFIED_EXECUTION_CERTIFICATION"
