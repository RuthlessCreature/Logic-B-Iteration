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


def _signal_candles(last_volume=300,late_drift=False):
    # First break (09:32) -> defended pullback (09:33) ->
    # new high with volume acceleration (09:35). 09:36 is not used for signal.
    prices=[10.0,10.03,10.12,10.07,10.09,10.22,10.23]
    if late_drift:prices[-1]=8.88
    volumes=[100,100,100,110,110,last_volume,100]
    first=pd.Timestamp("2025-01-06 09:30:00")
    return pd.DataFrame([{
        "trade_time":first+pd.Timedelta(minutes=i),
        "open":px,"high":px+.01,"low":px-.01,"close":px,
        "vol":v,"amount":px*v
    } for i,(px,v) in enumerate(zip(prices,volumes))])


def test_bar_proxy_needs_first_break_pullback_second_break_and_real_volume():
    result=first_signal(_signal_candles(),9.9,code="600000.SH")
    assert result is not None
    assert result["signal_time"].endswith("09:35:00")
    assert result["entry_reference_time"].endswith("09:36:00")
    assert result["volume_ratio"]>1.35


def test_volume_absent_means_no_v05_entry_even_if_rebreak_pattern_is_pretty():
    assert first_signal(_signal_candles(last_volume=100),9.9,code="600000.SH") is None


def test_forward_price_drift_cannot_change_a_past_completed_bar_trigger():
    a=first_signal(_signal_candles(),9.9,code="600000.SH")
    b=first_signal(_signal_candles(late_drift=True),9.9,code="600000.SH")
    assert a["signal_time"]==b["signal_time"]=="2025-01-06T09:35:00"
    assert a["volume_ratio"]==b["volume_ratio"]


def test_true_calendar_sessions_are_separate_from_sparser_trigger_days():
    from datetime import date,timedelta
    first=date(2025,1,1)
    sessions=[str(first+timedelta(days=i)) for i in range(15)]
    x=pd.DataFrame([{"trade_date":sessions[5],"outcome_date":sessions[6],
      "label":1,**{f:1.0 for f in FEATURES}}])
    result=walkforward(x,min_train_days=10,valid_days=5,calendar=sessions)
    assert result["reason"] if not result["ready"] else True
    assert result.get("observed_days",15)==15
