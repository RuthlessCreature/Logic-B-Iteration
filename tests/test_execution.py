from datetime import datetime
import pandas as pd
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
