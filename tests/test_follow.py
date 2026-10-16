import json
from pathlib import Path
from logic_b.follow import build_review

CFG=json.loads(Path("config/research.json").read_text(encoding="utf-8"))
DS=json.loads(Path("examples/toy_history.json").read_text(encoding="utf-8"))

def test_no_validated_strategy_results_in_no_follow():
    d={"days":[DS["days"][0]]}
    r=build_review(d,CFG)
    assert r["status"]=="NO_FOLLOW"
    assert r["orders_transmitted"]==0

def test_qualified_status_is_only_manual_review_not_order():
    d={"days":[DS["days"][0]]}
    r=build_review(d,CFG,{"verdict":"CANDIDATE_FOR_MANUAL_REVIEW"})
    assert r["status"]=="MANUAL_REVIEW_ONLY"
    assert r["candidate"]["symbol"]=="600001.SH"
    assert r["target_session"]=="NEXT_TRADING_SESSION_UNRESOLVED"
    assert r["orders_transmitted"]==0
    assert len(r["manual_checks"])>1
