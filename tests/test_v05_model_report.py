from datetime import date,timedelta
import numpy as np
import pandas as pd
import pytest
from logic_b.v05_model_report import _auc,evaluate_oos,fit_research_candidate
from logic_b.v05_research import FEATURES

def generate(n=180):
    sessions=[str(date(2025,1,1)+timedelta(days=i)) for i in range(n)]
    rows=[]
    for i in range(1,n-1):
        row={"trade_date":sessions[i],"outcome_date":sessions[i+1],"label":i%2}
        for j,col in enumerate(FEATURES):
            row[col]=float(i%9+j*.1)
        rows.append(row)
    return pd.DataFrame(rows),sessions

def test_auc_ranks_classes_and_ties_correctly():
    assert _auc(np.array([0,1]),np.array([.1,.9]))==1.0
    assert _auc(np.array([0,1]),np.array([.5,.5]))==.5
    assert _auc(np.array([1,1]),np.array([.3,.7])) is None

def test_purged_chronological_folds_never_learn_last_day_label():
    data,session=generate(180)
    result=evaluate_oos(data,session)
    assert result["ready"]
    good=[x for x in result["folds"] if x["ready"]]
    assert len(good)>=1
    for fold in good:
        assert fold["train_last_outcome_date"]<fold["start"]
        assert fold["n_validate"]>=10
        assert 0<=fold["brier"]<=1

def test_train_model_never_promotes_to_live_trade_permissions():
    data,session=generate(180)
    fit=fit_research_candidate(data,session)
    assert fit["trained"]
    assert not fit["model_promotable"]
    assert fit["trade_permissions"]=="NEVER"
    assert len(fit["features"])==len(FEATURES)

def test_blind_holdout_and_missing_samples_are_blocked():
    data,session=generate(8)
    assert not evaluate_oos(data,session)["ready"]
    with pytest.raises(ValueError,match="BLIND_HOLDOUT_LOCKED"):
        evaluate_oos(data,session+["2026-07-01"])
