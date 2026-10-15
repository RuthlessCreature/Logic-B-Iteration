import json
from pathlib import Path
import pytest

from logic_b.research import (validate_proposal, proposal_digest, training_summary,
                              compare_candidate, ask_llm_for_hypothesis)
from logic_b.replay import replay

CFG = json.loads(Path("config/research.json").read_text(encoding="utf-8"))
PROP = json.loads(Path("examples/proposal_example.json").read_text(encoding="utf-8"))

def synthetic():
    # One train and two validation trading dates; low coverage means NO_FOLLOW.
    d = json.loads(Path("examples/toy_history.json").read_text(encoding="utf-8"))
    later = [{**d["days"][0], "date": "2025-01-02"},
             {**d["days"][1], "date": "2025-01-03"},
             {**d["days"][2], "date": "2025-01-06"}]
    d["days"].extend(later)
    return d

def test_proposal_is_structured_and_versioned():
    assert validate_proposal(PROP) == PROP
    assert proposal_digest(PROP) == proposal_digest(json.loads(json.dumps(PROP)))
    bad = json.loads(json.dumps(PROP)); bad["params"]["initial_cash"] = 10_000_000
    with pytest.raises(ValueError):
        validate_proposal(bad)

def test_training_summary_excludes_validation():
    ds = synthetic()
    m = training_summary(ds, CFG)
    assert m["sessions"] == 3
    x = json.loads(json.dumps(ds))
    x["days"][-1]["daily"]["600001.SH"]["close"] = 100
    assert training_summary(x, CFG) == m

def test_credible_gate_fail_closed_in_incomplete_pilot():
    result = compare_candidate(synthetic(), CFG, PROP)
    assert result["verdict"] == "NO_FOLLOW"
    assert result["results"]["train"]["baseline"]["sessions"] == 3
    assert result["results"]["validation"]["proposal"]["sessions"] == 3

def test_research_proposals_cannot_change_fees_or_dates():
    wrong = json.loads(json.dumps(PROP)); wrong["params"]["minimum_commission"] = 0
    with pytest.raises(ValueError):
        compare_candidate(synthetic(), CFG, wrong)

def test_model_api_not_called_without_key():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY missing"):
        ask_llm_for_hypothesis({"return_pct": 0}, model="test", api_key=None,
                               opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network called")))
