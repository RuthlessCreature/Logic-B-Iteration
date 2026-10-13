import numpy as np
import pandas as pd
import pytest

from logic_b.h01_activity import H01DataBlocked
from logic_b.h01_sensitivity import analyze, paired_block_interval


def make_samples(n=168):
    days=pd.bdate_range("2023-01-02",periods=n)
    x=pd.DataFrame({
        "trade_date":days.strftime("%Y-%m-%d"),
        "cohort_id":"VENDOR_PRIOR_LIMITUP_MARKET_PROXY",
        "asof_at":[f"{d:%Y-%m-%d}T09:35:00+08:00" for d in days],
        "label_observed_at":[f"{d:%Y-%m-%d}T16:00:00+08:00" for d in days],
        "evaluation_ready":True,
        "repeat_rate":0.2+0.04*np.cos(np.arange(n)*0.3),
        "prior_repeat_rate":0.2+0.04*np.cos((np.arange(n)-1)*0.3),
        "prior_day_limitup_count":70+np.arange(n)%20,
        "h01_experience_proxy":np.cos((np.arange(n)-2)*0.25),
    })
    audit=pd.DataFrame({
        "trade_date":days.strftime("%Y%m%d"),"status":"MATCH"
    })
    return x,audit


def test_one_anomaly_quarantined_including_3_following_days():
    x,a=make_samples()
    a.loc[10,"status"]="SOURCE_DEFINITION_REVIEW"
    r,p,y,q=analyze(x,a)
    assert r["status"]=="EXPLORATORY_NOT_VALIDATED"
    assert list(q.index[q["count_audit_quarantine"]])==[10,11,12,13]
    assert len(p)>40
    assert r["holdout_2026_07_01_to_09_28_used"] is False
    assert r["equity_backtest_performed"] is False


def test_quality_threshold_breach_blocks_promotion_even_if_forecast_runs():
    x,a=make_samples()
    a.loc[[10,20,30,40],"status"]="SOURCE_DEFINITION_REVIEW"
    r,_,_,_=analyze(x,a)
    assert r["status"]=="BLOCKED_PROMOTION_SOURCE_COUNT_MISMATCH"
    assert r["source_mismatch_fraction"]>0.02


def test_protected_holdout_not_allowed():
    x,a=make_samples()
    x.loc[len(x)-1,"trade_date"]="2026-07-01"
    with pytest.raises(H01DataBlocked,match="holdout"):
        analyze(x,a)


def test_seeded_block_interval_is_finite():
    vals=np.array([.01,-.02,.03,.02,-.01]*6)
    assert paired_block_interval(vals,5,draws=100)==paired_block_interval(vals,5,draws=100)
