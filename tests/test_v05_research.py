from datetime import date,timedelta
import pandas as pd
import pytest
from logic_b.v05_research import first_signal,walkforward,FEATURES

def fixture():
    prices=[10,10.04,10.13,10.07,10.1,10.16,10.2,10.21]
    volumes=[100,100,100,110,120,250,110,100]
    first=pd.Timestamp("2025-01-06 09:31:00")
    return pd.DataFrame([{"trade_time":first+pd.Timedelta(minutes=i),
      "open":price,"close":price,"vol":vol,"amount":price*vol} for i,(price,vol) in enumerate(zip(prices,volumes))])

def test_historical_bar_signal_only_uses_next_completed_minute_for_entry():
    out=first_signal(fixture(),9.8)
    assert out is None or out["entry_reference_time"]>out["signal_time"]

def test_ml_training_refuses_small_samples():
    row={"trade_date":"2025-01-03","outcome_date":"2025-01-06","label":1}
    row.update({f:1. for f in FEATURES})
    x=walkforward(pd.DataFrame([row]))
    assert x["ready"] is False
    assert x["reason"]=="INSUFFICIENT_TRADING_DAYS"

def test_ml_training_cannot_touch_locked_2026_holdout():
    row={"trade_date":"2026-07-02","outcome_date":"2026-07-03","label":1}
    row.update({f:1. for f in FEATURES})
    with pytest.raises(ValueError,match="BLIND_HOLDOUT_LOCKED"):
        walkforward(pd.DataFrame([row]))
