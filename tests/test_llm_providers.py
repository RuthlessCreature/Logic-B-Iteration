import json
from pathlib import Path

import pytest

from logic_b.llm_providers import (
    DeepSeekProvider, ProposalRequest, ProviderDisabled, ProviderNotActivated,
    ProviderNotConfigured, select_provider, load_provider_config, validate_request,
)

registry = load_provider_config()
sample = ProposalRequest({
    "training_end":"2024-12-31", "classification":"BAR_CLOSE_SIMULATION_NOT_REAL_FILL",
    "sessions":100,"initial_cash":10000,
})


def test_default_provider_openai_deepseek_disabled():
    assert registry["primary"] == "openai"
    assert registry["providers"]["deepseek"]["enabled"] is False
    assert registry["providers"]["deepseek"]["allow_external_calls"] is False
    assert registry["providers"]["deepseek"]["model"] is None


def test_default_deepseek_does_not_read_key_or_make_any_network_call(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    provider = DeepSeekProvider(call=lambda *_args, **_kwargs:
                                pytest.fail("disabled provider unexpectedly called"))
    with pytest.raises(ProviderDisabled, match="PROVIDER_DISABLED"):
        provider.generate_proposal(sample)


def test_explicit_selection_never_falls_back_to_other_provider():
    with pytest.raises(ValueError, match="unknown provider"):
        select_provider("unknown", model="anything")
    with pytest.raises(ProviderDisabled):
        select_provider("deepseek").generate_proposal(sample)


def test_opt_in_network_switch_alone_still_cannot_call_provider():
    cfg = {"enabled": True, "model": "future-model-id",
           "credential_env": "DEEPSEEK_API_KEY"}
    with pytest.raises(ProviderNotActivated, match="NETWORK_NOT_AUTHORIZED"):
        DeepSeekProvider(cfg).generate_proposal(sample)
    with pytest.raises(ProviderNotConfigured, match="DEEPSEEK_API_KEY"):
        DeepSeekProvider(cfg,allow_external_calls=True).generate_proposal(sample)


def test_unreviewed_transport_not_wired_even_with_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY","dummy-for-unit-test")
    cfg = {"enabled":True,"model":"future-model-id",
           "credential_env":"DEEPSEEK_API_KEY"}
    with pytest.raises(ProviderNotActivated,match="TRANSPORT_NOT_IMPLEMENTED"):
        DeepSeekProvider(cfg,allow_external_calls=True).generate_proposal(sample)


def test_proposal_request_fail_closed_without_train_boundary():
    with pytest.raises(ValueError,match="training_end"):
        validate_request(ProposalRequest({"training_end":"2026-06-30"}))
    with pytest.raises(ValueError,match="vetted"):
        validate_request(ProposalRequest({"training_end":"2024-12-31","future_2026_returns":[5,1,2]}))


def test_mock_normalizes_proposal_with_provider_provenance(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY","dummy")
    proposal=json.loads(Path("examples/proposal_example.json").read_text())
    config={"enabled":True,"model":"future-model-id","credential_env":"DEEPSEEK_API_KEY"}
    q=DeepSeekProvider(config,allow_external_calls=True,
                       call=lambda summary,**kw:proposal).generate_proposal(sample)
    assert q.proposal == proposal
    assert q.provider == "deepseek"
    assert q.connected is False
    assert len(q.response_sha256) == 64
    assert len(q.request_sha256) == 64
