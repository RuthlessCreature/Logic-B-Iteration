"""Explicit optional LLM provider boundary. DeepSeek RESERVED and DISABLED.

The existing research_cli continues using its current explicit OpenAI path;
this module prepares a typed provider interface for future migration. There is
NO implicit fallback, automatic credential acquisition or background usage.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Protocol


class ProviderDisabled(RuntimeError):
    """Provider is disabled by the user's configuration."""


class ProviderNotConfigured(RuntimeError):
    """An explicitly chosen provider is missing model or credential."""


class ProviderNotActivated(RuntimeError):
    """Provider was reserved but live network access was not authorized."""


@dataclass(frozen=True)
class ProposalRequest:
    """Only a vetted TRAIN summary may be used; never unfiltered market rows."""
    train_summary: dict[str, Any]
    train_end: str = "2024-12-31"
    schema_version: str = "logic-b-proposal-v1"


@dataclass(frozen=True)
class ProposalResponse:
    provider: str
    model: str
    proposal: dict[str, Any]
    request_sha256: str
    response_sha256: str
    usage: dict[str, Any] | None = None
    connected: bool = False


class LLMProvider(Protocol):
    """A model can PROPOSE, not modify bar/fill/fee data or place orders."""
    def generate_proposal(self, request: ProposalRequest) -> ProposalResponse:
        ...


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                   allow_nan=False).encode("utf-8")).hexdigest()


def load_provider_config(path: str | Path = "config/llm_providers.json") -> dict[str, Any]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("primary") != "openai" or obj.get("provider_selection_policy") != "single_primary_no_silent_fallback":
        raise ValueError("unknown/default provider policy; never silently swap research models")
    for key in ("openai", "deepseek"):
        if key not in obj.get("providers", {}):
            raise ValueError(f"missing provider registry entry {key}")
    return obj


def validate_request(request: ProposalRequest) -> None:
    if request.train_end != "2024-12-31" or request.schema_version != "logic-b-proposal-v1":
        raise ValueError("unapproved experiment boundary")
    allowed = {"classification", "status", "initial_cash", "final_equity",
               "return_pct", "max_drawdown_pct", "training_end", "sessions",
               "closed_trades", "reason_counts"}
    if not request.train_summary or set(request.train_summary).difference(allowed):
        raise ValueError("LLM can only receive vetted training-period aggregated metrics")
    if request.train_summary.get("training_end") != "2024-12-31":
        raise ValueError("training_end verification failed")


class DeepSeekProvider:
    """Reserved DeepSeek Chat Completions API slot; no calls until explicit enablement.

    Enabling this requires BOTH a config flag and a separate explicit
    network-authorization argument. Credentials stay in DEEPSEEK_API_KEY.
    Live integration and actual models must be reviewed/activated separately.
    """
    def __init__(self, config: dict[str, Any] | None = None, *,
                 allow_external_calls: bool = False,
                 call: Callable | None = None):
        self.config = config if config is not None else load_provider_config()["providers"]["deepseek"]
        self.allow_external_calls = allow_external_calls
        self.call = call  # injected call is for OFFLINE tests only

    def generate_proposal(self, request: ProposalRequest) -> ProposalResponse:
        # Check enabled before parsing credentials, model IDs or constructing
        # any HTTP payload. Disabled means zero network requests.
        if self.config.get("enabled") is not True:
            raise ProviderDisabled("PROVIDER_DISABLED: DeepSeek reserved, disabled, not connected")
        validate_request(request)
        if not self.allow_external_calls:
            raise ProviderNotActivated("NETWORK_NOT_AUTHORIZED: no live DeepSeek calls")
        model = self.config.get("model")
        env = self.config.get("credential_env", "DEEPSEEK_API_KEY")
        if not isinstance(model, str) or not model.strip() or env != "DEEPSEEK_API_KEY":
            raise ProviderNotConfigured("MODEL_NOT_CONFIGURED: confirm live DeepSeek model before activation")
        secret = os.environ.get(env)
        if not secret:
            raise ProviderNotConfigured("DEEPSEEK_API_KEY missing; do not log or store key")
        # Deliberate activation boundary. The future protocol implementation
        # will need an explicit integration review and its own transport tests.
        # A test-injected mock can exercise the shared schema without network.
        if self.call is None:
            raise ProviderNotActivated("TRANSPORT_NOT_IMPLEMENTED: activate only with reviewed adapter")
        from .research import validate_proposal
        output = self.call(request.train_summary, model=model, api_key=secret)
        proposal = validate_proposal(output)
        return ProposalResponse(provider="deepseek", model=model, proposal=proposal,
                                request_sha256=_hash(request.train_summary),
                                response_sha256=_hash(proposal), connected=False)


class ExistingOpenAIProvider:
    """Adapter for current explicit OpenAI hypothesis route; not a second caller."""
    def __init__(self, model: str):
        self.model = model

    def generate_proposal(self, request: ProposalRequest) -> ProposalResponse:
        validate_request(request)
        from .research import ask_llm_for_hypothesis
        proposal = ask_llm_for_hypothesis(request.train_summary, model=self.model)
        return ProposalResponse(provider="openai", model=self.model, proposal=proposal,
                                request_sha256=_hash(request.train_summary),
                                response_sha256=_hash(proposal), connected=True)


def select_provider(name: str, *, model: str | None = None,
                    registry: dict[str, Any] | None = None,
                    allow_external_calls: bool = False) -> LLMProvider:
    """Explicit selection only. No automatic fallback or hidden paid calls."""
    data = registry if registry is not None else load_provider_config()
    providers = data["providers"]
    if name not in providers:
        raise ValueError("unknown provider: no fallback")
    if name == "deepseek":
        return DeepSeekProvider(providers[name], allow_external_calls=allow_external_calls)
    if name == "openai" and providers["openai"].get("enabled") is True and model:
        return ExistingOpenAIProvider(model)
    raise ProviderNotConfigured("Explicit OpenAI model and enabled registry are required")
