"""DeepSeek is an optional daily runtime model, NEVER the Codex train-only API."""
import copy
import pytest
from logic_b.runtime import load_runtime_config
from logic_b.runtime_deepseek import (ContextRequest, DeepSeekRuntimeProvider,
    RuntimeModelDisabled,RuntimeModelUnauthorized,RuntimeModelNotConfigured,
    validate_context_request,validate_context_response)

CFG=load_runtime_config()
REQ=ContextRequest(
    decision_at="2020-01-09T09:35:00+08:00",
    evidence_available_at="2020-01-09T09:34:59+08:00",
    trade_date="2020-01-09",
    feature_snapshot={"source_quality":"VERIFIED_ASOF",
                      "market_regime":"RETREAT",
                      "negative_feedback_count":7,
                      "feature_ids":["NEGATIVE_FEEDBACK_COUNT_D_MINUS_1"]},
)

def test_default_is_disabled_with_no_transport_or_cost():
    assert CFG["roles"]["deepseek"]["stage"]=="RUNTIME_CONTEXT_INFERENCE"
    assert CFG["roles"]["deepseek"]["enabled"] is False
    with pytest.raises(RuntimeModelDisabled,match="DISABLED"):
        DeepSeekRuntimeProvider(transport=lambda **kwargs: pytest.fail("network called")).infer(REQ)

def test_research_future_and_protected_boundaries_differ():
    with pytest.raises(ValueError,match="historical request"):
        validate_context_request(ContextRequest(
            "2026-07-01T09:35:00+08:00","2026-06-30T15:00:00+08:00",
            "2026-07-01",REQ.feature_snapshot))
    validate_context_request(ContextRequest(
        "2027-01-04T09:35:00+08:00","2027-01-04T09:34:59+08:00",
        "2027-01-04",REQ.feature_snapshot,scope="forward_live"))

def test_no_future_evidence_or_unverified_data():
    with pytest.raises(ValueError,match="future evidence"):
        validate_context_request(ContextRequest(REQ.decision_at,
             "2020-01-09T15:00:00+08:00",REQ.trade_date,REQ.feature_snapshot))
    with pytest.raises(ValueError,match="unapproved/private"):
        validate_context_request(ContextRequest(REQ.decision_at,
             REQ.evidence_available_at,REQ.trade_date,
             dict(REQ.feature_snapshot,account_cash=10000)))

def test_credentials_and_transport_require_explicit_separate_authorization(monkeypatch):
    s=copy.deepcopy(CFG["roles"]["deepseek"])
    s.update(enabled=True,model="future-runtime-model")
    with pytest.raises(RuntimeModelUnauthorized,match="NOT_AUTHORIZED"):
        DeepSeekRuntimeProvider(s,explicit_user_authorization=True).infer(REQ)
    s["network_calls_allowed"]=True
    with pytest.raises(RuntimeModelUnauthorized):
        DeepSeekRuntimeProvider(s).infer(REQ)
    with pytest.raises(RuntimeModelNotConfigured,match="API_KEY_MISSING"):
        DeepSeekRuntimeProvider(s,explicit_user_authorization=True).infer(REQ)
    monkeypatch.setenv("DEEPSEEK_API_KEY","test-secret")
    with pytest.raises(RuntimeModelUnauthorized,match="TRANSPORT_NOT_IMPLEMENTED"):
        DeepSeekRuntimeProvider(s,explicit_user_authorization=True).infer(REQ)

def test_mock_can_return_structured_audited_context_only(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY","dummy")
    s=copy.deepcopy(CFG["roles"]["deepseek"])
    s.update(enabled=True,network_calls_allowed=True,model="future-runtime-model")
    def offline_mock(**kwargs):
        assert kwargs["payload"]["feature_snapshot"]["negative_feedback_count"]==7
        assert kwargs["credential"]=="dummy"
        return {"context_tags":["MARKET_STRESS"],"risk_flags":["NEGATIVE_FEEDBACK"],
                "supporting_feature_ids":["NEGATIVE_FEEDBACK_COUNT_D_MINUS_1"],
                "rationale_short":"Prior-session failure count elevated",
                "confidence":0.76}
    r=DeepSeekRuntimeProvider(s,explicit_user_authorization=True,
        transport=offline_mock).infer(REQ)
    assert r.provider=="deepseek" and not r.connected
    assert len(r.input_sha256)==64 and len(r.output_sha256)==64
    assert r.authority=="ADVISORY_ONLY_NO_HARD_GATE_OVERRIDE"

def test_hallucinated_evidence_id_is_rejected():
    with pytest.raises(ValueError,match="invented evidence"):
        validate_context_response({"context_tags":[],"risk_flags":[],
          "supporting_feature_ids":["FUTURE_STOCK_PROFIT"],
          "rationale_short":"", "confidence":.5},REQ.feature_snapshot["feature_ids"])
