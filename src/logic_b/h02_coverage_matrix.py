"""Deterministic, fail-closed serialization for H02 coverage evidence."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


PROTECTED_CUTOFF = "20260630"
EVIDENCE_LAYERS = (
    "calendar", "candidate_d_minus_1", "independent_daily_d",
    "reference_st_d", "reference_halt_d", "official_price_limits_d",
    "candidate_minute_1m_d",
)
STATUS_FIELDS = ("present", "structurally_valid", "provenance_valid", "PIT_certified", "execution_ready")


class CoverageMatrixInvalid(ValueError):
    """Coverage evidence is malformed or crosses the protected cutoff."""


def _date_token(value: Any, label: str) -> str:
    token = str(value).replace("-", "")
    if len(token) != 8 or not token.isdigit():
        raise CoverageMatrixInvalid(f"invalid {label}: {value}")
    try:
        date(int(token[:4]), int(token[4:6]), int(token[6:]))
    except ValueError as exc:
        raise CoverageMatrixInvalid(f"invalid {label}: {value}") from exc
    if token > PROTECTED_CUTOFF:
        raise CoverageMatrixInvalid("protected holdout date rejected")
    return token


def canonicalize_coverage_matrix(report: dict[str, Any]) -> dict[str, Any]:
    """Validate coverage claims and derive a fail-closed execution gate.

    Upstream booleans, status labels, and digest-shaped strings are claims, not
    execution certificates. This module has no trusted source/PIT/fill proof
    verifier, so it reports coverage separately and never emits formal READY.
    """
    if report.get("schema_version") != "h02-coverage-matrix-v1":
        raise CoverageMatrixInvalid("unsupported coverage matrix schema")
    scope = report.get("scope", {})
    if not isinstance(scope, dict) or scope.get("protected_holdout_accessed") is not False:
        raise CoverageMatrixInvalid("protected holdout access must remain false")
    candidate = _date_token(scope.get("candidate_date"), "scope.candidate_date")
    trade = _date_token(scope.get("trade_date"), "scope.trade_date")
    if candidate >= trade:
        raise CoverageMatrixInvalid("scope.candidate_date must precede scope.trade_date")
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise CoverageMatrixInvalid("rows must be a list")

    normalized_rows = []
    seen = set()
    for original in rows:
        if not isinstance(original, dict) or not isinstance(original.get("evidence"), dict):
            raise CoverageMatrixInvalid("each row requires an evidence object")
        row = dict(original)
        token = _date_token(row.get("trade_date"), "row.trade_date")
        row_candidate = _date_token(row.get("candidate_date"), "row.candidate_date")
        if token != trade:
            raise CoverageMatrixInvalid("row.trade_date conflicts with scope.trade_date")
        if row_candidate != candidate:
            raise CoverageMatrixInvalid("row.candidate_date conflicts with scope.candidate_date")
        row["trade_date"] = f"{token[:4]}-{token[4:6]}-{token[6:]}"
        row["candidate_date"] = f"{row_candidate[:4]}-{row_candidate[4:6]}-{row_candidate[6:]}"
        symbol = str(row.get("symbol", ""))
        if len(symbol) != 9 or symbol[6] != "." or not symbol[:6].isdigit() or symbol[7:] not in ("SH", "SZ"):
            raise CoverageMatrixInvalid(f"invalid symbol: {symbol}")
        key = (token, symbol)
        if key in seen:
            raise CoverageMatrixInvalid(f"duplicate symbol-day: {key}")
        seen.add(key)

        evidence = dict(row["evidence"])
        for layer in EVIDENCE_LAYERS:
            state = evidence.get(layer)
            if not isinstance(state, dict):
                raise CoverageMatrixInvalid(f"missing evidence layer: {layer}")
            state = dict(state)
            for field in STATUS_FIELDS:
                if field not in state or not isinstance(state[field], bool):
                    raise CoverageMatrixInvalid(f"{layer}.{field} must be boolean")
            if layer == "candidate_minute_1m_d" and not isinstance(state.get("fill_certified"), bool):
                raise CoverageMatrixInvalid("candidate_minute_1m_d.fill_certified must be boolean")
            # Coverage is descriptive only; all execution-related upstream
            # claims are forcibly cleared pending independent verification.
            state["execution_ready"] = False
            if layer == "candidate_minute_1m_d":
                state["fill_certified"] = False
            evidence[layer] = state

        row["evidence"] = evidence
        row["execution_ready"] = False
        normalized_rows.append(row)

    normalized_rows.sort(key=lambda item: (item["trade_date"], item["symbol"]))
    normalized = dict(report)
    normalized["rows"] = normalized_rows
    n = len(normalized_rows)
    aggregate = dict(report.get("aggregate", {}))
    aggregate.update({
        "candidate_symbol_days_in_sample": n,
        "minute_partitions_present": sum(bool(r["evidence"]["candidate_minute_1m_d"]["present"]) for r in normalized_rows),
        "minute_structural_sample_rows": sum(bool(r["evidence"]["candidate_minute_1m_d"]["structurally_valid"]) for r in normalized_rows),
        "independent_daily_rows": sum(bool(r["evidence"]["independent_daily_d"]["present"]) for r in normalized_rows),
        "official_price_limit_rows": sum(bool(r["evidence"]["official_price_limits_d"]["present"]) for r in normalized_rows),
        "PIT_certified_rows": sum(all(r["evidence"][layer]["PIT_certified"] for layer in EVIDENCE_LAYERS) for r in normalized_rows),
        "execution_ready_rows": 0,
        "overall_gate": "BLOCKED_UNVERIFIED_EXECUTION_CERTIFICATION",
    })
    normalized["aggregate"] = aggregate
    return normalized


def canonical_coverage_json(report: dict[str, Any]) -> str:
    return json.dumps(canonicalize_coverage_matrix(report), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_coverage_matrix(report: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(canonical_coverage_json(report), encoding="utf-8", newline="\n")
