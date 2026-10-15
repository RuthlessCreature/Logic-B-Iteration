"""Demand-driven Xuangubao/BaoStock collector: only fetch candidate and held bars."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import time
from .collect import BaoStockClient,fetch_xgb_day,fetch_daily,fetch_5m,_atomic_json,_check_dates
from .strategy import select_core
from .replay import replay

def prepare_demand_driven(calendar,events,dailies,minute_loader,config):
    if calendar != sorted(set(calendar)) or len(calendar)!=len(events):
        raise ValueError("calendar/events mismatch")
    if calendar:
        _check_dates(calendar[0],calendar[-1])
    if any(e.get("date")!=d for e,d in zip(events,calendar)):
        raise ValueError("vendor event date mismatch")
    snapshots=[]
    requested=0
    cached=0
    missing_daily=0
    reasons=Counter()
    for i,day in enumerate(calendar):
        # Prior completed sessions only; no D session pool in D signal.
        prior_result=replay({"days":snapshots},config) if snapshots else None
        held=prior_result["daily_equity"][-1]["symbol"] if prior_result else None
        core,_=select_core(events[i-1],config.get("baseline",{})) if i else (None,"WARMUP")
        symbol=held or core
        vendor=events[i]
        row={k:vendor.get(k) for k in ("date","limit_up","limit_down","limit_broken","market")}
        row["daily"]={s:v["records"][day] for s,v in dailies.items() if day in v.get("records",{})}
        row["bars_5m"]={}
        if symbol:
            requested+=1
            reasons["EXIT_HELD_POSITION" if held else "ENTRY_CORE"]+=1
            if symbol not in row["daily"]:
                missing_daily+=1
            else:
                data=minute_loader(symbol,day)
                bars=data.get("bars",[]) if isinstance(data,dict) else data
                if bars:
                    row["bars_5m"][symbol]=bars
                    cached+=1
        snapshots.append(row)
    missing_bar=requested-missing_daily-cached
    return {"days":snapshots,"coverage_complete":False,
            "classification":"HISTORICAL_DATA_PARTIAL_NOT_BROKER_FILLS"},{
        "event_days":len(calendar),"source_codes":len(dailies),
        "minute_requested":requested,"minute_with_bars":cached,
        "missing_daily_target_days":missing_daily,
        "missing_minute_target_days":missing_bar,
        "request_types":dict(reasons)}

def run_pilot(start,end,max_sessions,cache,config):
    _check_dates(start,end)
    if max_sessions<2:
        raise ValueError("need at least two sessions")
    with BaoStockClient() as bs:
        calendar=bs.trade_calendar(start,end)[:max_sessions]
        if len(calendar)<2:
            raise ValueError("insufficient historical sessions")
        events=[]
        for day in calendar:
            events.append(fetch_xgb_day(day,cache))
            time.sleep(.1)
        candidates={s for i in range(1,len(events))
                    if (s:=select_core(events[i-1],config.get("baseline",{}))[0])}
        daily={symbol:fetch_daily(symbol,cache,bs,start=start,end=end)
               for symbol in sorted(candidates)}
        dataset,coverage=prepare_demand_driven(
            calendar,events,daily,lambda sym,d:fetch_5m(sym,d,cache,bs),config)
    result=replay(dataset,config)
    audit={"classification":"REAL_PRICE_PARTIAL_SIMULATION_NOT_EXECUTABLE_RETURN",
           "period":[calendar[0],calendar[-1]],"coverage":coverage,
           "account":{"initial_cash":result["initial_cash"],
                      "final_equity":result["final_equity"],
                      "return_pct":result["return_pct"],
                      "max_drawdown_pct":result["max_drawdown_pct"],
                      "closed_trades":len(result["closed_trades"]),
                      "fills_buy":sum(x["side"]=="BUY" for x in result["fills"]),
                      "fills_sell":sum(x["side"]=="SELL" for x in result["fills"]),
                      "held_at_end":bool(result["daily_equity"][-1]["symbol"]),
                      "corporate_action_flags":len(result["account_unresolved_corporate_actions"]),
                      "unreliable_marks":sum(x["mark_stale"] or x["corporate_action_unreconciled"]
                                            for x in result["daily_equity"]),
                      "order_reasons":dict(Counter(x["reason"] for x in result["orders"]))},
           "warnings":["Only v0 historical baseline-selected securities loaded.",
                       "Source prices are genuine, executions are simulated at a completed 5m bar.",
                       "Incomplete period, corporate actions and 09:35 signal availability not fully verified."]}
    return dataset,result,audit

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2020-01-01")
    p.add_argument("--end",default="2020-03-31")
    p.add_argument("--max-sessions",type=int,default=40)
    p.add_argument("--cache",type=Path,default=Path("data/raw"))
    p.add_argument("--out",type=Path,default=Path("runs/smart-pilot"))
    p.add_argument("--config",type=Path,default=Path("config/research.json"))
    args=p.parse_args()
    cfg=json.loads(args.config.read_text(encoding="utf-8"))
    ds,r,a=run_pilot(args.start,args.end,args.max_sessions,args.cache,cfg)
    args.out.mkdir(parents=True,exist_ok=True)
    # These detailed files stay inside ignored runner storage, never artifact-uploaded.
    _atomic_json(args.out/"private_replay_input.json",ds)
    _atomic_json(args.out/"private_trade_ledger.json",r)
    _atomic_json(args.out/"aggregate.json",a)
    print(json.dumps(a,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
