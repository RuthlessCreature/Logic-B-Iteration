"""Future daily DeepSeek contextual inference interface; distinct from offline research.

Strictly no network unless user explicitly enables the provider AND authorizes
external use AND supplies credentials/model + reviewed transport. Default OFF.
No assumption that language-model market descriptions predict actual prices.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
import os
from typing import Any, Callable, Protocol

from .runtime import PROTECTED_END

class RuntimeModelDisabled(RuntimeError):
    pass
class RuntimeModelUnauthorized(RuntimeError):
    pass
class RuntimeModelNotConfigured(RuntimeError):
    pass

@dataclass(frozen=True)
class ContextRequest:
    decision_at: str
    evidence_available_at: str
    trade_date: str
    feature_snapshot: dict[str, Any]
    evidence_quality: str = "VERIFIED_ASOF"
    scope: str = "historical_replay"

@dataclass(frozen=True)
class ContextResponse:
    provider: str
    model: str
    context_tags: tuple[str, ...]
    risk_flags: tuple[str, ...]
    feature_ids: tuple[str, ...]
    rationale_short: str
    confidence: float
    input_sha256: str
    output_sha256: str
    connected: bool = False
    authority: str = "ADVISORY_ONLY_NO_HARD_GATE_OVERRIDE"

class RuntimeContextProvider(Protocol):
    def infer(self, request: ContextRequest) -> ContextResponse: ...

def _stamp(s):
    try:
        dt = datetime.fromisoformat(s)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid model request timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() != timedelta(hours=8):
        raise ValueError("runtime context requires explicit China timezone")
    return dt

def validate_context_request(req: ContextRequest):
    decision = _stamp(req.decision_at)
    available = _stamp(req.evidence_available_at)
    day = decision.date().isoformat()
    if decision.strftime("%H:%M") != "09:35" or day != req.trade_date:
        raise ValueError("decision checkpoint/trade date mismatch")
    if available > decision:
        raise ValueError("future evidence after runtime decision")
    if req.scope == "historical_replay":
        if not "2020-01-01" <= day <= "2026-06-30":
            raise ValueError("historical request outside permitted research window")
    elif req.scope == "forward_live":
        if day <= PROTECTED_END:
            raise ValueError("protected/historical data not allowed in future runtime")
    else:
        raise ValueError("unapproved runtime context scope")
    if req.evidence_quality != "VERIFIED_ASOF":
        raise ValueError("unverified feature availability")
    # Only aggregate and already timestamp-verified features cross provider boundary:
    # no account, orders, raw stock ticks, private keys, historical future labels.
    allowed = {"market_regime", "market_breadth", "limit_up_count",
               "limit_down_count", "broken_limit_count",
               "negative_feedback_count", "sector_breadth",
               "feature_ids", "source_quality"}
    if not isinstance(req.feature_snapshot, dict) or set(req.feature_snapshot).difference(allowed):
        raise ValueError("unapproved/private feature field")
    if req.feature_snapshot.get("source_quality") != "VERIFIED_ASOF":
        raise ValueError("source quality unverified")
    features = req.feature_snapshot.get("feature_ids", [])
    if not isinstance(features, list) or not all(
            isinstance(x,str) and 1 <= len(x) <= 100 for x in features):
        raise ValueError("invalid feature IDs")
    json.dumps(req.feature_snapshot, sort_keys=True, allow_nan=False)

def _digest(payload):
    return sha256(json.dumps(payload,sort_keys=True,allow_nan=False,
                             ensure_ascii=False,separators=(",", ":")).encode()).hexdigest()

def validate_context_response(obj, allowed_feature_ids):
    if not isinstance(obj,dict) or set(obj) != {
        "context_tags","risk_flags","supporting_feature_ids",
        "rationale_short","confidence"
    }:
        raise ValueError("untrusted runtime LLM output shape")
    for k in ("context_tags","risk_flags","supporting_feature_ids"):
        a=obj[k]
        if not isinstance(a,list) or len(a)>8 or not all(
            isinstance(v,str) and 1<=len(v)<=80 for v in a):
            raise ValueError("invalid runtime context tags")
    if not set(obj["supporting_feature_ids"]).issubset(set(allowed_feature_ids)):
        raise ValueError("invented evidence reference")
    if not isinstance(obj["rationale_short"],str) or len(obj["rationale_short"])>400:
        raise ValueError("invalid runtime model rationale")
    if type(obj["confidence"]) not in (int,float) or not 0<=obj["confidence"]<=1:
        raise ValueError("invalid confidence")
    return obj

class DeepSeekRuntimeProvider:
    def __init__(self, settings:dict|None=None, *,
                 explicit_user_authorization:bool=False,
                 transport:Callable|None=None):
        self.settings=settings
        self.authorized=explicit_user_authorization
        self.transport=transport

    def infer(self, req:ContextRequest) -> ContextResponse:
        from .runtime import load_runtime_config
        settings=self.settings if self.settings is not None else load_runtime_config()["roles"]["deepseek"]
        if settings.get("enabled") is not True:
            raise RuntimeModelDisabled("RUNTIME_DEEPSEEK_DISABLED")
        validate_context_request(req)
        if settings.get("network_calls_allowed") is not True or not self.authorized:
            raise RuntimeModelUnauthorized("RUNTIME_NETWORK_NOT_AUTHORIZED")
        model=settings.get("model")
        if not isinstance(model,str) or not model:
            raise RuntimeModelNotConfigured("DEEPSEEK_MODEL_NOT_CONFIGURED")
        if settings.get("credential_env") != "DEEPSEEK_API_KEY":
            raise RuntimeModelNotConfigured("DEEPSEEK_API_KEY policy required")
        api_key=os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeModelNotConfigured("DEEPSEEK_API_KEY_MISSING")
        if self.transport is None:
            raise RuntimeModelUnauthorized("RUNTIME_TRANSPORT_NOT_IMPLEMENTED")
        payload={"model":model,
                 "decision_at":req.decision_at,
                 "feature_snapshot":req.feature_snapshot,
                 "output_schema":"context_tags_risk_flags_supporting_feature_ids_rationale_short_confidence"}
        raw=self.transport(payload=payload,credential=api_key)
        value=validate_context_response(raw,req.feature_snapshot.get("feature_ids",[]))
        return ContextResponse(
            "deepseek",model,tuple(value["context_tags"]),tuple(value["risk_flags"]),
            tuple(value["supporting_feature_ids"]),value["rationale_short"],
            float(value["confidence"]),_digest(payload),_digest(value),connected=False)
