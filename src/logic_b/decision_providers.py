"""Typed decision-provider boundary: TypeSafe AI Jev reserved/off by default.

Jev is *not* a generative LLM. It is a possible future decision primitive
for optional choice / score / noul evidence, NEVER an execution/permission gate.
The actual HTTP transport is intentionally not implemented or enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Callable, Protocol

FIRST = "2020-01-01"
LAST = "2026-06-30"
REGIMES = ("ATTACK", "TRIAL", "NEUTRAL", "RETREAT", "ICE")
ALLOWED_TASKS = ("advisory_market_regime", "advisory_tail_risk_score",
                 "advisory_negative_feedback")


class DecisionProviderDisabled(RuntimeError):
    pass


class DecisionProviderNotAuthorized(RuntimeError):
    pass


class DecisionProviderNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class DecisionRequest:
    """Market evidence with verified as-of. No future or protected market rows."""
    asof: str
    state: dict[str, Any]
    task: str = "advisory_market_regime"
    scope: str = "historical_replay"  # forward_live reserved for post-protected future trading


@dataclass(frozen=True)
class DecisionResponse:
    provider: str
    model: str
    task: str
    answers: dict[str, Any]
    request_sha256: str
    response_sha256: str
    usage: dict[str, Any] | None
    authority: str = "ADVISORY_ONLY_NO_ORDER_NO_MARKET_GATE_OVERRIDE"
    connected: bool = False


class DecisionProvider(Protocol):
    def evaluate(self, request: DecisionRequest) -> DecisionResponse:
        ...


def _digest(payload: Any) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def load_decision_registry(path: str | Path = "config/decision_providers.json") -> dict:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("active_provider") != "deterministic":
        raise ValueError("Changing primary decision provider requires separate authorization")
    jev = obj.get("providers", {}).get("jev_typesafe")
    if jev is None or jev.get("decision_authority") != "ADVISORY_ONLY_NO_ORDER_NO_MARKET_GATE_OVERRIDE":
        raise ValueError("Decision-provider safety policy absent")
    return obj


def validate_decision_request(req: DecisionRequest) -> None:
    try:
        t = datetime.fromisoformat(req.asof)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid asof timestamp") from exc
    if t.tzinfo is None:
        raise ValueError("asof timestamp must carry timezone")
    trade_date = t.date().isoformat()
    if req.scope == "historical_replay":
        if not FIRST <= trade_date <= LAST:
            raise ValueError("asof beyond authorized 2020-2026 history")
    elif req.scope == "forward_live":
        # Future online production has a *different* time domain from backtest.
        # This NEVER unlocks the original protected historical 2026Q3 holdout.
        if trade_date <= "2026-09-28":
            raise ValueError("forward runtime cannot replay protected or historical dates")
    else:
        raise ValueError("unknown decision scope")
    if req.task not in ALLOWED_TASKS or not isinstance(req.state, dict):
        raise ValueError("unknown decision task or state")
    # Explicit allowlist prevents passing future bars, private holdings,
    # LLM context, unfiltered historical data or credentials.
    allowed = {"trade_date", "evidence_asof", "market_breadth", "limit_up_count",
               "limit_down_count", "broken_limit_count", "prior_core_failure_rate",
               "negative_feedback_count", "recent_momentum", "source_quality"}
    if set(req.state).difference(allowed) or req.state.get("trade_date") != trade_date:
        raise ValueError("state includes unvetted or different-day fields")
    if req.state.get("source_quality") != "VERIFIED_ASOF":
        raise ValueError("unverified as-of market data cannot be sent to decision models")
    observation = req.state.get("evidence_asof")
    try:
        obs = datetime.fromisoformat(observation)
    except (TypeError, ValueError) as exc:
        raise ValueError("missing evidence_asof") from exc
    if obs.tzinfo is None or obs > t:
        raise ValueError("feature evidence after decision cutoff")
    # Only aggregate JSON-safe scalars; never provide raw/private datasets.
    json.dumps(req.state, allow_nan=False)


def build_jev_questions(task: str) -> dict:
    """Per official TypeSafe OpenAPI: state + typed questions, no prose response."""
    if task == "advisory_market_regime":
        return {"market_regime": {
            "type": "choice",
            "instructions": "As a purely exploratory classification, which market regime best describes the time-valid evidence? Never override rule-based risk vetoes.",
            "criteria": {name: desc for name, desc in {
                "ATTACK": "Broadening momentum, positive follow-through, manageable losses",
                "TRIAL": "Potential early recovery but incomplete confirmation",
                "NEUTRAL": "Mixed evidence; no clear validated advantage",
                "RETREAT": "Worsening negative feedback and market risk",
                "ICE": "Severe loss breadth and liquidity stress",
            }.items()},
        }}
    if task == "advisory_tail_risk_score":
        return {"tail_risk": {
            "type": "score", "instructions": "Rate the evidence for next-session negative-tail and locked-exit exposure; this is only a research annotation.",
            "criteria": ["Low observed stress", "Some warning signs",
                         "Substantial negative feedback", "Severe marketwide stress"],
        }}
    if task == "advisory_negative_feedback":
        return {"negative_feedback": {
            "type": "noul",
            "instructions": "Does the time-valid market evidence support material propagation of negative feedback from previous strong stocks?",
            "criteria": {"true": "Evidence supports broadening negative feedback",
                         "false": "Evidence does not support broadening negative feedback"},
        }}
    raise ValueError("unknown task")


def validate_jev_answers(questions: dict, answers: dict) -> None:
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ValueError("TypeSafe returned missing/extra answers")
    for name, question in questions.items():
        answer = answers[name]
        if not isinstance(answer, dict) or answer.get("type") != question["type"]:
            raise ValueError("mismatched answer type")
        kind = question["type"]
        if kind == "choice":
            if answer.get("choice") not in question["criteria"]:
                raise ValueError("out-of-schema choice")
            if type(answer.get("confidence")) not in (int, float) or not 0 <= answer["confidence"] <= 1:
                raise ValueError("invalid confidence")
            probs = answer.get("probabilities")
            if not isinstance(probs, dict) or set(probs) != set(question["criteria"]):
                raise ValueError("invalid choice distribution")
            if any(type(p) not in (int, float) or not 0 <= p <= 1 for p in probs.values()):
                raise ValueError("invalid probabilities")
        elif kind == "noul":
            value = answer.get("noul")
            if type(value) not in (int, float) or not 0 <= value <= 1:
                raise ValueError("invalid noul probability")
        elif kind == "score":
            value, confidence = answer.get("score"), answer.get("confidence")
            if type(value) not in (int, float) or not 0 <= value <= len(question["criteria"]) - 1:
                raise ValueError("invalid score")
            if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
                raise ValueError("invalid score confidence")
        else:
            raise ValueError("unsupported answer kind")


class TypeSafeJevProvider:
    """Explicitly disabled until the user authorizes paid API/credential use."""
    def __init__(self, config: dict | None = None, *, allow_external_calls: bool = False,
                 transport: Callable[..., dict] | None = None):
        default = load_decision_registry()["providers"]["jev_typesafe"]
        self.config = default if config is None else config
        self.allow_external_calls = allow_external_calls
        self.transport = transport

    def evaluate(self, request: DecisionRequest) -> DecisionResponse:
        if self.config.get("enabled") is not True:
            raise DecisionProviderDisabled("PROVIDER_DISABLED: TypeSafe Jev reserved and offline")
        validate_decision_request(request)
        if not self.allow_external_calls or self.config.get("allow_external_calls") is not True:
            raise DecisionProviderNotAuthorized("NETWORK_NOT_AUTHORIZED")
        model = self.config.get("model")
        if not isinstance(model, str) or not model:
            raise DecisionProviderNotConfigured("Set a verified TypeSafe model from GET /v1/models")
        if self.config.get("credential_env") != "TYPESAFE_API_KEY":
            raise DecisionProviderNotConfigured("TYPESAFE_API_KEY policy required")
        secret = os.environ.get("TYPESAFE_API_KEY")
        if not secret:
            raise DecisionProviderNotConfigured("TYPESAFE_API_KEY missing")
        if self.transport is None:
            raise DecisionProviderNotAuthorized("TRANSPORT_NOT_IMPLEMENTED: enable only after explicit integration review")
        questions = build_jev_questions(request.task)
        payload = {"model": model, "state": request.state, "questions": questions}
        # Injected transport is only for OFFLINE mock tests. No production
        # urllib/requests implementation exists at this stage.
        result = self.transport(payload=payload, api_key=secret,
                                endpoint=self.config["endpoint"])
        if not isinstance(result, dict):
            raise ValueError("invalid model result")
        answers = result.get("answers")
        validate_jev_answers(questions, answers)
        return DecisionResponse("jev_typesafe", result.get("model", model),
            request.task, answers, _digest(payload), _digest(result),
            result.get("usage"), connected=False)


def get_decision_provider(name: str = "jev_typesafe") -> DecisionProvider:
    if name != "jev_typesafe":
        raise ValueError("unknown named provider; no silent fallback")
    return TypeSafeJevProvider()
