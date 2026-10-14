from datetime import datetime
import pandas as pd
import pytest
from logic_b.execution import simulate_buy_fill, simulate_sell_fill
from logic_b.models import FillModel

def bars(prices):
    base=pd.Timestamp("2026-09-28 09:35:00")
    return pd.DataFrame([{"trade_time":base+pd.Timedelta(minutes=i),"open":o,"high":h,"low":l,"close":c,"vol":v} for i,(o,h,l,c,v) in enumerate(prices)])

def test_realistic_buy_rejects_sealed_limit():
    f=simulate_buy_fill(ts_code="X",signal_time=datetime(2026,9,28,9,35),minute_bars=bars([(11,11,11,11,1000)]*4),limit_up_price=11,model=FillModel.REALISTIC)
    assert not f.filled

def test_conservative_buy_requires_two_open_minutes():
    f=simulate_buy_fill(ts_code="X",signal_time=datetime(2026,9,28,9,35),minute_bars=bars([(11,11,11,11,1000),(10.9,11,10.8,10.95,5000),(10.95,11,10.85,10.9,6000)]),limit_up_price=11,model=FillModel.CONSERVATIVE)
    assert f.filled
    assert f.fill_time==pd.Timestamp("2026-09-28 09:37:00")

def test_realistic_sell_rejects_locked_down():
    f=simulate_sell_fill(ts_code="X",signal_time=datetime(2026,9,28,9,35),minute_bars=bars([(9,9,9,9,2000)]*3),limit_down_price=9,model=FillModel.REALISTIC)
    assert not f.filled

def test_zero_volume_and_checkpoint_only_bars_fail_closed_without_fill():
    signal=datetime(2026,9,28,9,35)
    checkpoint=pd.DataFrame([{"trade_time":"2026-09-28 09:35:00","open":10,"high":10.2,"low":9.9,"close":10,"vol":100}])
    zero_volume=bars([(10,10.2,9.9,10,0)])
    for frame in (checkpoint,zero_volume):
        fill=simulate_buy_fill(ts_code="X",signal_time=signal,minute_bars=frame,limit_up_price=11,model=FillModel.REALISTIC)
        assert not fill.filled
        assert fill.fill_time is None

@pytest.mark.parametrize("mutation", ["nan_price", "zero_price", "bad_ohlc", "negative_volume", "bad_time", "duplicate_time", "out_of_order"])
def test_invalid_minute_bars_raise_before_any_fill(mutation):
    frame=bars([(10,10.2,9.9,10,100),(10,10.2,9.9,10,100)])
    if mutation=="nan_price": frame.loc[0,"open"]=float("nan")
    if mutation=="zero_price": frame.loc[0,"close"]=0
    if mutation=="bad_ohlc": frame.loc[0,"high"]=9
    if mutation=="negative_volume": frame.loc[0,"vol"]=-1
    if mutation=="bad_time": frame["trade_time"]=frame["trade_time"].astype(object); frame.loc[0,"trade_time"]="not-a-time"
    if mutation=="duplicate_time": frame.loc[1,"trade_time"]=frame.loc[0,"trade_time"]
    if mutation=="out_of_order": frame=frame.iloc[::-1].reset_index(drop=True)
    with pytest.raises(ValueError):
        simulate_buy_fill(ts_code="X",signal_time=datetime(2026,9,28,9,35),minute_bars=frame,limit_up_price=11,model=FillModel.REALISTIC)
