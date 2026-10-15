"""Runtime inference *scaffold*, wholly separate from offline Codex research.

No network transport and no trading integration. Produces auditable, typed
human-review decisions at a fixed as-of cutoff with deterministic hard gates.
DeepSeek/Jev may later supply *advisory outputs* without changing hard rules.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from hashlib import sha256
from pathlib import Path
import json
from typing import Any

from .strategy import select_core

REGIMES = frozenset({"ATTACK", "TRIAL", "NEUTRAL", "RETREAT", "ICE", "UNKNOWN"})
PROTECTED_START = "2026-07-01"
PROTECTED_END = "2026-09-28"


@dataclass(frozen=True)
class RuntimeSnapshot:
    """Only completed, attributed evidence; no private holdings to models."""
    decision_at: str  # ISO8601 with offset in China time
    evidence_available_at: str  # ISO8601 with timezone
    evidence_quality: str  # VERIFIED_ASOF / UNVERIFIED
    source_day: str  # previous completed exchange session (trade date)
    market_regime: str  # determined by frozen state engine
    previous_day_events: dict[str, Any]  # D-1 known, not D closing pool
    core_confirmed_asof: bool = False  # from lawful D intraday confirmation
    market_hard_veto: bool = False
    held_symbol: str | None = None
    prior_holding_exit_due: bool = False
    symbol_tradable: bool = True
    candidate_data_quality: str = "VERIFIED_ASOF"
    historical_replay: bool = True


def load_runtime_config(path: str | Path = "config/runtime.json") -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "logic-b-runtime-v0.1":
        raise ValueError("unknown runtime contract")
    if data.get("orders_transmitted") != 0 or not data.get("hard_rules", {}).get("risk_gate_cannot_be_overridden"):
        raise ValueError("unsafe runtime configuration")
    if data.get("roles", {}).get("codex", {}).get("used_in_runtime") is not False:
        raise ValueError("offline Codex cannot be required for synchronous runtime")
    if data.get("roles", {}).get("deterministic", {}).get("hard_gate_authority") is not True:
        raise ValueError("deterministic hard risk gate required")
    if data.get("degraded_mode") != "NO_FOLLOW":
        raise ValueError("unvalidated degraded mode")
    return data


def _timestamp(value: str, field: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(hours=8):
        raise ValueError(f"{field} must be UTC+08:00 China exchange time")
    return stamp


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def _validate(snapshot: RuntimeSnapshot):
    now = _timestamp(snapshot.decision_at, "decision_at")
    avail = _timestamp(snapshot.evidence_available_at, "evidence_available_at")
    day = now.date().isoformat()
    if now.strftime("%H:%M") != "09:35":
        raise ValueError("wrong decision checkpoint; not a 09:35 assessment")
    if snapshot.historical_replay and (day < "2020-01-01" or day > "2026-06-30"):
        raise ValueError("historical replay outside authorized 2020-2026 development")
    if PROTECTED_START <= day <= PROTECTED_END:
        raise ValueError("protected historical date may not be replayed or backfilled")
    if not snapshot.historical_replay and day <= PROTECTED_END:
        raise ValueError("forward runtime cannot masquerade as prior/protected history")
    if avail > now:
        raise ValueError("future evidence not available at decision time")
    source = date.fromisoformat(snapshot.source_day)
    if source >= now.date():
        raise ValueError("previous-day pool must strictly predate decision day")
    event_day = snapshot.previous_day_events.get("date")
    if event_day is not None and event_day != snapshot.source_day:
        raise ValueError("vendor prior-day events do not match declared source_day")
    if snapshot.market_regime not in REGIMES:
        raise ValueError("unknown market regime")
    if snapshot.held_symbol and snapshot.core_confirmed_asof and not snapshot.previous_day_events:
        raise ValueError("candidate evidence missing")
    return day


def decide_runtime(snapshot: RuntimeSnapshot, *, research_strategy: dict,
                   config: dict | None = None,
                   jev_advisory: dict | None = None,
                   deepseek_advisory: dict | None = None) -> dict[str, Any]:
    """Dry-run human-review output; *cannot* transmit any broker order."""
    cfg = config if config is not None else load_runtime_config()
    load_runtime_config_verified = (
        cfg.get("orders_transmitted") == 0
        and cfg.get("hard_rules", {}).get("risk_gate_cannot_be_overridden") is True
        and cfg.get("roles", {}).get("codex", {}).get("used_in_runtime") is False
        and cfg.get("roles", {}).get("deterministic", {}).get("hard_gate_authority") is True
        and cfg.get("degraded_mode") == "NO_FOLLOW"
    )
    if not load_runtime_config_verified:
        raise ValueError("unsafe policy: runtime may never bypass deterministic controls")
    day = _validate(snapshot)
    snap_hash = _digest(asdict(snapshot))
    policy_hash = _digest({"cfg": cfg, "strategy":research_strategy})
    reason = "UNSET"
    selected = None
    action = "CASH"
    # The held position belongs to a deterministic execution state machine;
    # never call it a filled SELL; this is just a review decision intent.
    if snapshot.held_symbol:
        action = "SELL" if snapshot.prior_holding_exit_due else "HOLD"
        reason = "EXIT_DUE_REVIEW_EXECUTION_SEPARATELY" if snapshot.prior_holding_exit_due else "HELD_POSITION"
    elif (snapshot.market_regime in {"RETREAT", "ICE", "UNKNOWN"}
          or snapshot.market_hard_veto):
        reason = "MARKET_RISK_VETO"
    elif snapshot.evidence_quality != "VERIFIED_ASOF" or snapshot.candidate_data_quality != "VERIFIED_ASOF":
        reason = "STALE_OR_UNVERIFIED_EVIDENCE"
    elif cfg.get("promotion", {}).get("approved_strategy_sha") is None:
        reason = "STRATEGY_NOT_PROMOTED"
    elif not snapshot.core_confirmed_asof:
        reason = "NO_LEGAL_0935_CORE_CONFIRMATION"
    elif not snapshot.symbol_tradable:
        reason = "CANDIDATE_NOT_TRADABLE"
    else:
        symbol, select_reason = select_core(snapshot.previous_day_events,
                                            research_strategy.get("baseline", {}))
        if symbol:
            selected = symbol
            action = "BUY_CORE"
            reason = "REVIEW_CORE_ONLY_" + select_reason
        else:
            reason = select_reason

    # Provider-advisories are inert unless a *separate validated route and
    # explicit approval* is implemented. No implicit promotion of confidence.
    advisory_states = {
        "jev": "DISABLED" if not cfg["roles"]["jev_typesafe"]["enabled"] else "SHADOW_ONLY",
        "deepseek": "DISABLED" if not cfg["roles"]["deepseek"]["enabled"] else "SHADOW_ONLY",
    }
    return {
        "schema_version":"logic-b-runtime-decision-v0.1",
        "stage": "RUNTIME_SHADOW_REVIEW_NOT_LIVE_ORDERS",
        "trade_date": day,
        "decision_at": snapshot.decision_at,
        "action": action,
        "review_status": "MANUAL_REVIEW_ONLY" if action == "BUY_CORE" else "NO_FOLLOW",
        "selected_core": selected,
        "reason": reason,
        "regime": snapshot.market_regime,
        "advisory_status": advisory_states,
        "jev_advisory_supplied": jev_advisory is not None,
        "deepseek_advisory_supplied": deepseek_advisory is not None,
        "advisory_can_override_risk_gate": False,
        "model_calls_executed": 0,
        "orders_transmitted": 0,
        "data_snapshot_sha256": snap_hash,
        "policy_sha256": policy_hash,
    }
