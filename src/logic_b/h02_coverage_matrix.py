"""Deterministic, fail-closed serialization for H02 coverage evidence."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROTECTED_CUTOFF = "20260630"
EVIDENCE_LAYERS = (
    "calendar",
    "candidate_d_minus_1",
    "independent_daily_d",
    "reference_st_d",
    "reference_halt_d",
    "official_price_limits_d",
    "candidate_minute_1m_d",
)
STATUS_FIELDS = (
    "present",
    "structurally_valid",
    "provenance_valid",
    "PIT_certified",
    "execution_ready",
)


class CoverageMatrixInvalid(ValueError):
    """Coverage evidence is malformed or crosses the protected cutoff."""


def _date_token(value: Any) -> str:
    token = str(value).replace("-", "")
    if len(token) != 8 or not token.isdigit():
        raise CoverageMatrixInvalid(f"invalid trade date: {value}")
    if token > PROTECTED_CUTOFF:
        raise CoverageMatrixInvalid("protected holdout date rejected")
    return token


def canonicalize_coverage_matrix(report: dict[str, Any]) -> dict[str, Any]:
    """Validate fixed evidence layers and derive readiness from their statuses.

    Caller-provided `execution_ready` values are never trusted. Every required
    layer must pass all evidence statuses; the minute layer also needs explicit
    fill certification. The function does not promote source presence to PIT
    or execution evidence.
    """
    if report.get("schema_version") != "h02-coverage-matrix-v1":
        raise CoverageMatrixInvalid("unsupported coverage matrix schema")
    scope = report.get("scope", {})
    if scope.get("protected_holdout_accessed") is not False:
        raise CoverageMatrixInvalid("protected holdout access must remain false")
    if scope.get("trade_date") is not None:
        _date_token(scope["trade_date"])
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise CoverageMatrixInvalid("rows must be a list")

    normalized_rows = []
    seen = set()
    for original in rows:
        if not isinstance(original, dict) or not isinstance(original.get("evidence"), dict):
            raise CoverageMatrixInvalid("each row requires an evidence object")
        row = dict(original)
        token = _date_token(row.get("trade_date"))
        row["trade_date"] = f"{token[:4]}-{token[4:6]}-{token[6:]}"
        symbol = str(row.get("symbol", ""))
        if len(symbol) != 9 or symbol[6] != "." or not symbol[:6].isdigit() or symbol[7:] not in ("SH", "SZ"):
            raise CoverageMatrixInvalid(f"invalid symbol: {symbol}")
        key = (token, symbol)
        if key in seen:
            raise CoverageMatrixInvalid(f"duplicate symbol-day: {key}")
        seen.add(key)

        evidence = dict(row["evidence"])
        layer_ready = []
        for layer in EVIDENCE_LAYERS:
            state = evidence.get(layer)
            if not isinstance(state, dict):
                raise CoverageMatrixInvalid(f"missing evidence layer: {layer}")
            state = dict(state)
            for field in STATUS_FIELDS:
                if field not in state:
                    raise CoverageMatrixInvalid(f"missing {layer}.{field}")
                if not isinstance(state[field], bool):
                    raise CoverageMatrixInvalid(f"{layer}.{field} must be boolean")
            if layer == "candidate_minute_1m_d":
                if not isinstance(state.get("fill_certified"), bool):
                    raise CoverageMatrixInvalid("candidate_minute_1m_d.fill_certified must be boolean")
                digest = state.get("direct_normalized_sha256")
                if state["present"] and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                    raise CoverageMatrixInvalid("present minute evidence requires a normalized SHA256")
            ready = all(state[field] for field in STATUS_FIELDS[:-1])
            if layer == "candidate_minute_1m_d":
                ready = ready and state.get("fill_certified") is True
            state["execution_ready"] = ready
            layer_ready.append(ready)
            evidence[layer] = state

        row["evidence"] = evidence
        cross_check = row.get("cross_provider_daily_minute", {})
        row["execution_ready"] = (
            all(layer_ready)
            and cross_check.get("status") == "MATCH_TICK_TOLERANCE"
        )
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
        "execution_ready_rows": sum(bool(r["execution_ready"]) for r in normalized_rows),
        "overall_gate": "READY" if normalized_rows and all(r["execution_ready"] for r in normalized_rows) else "BLOCKED_INCOMPLETE_PROVENANCE_AND_EXECUTION_EVIDENCE",
    })
    normalized["aggregate"] = aggregate
    return normalized


def canonical_coverage_json(report: dict[str, Any]) -> str:
    """Return byte-stable JSON for the same validated matrix input."""
    normalized = canonicalize_coverage_matrix(report)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_coverage_matrix(report: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(canonical_coverage_json(report), encoding="utf-8", newline="\n")
