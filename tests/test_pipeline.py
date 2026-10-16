"""No future event access and only holding/candidate minute requests."""
import json
from pathlib import Path
import pytest

from logic_b.pipeline import prepare_demand_driven
from logic_b.replay import replay

CFG=json.loads(Path("config/research.json").read_text(encoding="utf-8"))

def events(day,candidate=False):
    return {"date":day,"limit_up":[{"symbol":"600001.SH","limit_up_days":1}] if candidate else [],
            "limit_down":[],"limit_broken":[],"market":{}}

def record(price):
    return {"close":price,"is_st":False,"preclose":None,"tradestatus":1}

def test_only_needed_three_bars_for_locked_exit():
    calendar=["2020-01-02","2020-01-03","2020-01-06","2020-01-07"]
    raw=[events(d,i==0) for i,d in enumerate(calendar)]
    daily={"600001.SH":{"records":dict(zip(calendar,map(record,[10,10,9,9.3])))}}
    called=[]
    def get(sym,day):
        called.append((sym,day))
        px={"2020-01-03":10,"2020-01-06":9,"2020-01-07":9.3}[day]
        return {"bars":[{"time":"09:45","open":px,"high":px,"low":px,"close":px,"volume":12000}]}
    ds,coverage=prepare_demand_driven(calendar,raw,daily,get,CFG)
    assert [day for _,day in called]==calendar[1:]
    assert coverage["minute_requested"]==3
    assert coverage["request_types"]=={"ENTRY_CORE":1,"EXIT_HELD_POSITION":2}
    x=replay(ds,CFG)
    assert [q["side"] for q in x["fills"]]==["BUY","SELL"]
    assert [q["reason"] for q in x["orders"]]==[
        "SIMULATED_BAR_CLOSE_FILL","NO_FILL_LIMIT_DOWN","SIMULATED_BAR_CLOSE_FILL"
    ]

def test_protected_date_rejected_before_any_minute_requests():
    called=[]
    with pytest.raises(ValueError,match="only 2020"):
        prepare_demand_driven(
            ["2026-06-30","2026-07-01"],
            [events("2026-06-30"),events("2026-07-01")],
            {},lambda *_:called.append(1),CFG)
    assert not called

def test_missing_daily_fails_closed():
    days=["2020-01-02","2020-01-03"]
    ds,cov=prepare_demand_driven(
        days,[events(days[0],True),events(days[1])],
        {},lambda *_:pytest.fail("minute called with missing daily"),CFG)
    assert cov["missing_daily_target_days"]==1
    assert replay(ds,CFG)["orders"][0]["reason"]=="MISSING_DAILY"

def test_missing_minute_fails_closed():
    days=["2020-01-02","2020-01-03"]
    ds,cov=prepare_demand_driven(days,
        [events(days[0],True),events(days[1])],
        {"600001.SH":{"records":{d:record(10) for d in days}}},
        lambda *_:{"bars":[]},CFG)
    assert cov["missing_minute_target_days"]==1
    assert replay(ds,CFG)["orders"][0]["reason"]=="MISSING_5M_BARS"

def test_suspended_symbol_does_not_create_a_missing_minute_failure():
    days=["2020-01-02","2020-01-03"]
    daily={"600001.SH":{"records":{days[0]:record(10),days[1]:dict(record(10),tradestatus=0)}}}
    def no_minute(*_):
        pytest.fail("a suspended security must not request minute bars")
    ds,cov=prepare_demand_driven(days,[events(days[0],True),events(days[1])],daily,no_minute,CFG)
    assert cov["suspended_target_days"]==1
    assert cov["minute_requested"]==0
    assert cov["missing_minute_target_days"]==0
    assert replay(ds,CFG)["orders"][0]["reason"]=="SUSPENDED"

def test_unavailable_previous_event_source_fails_closed_without_crashing():
    days=["2020-01-02","2020-01-03"]
    missing={"date":days[0],"limit_up":None,"limit_down":None,"limit_broken":None,
             "market":None,"source_status":"MISSING"}
    ds,cov=prepare_demand_driven(days,[missing,events(days[1])],{},
                                 lambda *_:pytest.fail("missing source must not produce a candidate"),CFG)
    assert cov["event_source_complete"] is False
    assert cov["coverage_complete"] is False
    assert replay(ds,CFG)["orders"][0]["reason"]=="SOURCE_UNAVAILABLE"

def test_target_planning_tracks_portfolio_in_one_pass(monkeypatch):
    import logic_b.pipeline as pipeline
    days=["2020-01-02","2020-01-03"]
    daily={"600001.SH":{"records":dict(zip(days,[record(10),record(10)]))}}
    def forbidden_replay(*_args,**_kwargs):
        pytest.fail("target planning must not replay every historical prefix")
    monkeypatch.setattr(pipeline,"replay",forbidden_replay)
    dataset,coverage=pipeline.prepare_demand_driven(
        days,[events(days[0],True),events(days[1])],daily,
        lambda *_:{"bars":[{"time":"09:45","open":10,"high":10,"low":10,
                             "close":10,"volume":1000}]},CFG)
    assert coverage["minute_requested"]==1
    assert dataset["days"][1]["date"]==days[1]
