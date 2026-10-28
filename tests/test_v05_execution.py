from datetime import datetime,timedelta
import pandas as pd
from logic_b.v05_execution import audit_event_fills
from logic_b.models import FillModel

def bars(day,rows):
    base=pd.Timestamp(day+" 09:35:00")
    return pd.DataFrame([{"trade_time":base+pd.Timedelta(minutes=i),
      "open":a,"high":b,"low":c,"close":d,"vol":vol}
      for i,(a,b,c,d,vol) in enumerate(rows)])

def test_conservative_refuses_to_buy_a_sealed_limit():
    entry=bars("2025-01-06",[(11,11,11,11,100000)]*8)
    later=bars("2025-01-07",[(11,11.1,10.9,11,100000)]*8)
    r=audit_event_fills(code="600000.SH",signal_time=datetime(2025,1,6,9,35),
       entry_day_bars=entry,exit_day_bars=later,entry_day_preclose=10.,
       exit_day_preclose=11.,risk_warning=False,ipo_no_limit=False)
    assert not r["entry_filled"]
    assert r["net_return"] is None
    assert r["state"]=="ENTRY_UNFILLED"

def test_locked_limit_down_does_not_generate_fake_realized_profit():
    entry=bars("2025-01-06",[(10.4,10.6,10.2,10.5,100000)]*9)
    later=bars("2025-01-07",[(9.45,9.45,9.45,9.45,100000)]*9)
    r=audit_event_fills(code="600000.SH",signal_time=datetime(2025,1,6,9,35),
       entry_day_bars=entry,exit_day_bars=later,entry_day_preclose=10.,
       exit_day_preclose=10.5,risk_warning=False,ipo_no_limit=False)
    assert r["entry_filled"]
    assert not r["exit_filled"]
    assert r["state"]=="POSITION_OPEN"
    assert r["net_return"] is None

def test_full_lot_costs_are_deducted_from_conservative_open_close_proxy():
    entry=bars("2025-01-06",[(10.4,10.6,10.2,10.5,100000)]*9)
    later=bars("2025-01-07",[(10.8,10.9,10.7,10.8,100000)]*9)
    r=audit_event_fills(code="600000.SH",signal_time=datetime(2025,1,6,9,35),
       entry_day_bars=entry,exit_day_bars=later,entry_day_preclose=10.,
       exit_day_preclose=10.5,risk_warning=False,ipo_no_limit=False)
    assert r["entry_filled"] and r["exit_filled"]
    assert r["state"]=="CLOSED_PROXY"
    assert r["net_return"]<(r["exit_price"]/r["entry_price"]-1)
    assert r["shares"]%100==0
    assert r["fill_certified"] is False

def test_missing_historical_risk_status_prevents_fake_execution():
    entry=bars("2025-01-06",[(10.4,10.6,10.2,10.5,100000)]*9)
    r=audit_event_fills(code="600000.SH",signal_time=datetime(2025,1,6,9,35),
       entry_day_bars=entry,exit_day_bars=entry,
       entry_day_preclose=10.,exit_day_preclose=10.5,
       risk_warning=None,ipo_no_limit=False)
    assert r["state"]=="UNVERIFIED"
    assert r["net_return"] is None

def test_insufficient_minute_liquidity_cannot_fill_full_target_position():
    entry=bars("2025-01-06",[(10.4,10.6,10.2,10.5,100)]*9)
    later=bars("2025-01-07",[(10.8,10.9,10.7,10.8,100)]*9)
    r=audit_event_fills(code="600000.SH",signal_time=datetime(2025,1,6,9,35),
       entry_day_bars=entry,exit_day_bars=later,entry_day_preclose=10.,
       exit_day_preclose=10.5,risk_warning=False,ipo_no_limit=False)
    assert r["state"]=="VOLUME_CAPACITY_UNVERIFIED"
    assert r["net_return"] is None
