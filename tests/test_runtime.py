import copy
from datetime import date
import pytest

from logic_b.runtime import RuntimeSnapshot, decide_runtime, load_runtime_config

RUNTIME = load_runtime_config()
STRATEGY = {"baseline":{"min_streak":1, "max_breaks":100, "min_market_temperature":None}}
EVENTS = {"date":"2020-01-08","limit_up":[
    {"symbol":"600001.SH","limit_up_days":2}]}
def snapshot(**changes):
    fields={"decision_at":"2020-01-09T09:35:00+08:00",
            "evidence_available_at":"2020-01-09T09:34:59+08:00",
            "evidence_quality":"VERIFIED_ASOF",
            "source_day":"2020-01-08","market_regime":"ATTACK",
            "previous_day_events":EVENTS,"core_confirmed_asof":True}
    fields.update(changes)
    return RuntimeSnapshot(**fields)

def test_offline_codex_is_not_online_dependency_and_models_are_disabled():
    assert RUNTIME["roles"]["codex"]["stage"]=="OFFLINE_RESEARCH_ONLY"
    assert RUNTIME["roles"]["codex"]["used_in_runtime"] is False
    assert RUNTIME["roles"]["deepseek"]["enabled"] is False
    assert RUNTIME["roles"]["jev_typesafe"]["enabled"] is False
    assert RUNTIME["external_provider_call_budget"]==0

def test_unapproved_version_is_no_follow():
    result=decide_runtime(snapshot(),research_strategy=STRATEGY,config=RUNTIME)
    assert (result["action"],result["review_status"])==("CASH","NO_FOLLOW")
    assert result["reason"]=="STRATEGY_NOT_PROMOTED"
    assert result["orders_transmitted"]==0 and result["model_calls_executed"]==0

def test_market_red_cannot_be_bypassed_by_provider_output():
    c=copy.deepcopy(RUNTIME)
    c["promotion"]["approved_strategy_sha"]="mock_test_approval_not_real_promotion"
    x=decide_runtime(snapshot(market_regime="ICE"),research_strategy=STRATEGY,
                     config=c, jev_advisory={"market_regime":"ATTACK","confidence":1},
                     deepseek_advisory={"message":"strong buy immediately"})
    assert x["action"]=="CASH"
    assert x["reason"]=="MARKET_RISK_VETO"
    assert x["advisory_can_override_risk_gate"] is False

def test_verified_and_mock_promoted_path_is_manual_review_only():
    c=copy.deepcopy(RUNTIME)
    c["promotion"]["approved_strategy_sha"]="offline_unit_test_only"
    r=decide_runtime(snapshot(),research_strategy=STRATEGY,config=c)
    assert r["action"]=="BUY_CORE"
    assert r["selected_core"]=="600001.SH"
    assert r["review_status"]=="MANUAL_REVIEW_ONLY"
    assert r["orders_transmitted"]==0

def test_missing_confirmation_and_late_evidence_fail_closed():
    c=copy.deepcopy(RUNTIME);c["promotion"]["approved_strategy_sha"]="test"
    r=decide_runtime(snapshot(core_confirmed_asof=False),research_strategy=STRATEGY,config=c)
    assert r["reason"]=="NO_LEGAL_0935_CORE_CONFIRMATION"
    with pytest.raises(ValueError,match="future evidence"):
        decide_runtime(snapshot(evidence_available_at="2020-01-09T09:35:01+08:00"),
                       research_strategy=STRATEGY,config=c)

def test_2026_protected_historical_window_and_runtime_distinguished():
    with pytest.raises(ValueError,match="outside authorized"):
        decide_runtime(snapshot(decision_at="2026-07-01T09:35:00+08:00",
           evidence_available_at="2026-06-30T15:05:00+08:00",
           source_day="2026-06-30"),research_strategy=STRATEGY,config=RUNTIME)
    with pytest.raises(ValueError,match="cannot masquerade"):
        decide_runtime(snapshot(historical_replay=False),research_strategy=STRATEGY,config=RUNTIME)
    # A truly forward date after protected period can be accepted into runtime
    # even though historical training dataset ends in June.
    r=decide_runtime(snapshot(historical_replay=False,
       decision_at="2027-01-04T09:35:00+08:00",
       evidence_available_at="2027-01-04T09:34:59+08:00",source_day="2026-12-31",
       previous_day_events={"date":"2026-12-31","limit_up":EVENTS["limit_up"]}),
       research_strategy=STRATEGY,config=RUNTIME)
    assert r["review_status"]=="NO_FOLLOW"

def test_exiting_holding_does_not_depend_on_ai_approval():
    r=decide_runtime(snapshot(held_symbol="600001.SH",prior_holding_exit_due=True),
                     research_strategy=STRATEGY,config=RUNTIME)
    assert r["action"]=="SELL"
    assert r["orders_transmitted"]==0

def test_unsafe_config_rejected():
    c=copy.deepcopy(RUNTIME)
    c["roles"]["codex"]["used_in_runtime"]=True
    with pytest.raises(ValueError,match="unsafe policy"):
        decide_runtime(snapshot(),research_strategy=STRATEGY,config=c)
    c=copy.deepcopy(RUNTIME);c["orders_transmitted"]=1
    with pytest.raises(ValueError,match="unsafe policy"):
        decide_runtime(snapshot(),research_strategy=STRATEGY,config=c)


def test_prior_day_vendor_event_label_must_match_source_date():
    with pytest.raises(ValueError,match="vendor prior-day events"):
        decide_runtime(snapshot(source_day="2020-01-07"),research_strategy=STRATEGY,config=RUNTIME)
