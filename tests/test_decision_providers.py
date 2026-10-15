"""No external model calls, broker operations, or paid traffic from reserved Jev."""
import copy

import pytest

from logic_b.decision_providers import (
    DecisionRequest, TypeSafeJevProvider, DecisionProviderDisabled,
    DecisionProviderNotAuthorized, DecisionProviderNotConfigured,
    build_jev_questions, get_decision_provider, load_decision_registry,
    validate_decision_request,
)

REG = load_decision_registry()
STATE = {"trade_date":"2020-01-09","evidence_asof":"2020-01-08T15:00:00+08:00",
         "source_quality":"VERIFIED_ASOF","limit_up_count":43,
         "limit_down_count":12,"negative_feedback_count":8}
REQ = DecisionRequest("2020-01-09T09:35:00+08:00", STATE)

def test_default_is_disabled_and_not_primary():
    assert REG["active_provider"] == "deterministic"
    cfg = REG["providers"]["jev_typesafe"]
    assert cfg["enabled"] is False
    assert cfg["model"] is None
    assert cfg["allow_external_calls"] is False
    assert cfg["endpoint"] == "https://api.typesafe.ai/v1/systemone"
    assert cfg["credential_env"] == "TYPESAFE_API_KEY"

def test_disabled_provider_never_calls_network(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY","dummy")
    spy = lambda **kw: pytest.fail("external Jev transport called while disabled")
    with pytest.raises(DecisionProviderDisabled,match="PROVIDER_DISABLED"):
        TypeSafeJevProvider(transport=spy,allow_external_calls=True).evaluate(REQ)
    with pytest.raises(DecisionProviderDisabled):
        get_decision_provider().evaluate(REQ)

def test_nonapproved_time_or_future_market_data_fails():
    with pytest.raises(ValueError,match="beyond authorized"):
        validate_decision_request(DecisionRequest("2026-07-01T09:35:00+08:00",
            dict(STATE,trade_date="2026-07-01")))
    with pytest.raises(ValueError,match="after decision"):
        validate_decision_request(DecisionRequest("2020-01-09T09:35:00+08:00",
            dict(STATE,evidence_asof="2020-01-09T15:00:00+08:00")))
    with pytest.raises(ValueError,match="unvetted"):
        validate_decision_request(DecisionRequest("2020-01-09T09:35:00+08:00",
            dict(STATE,future_pnl=100)))
    with pytest.raises(ValueError,match="unverified"):
        validate_decision_request(DecisionRequest("2020-01-09T09:35:00+08:00",
            dict(STATE,source_quality="EOD_UNVERIFIED")))

def test_network_requires_two_switches():
    cfg = copy.deepcopy(REG["providers"]["jev_typesafe"])
    cfg.update(enabled=True,model="jev-latest")
    with pytest.raises(DecisionProviderNotAuthorized,match="NETWORK_NOT_AUTHORIZED"):
        TypeSafeJevProvider(cfg,allow_external_calls=True).evaluate(REQ)
    cfg["allow_external_calls"] = True
    with pytest.raises(DecisionProviderNotAuthorized,match="NETWORK_NOT_AUTHORIZED"):
        TypeSafeJevProvider(cfg,allow_external_calls=False).evaluate(REQ)

def test_no_secret_or_model_no_activation(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY",raising=False)
    cfg = copy.deepcopy(REG["providers"]["jev_typesafe"])
    cfg.update(enabled=True,allow_external_calls=True)
    with pytest.raises(DecisionProviderNotConfigured,match="verified TypeSafe model"):
        TypeSafeJevProvider(cfg,allow_external_calls=True).evaluate(REQ)
    cfg["model"] = "jev-latest"
    with pytest.raises(DecisionProviderNotConfigured,match="TYPESAFE_API_KEY missing"):
        TypeSafeJevProvider(cfg,allow_external_calls=True).evaluate(REQ)

def test_without_transport_still_does_not_call_api(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY","mock-dummy")
    cfg = copy.deepcopy(REG["providers"]["jev_typesafe"])
    cfg.update(enabled=True,model="jev-latest",allow_external_calls=True)
    with pytest.raises(DecisionProviderNotAuthorized,match="TRANSPORT_NOT_IMPLEMENTED"):
        TypeSafeJevProvider(cfg,allow_external_calls=True).evaluate(REQ)

def test_offline_mock_typed_market_regime_decision(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY","mock-dummy")
    cfg = copy.deepcopy(REG["providers"]["jev_typesafe"])
    cfg.update(enabled=True,model="jev-latest",allow_external_calls=True)
    def fake(*,payload,api_key,endpoint):
        assert payload["questions"]["market_regime"]["type"]=="choice"
        assert api_key=="mock-dummy"
        assert endpoint=="https://api.typesafe.ai/v1/systemone"
        distribution={name: 0.05 for name in ("ATTACK","TRIAL","NEUTRAL","RETREAT","ICE")}
        distribution["RETREAT"]=0.8
        return {"model":"jev-latest","answers":{"market_regime":{
            "type":"choice","choice":"RETREAT","confidence":0.8,
            "probabilities":distribution}},"usage":{"input_tokens":100,"output_tokens":8}}
    r=TypeSafeJevProvider(cfg,allow_external_calls=True,transport=fake).evaluate(REQ)
    assert r.provider=="jev_typesafe"
    assert r.connected is False
    assert r.authority=="ADVISORY_ONLY_NO_ORDER_NO_MARKET_GATE_OVERRIDE"
    assert len(r.request_sha256)==len(r.response_sha256)==64
    assert r.answers["market_regime"]["choice"]=="RETREAT"

def test_typed_question_shapes_match_official_contract():
    assert build_jev_questions("advisory_market_regime")["market_regime"]["type"]=="choice"
    assert build_jev_questions("advisory_tail_risk_score")["tail_risk"]["type"]=="score"
    assert build_jev_questions("advisory_negative_feedback")["negative_feedback"]["type"]=="noul"

def test_jev_has_separate_forward_live_domain_after_protected_window():
    from logic_b.decision_providers import DecisionRequest, validate_decision_request
    new_state=dict(STATE, trade_date="2027-01-04",
                   evidence_asof="2027-01-04T09:34:59+08:00")
    validate_decision_request(DecisionRequest(
        "2027-01-04T09:35:00+08:00",new_state,scope="forward_live"))
    with pytest.raises(ValueError,match="authorized 2020-2026"):
        validate_decision_request(DecisionRequest(
            "2027-01-04T09:35:00+08:00",new_state))
    protected=dict(STATE,trade_date="2026-07-01",
                   evidence_asof="2026-07-01T09:34:59+08:00")
    with pytest.raises(ValueError,match="cannot replay protected"):
        validate_decision_request(DecisionRequest(
            "2026-07-01T09:35:00+08:00",protected,scope="forward_live"))
