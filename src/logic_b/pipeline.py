"""Demand-driven Xuangubao/BaoStock collector: only fetch candidate and held bars."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from .collect import BaoStockClient,fetch_calendar,fetch_xgb_day,fetch_daily,fetch_5m,_atomic_json,_check_dates
from .fees import compute_fees
from .replay import _tradeable
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
    suspended=0
    unknown_trade_status=0
    request_types=Counter()
    outcome_reasons=Counter()
    cash=float(config["initial_cash"])
    held=None
    shares=0
    bought_on=None
    commission=float(config["commission_rate"])
    minimum=float(config["minimum_commission"])
    lot_size=int(config["lot_size"])
    for i,day in enumerate(calendar):
        # Maintain the account's one-position state in one pass. The prior
        # implementation replayed the whole prefix for each day (O(N^2)).
        # This planner mirrors replay's sell-before-buy, T+1, fees and no-fallback
        # constraints only to decide which bars must be fetched.
        prior=snapshots[i-1] if i else None
        start_held=held
        core,core_reason=select_core(events[i-1],config.get("baseline",{})) if i else (None,"WARMUP")
        symbol=start_held or core
        vendor=events[i]
        row={k:vendor.get(k) for k in ("date","limit_up","limit_down","limit_broken","market")}
        row["daily"]={s:v["records"][day] for s,v in dailies.items() if day in v.get("records",{})}
        row["bars_5m"]={}
        if symbol:
            request_types["EXIT_HELD_POSITION" if start_held else "ENTRY_CORE"]+=1
            daily_record=row["daily"].get(symbol)
            if daily_record is None:
                missing_daily+=1
            elif daily_record.get("tradestatus") in (0,"0",False):
                suspended+=1
                request_types["SUSPENDED_NO_MINUTE_REQUIRED"]+=1
            elif daily_record.get("tradestatus") not in (1,"1",True):
                unknown_trade_status+=1
                request_types["TRADE_STATUS_UNKNOWN_NO_MINUTE_REQUIRED"]+=1
            else:
                requested+=1
                try:
                    data=minute_loader(symbol,day)
                    bars=data.get("bars",[]) if isinstance(data,dict) else data
                except Exception:
                    bars=[]
                if bars:
                    row["bars_5m"][symbol]=bars
                    cached+=1
                else:
                    outcome_reasons["MISSING_MINUTE_PARTITION"]+=1
        snapshots.append(row)
        sell_attempted=False
        if start_held and bought_on != day:
            sell_attempted=True
            sell_price,sell_reason,_=_tradeable(row,prior,start_held,config.get("execution_time","09:45"),"SELL") if prior else (None,"MISSING_DAILY",None)
            if sell_price is not None:
                gross=round(shares*sell_price,6)
                cost=compute_fees(gross,"SELL",day,rate=commission,minimum=minimum)
                cash=round(cash+gross-cost.total,6)
                held,shares,bought_on=None,0,None
            else:
                outcome_reasons[sell_reason]+=1
        if held is None and not sell_attempted and core is not None and prior is not None:
            buy_price,buy_reason,_=_tradeable(row,prior,core,config.get("execution_time","09:45"),"BUY")
            if buy_price is None:
                outcome_reasons[buy_reason]+=1
            else:
                lots=int(cash//(buy_price*lot_size))
                while lots:
                    qty=lots*lot_size
                    gross=round(qty*buy_price,6)
                    cost=compute_fees(gross,"BUY",day,rate=commission,minimum=minimum)
                    if gross+cost.total<=cash+1e-7:
                        break
                    lots-=1
                if lots:
                    held,shares,bought_on=core,qty,day
                    cash=round(cash-gross-cost.total,6)
                else:
                    outcome_reasons["INSUFFICIENT_CASH_FOR_100_SHARES"]+=1
        elif held is None and not sell_attempted and core is None and i:
            outcome_reasons[core_reason]+=1
    missing_bar=requested-cached
    event_sources_complete=all(
        isinstance(e.get("limit_up"),list) and isinstance(e.get("limit_down"),list)
        and isinstance(e.get("limit_broken"),list) and isinstance(e.get("provenance"),dict)
        and e.get("provenance",{}).get("provider")=="xuangubao"
        for e in events)
    coverage_complete=(event_sources_complete and missing_daily==0 and missing_bar==0
                       and unknown_trade_status==0)
    return {"days":snapshots,"coverage_complete":coverage_complete,
            "classification":"HISTORICAL_DATA_PARTIAL_NOT_BROKER_FILLS"},{
        "event_days":len(calendar),"source_codes":len(dailies),
        "minute_requested":requested,"minute_with_bars":cached,
        "missing_daily_target_days":missing_daily,
        "missing_minute_target_days":missing_bar,
        "suspended_target_days":suspended,
        "unknown_trade_status_target_days":unknown_trade_status,
        "event_source_complete":event_sources_complete,
        "coverage_complete":coverage_complete,
        "request_types":dict(request_types),
        "planning_outcome_reasons":dict(outcome_reasons)}

def run_pilot(start,end,max_sessions,cache,config):
    _check_dates(start,end)
    if max_sessions<2:
        raise ValueError("need at least two sessions")
    with BaoStockClient() as bs:
        calendar_cache=fetch_calendar(start,end,cache,bs)
        calendar=calendar_cache["days"][:max_sessions]
        if len(calendar)<2:
            raise ValueError("insufficient historical sessions")
        events=[]
        event_failures=[]
        event_reused=0
        event_downloaded=0
        event_reused_bytes=0
        event_downloaded_bytes=0
        for day in calendar:
            event_path=cache/"events"/(day+".json")
            was_cached=event_path.is_file()
            try:
                event=fetch_xgb_day(day,cache)
                event_reused+=int(was_cached)
                event_downloaded+=int(not was_cached)
                if was_cached:
                    event_reused_bytes+=event_path.stat().st_size
                else:
                    event_downloaded_bytes+=event_path.stat().st_size
            except Exception as exc:
                event_failures.append({"day":day,"error_type":type(exc).__name__,"error":str(exc)[:500]})
                event={"date":day,"limit_up":None,"limit_down":None,"limit_broken":None,
                       "market":None,"source_status":"MISSING"}
            events.append(event)
            time.sleep(.1)
        print(f"event partitions complete={len(calendar)-len(event_failures)}/{len(calendar)} failures={len(event_failures)}")
        candidates={s for i in range(1,len(events))
                    if isinstance(events[i-1].get("limit_up"),list)
                    and (s:=select_core(events[i-1],config.get("baseline",{}))[0])}
        daily={}
        daily_failures=[]
        daily_cache_reused_bytes=0
        daily_downloaded_bytes=0
        daily_reused_months=0
        daily_downloaded_months=0
        for symbol in sorted(candidates):
            try:
                daily[symbol]=fetch_daily(symbol,cache,bs,start=start,end=end)
                daily_cache_reused_bytes+=daily[symbol]["cache_reused_bytes"]
                daily_downloaded_bytes+=daily[symbol]["downloaded_bytes"]
                daily_reused_months+=daily[symbol]["cache_reused_months"]
                daily_downloaded_months+=daily[symbol]["downloaded_months"]
            except Exception as exc:
                daily_failures.append({"symbol":symbol,"error_type":type(exc).__name__,"error":str(exc)[:500]})
        minute_stats={"cache_reused_files":0,"downloaded_files":0,
                      "cache_reused_bytes":0,"downloaded_bytes":0}
        def minute_loader(symbol, day):
            path=cache/"minute"/symbol/(day+".json")
            cached_before=path.is_file()
            result=fetch_5m(symbol,day,cache,bs)
            byte_count=result.get("source_file_bytes",path.stat().st_size)
            key="cache_reused" if cached_before else "downloaded"
            minute_stats[key+"_files"]+=1
            minute_stats[key+"_bytes"]+=byte_count
            return result
        dataset,coverage=prepare_demand_driven(
            calendar,events,daily,minute_loader,config)
        coverage["event_failures"]=event_failures
        coverage["daily_failures"]=daily_failures
        coverage["calendar_cache"]={k:calendar_cache[k] for k in
            ("cache_reused_months","downloaded_months","cache_reused_bytes","downloaded_bytes")}
        coverage["events_cache"]={"reused_files":event_reused,"downloaded_files":event_downloaded,
            "reused_bytes":event_reused_bytes,"downloaded_bytes":event_downloaded_bytes}
        coverage["daily_cache"]={"reused_months":daily_reused_months,
            "downloaded_months":daily_downloaded_months,"reused_bytes":daily_cache_reused_bytes,
            "downloaded_bytes":daily_downloaded_bytes}
        coverage["minute_cache"]=minute_stats
        coverage["baostock_retries"]=bs.query_retry_count
        coverage["baostock_queries"]=bs.query_count
        coverage["baostock_api_failures"]=len(bs.query_failures)
    result=replay(dataset,config)
    # Fingerprints bind market inputs and frozen account assumptions to every
    # result without distributing price rows in public GitHub artifacts.
    stable_days=[{k:day.get(k) for k in ("date","limit_up","limit_down",
                     "limit_broken","market","daily","bars_5m")}
                 for day in dataset["days"]]
    digest=lambda value:hashlib.sha256(json.dumps(
        value,ensure_ascii=False,sort_keys=True,allow_nan=False,
        separators=(",",":")).encode("utf-8")).hexdigest()
    input_sha256=digest(stable_days)
    config_sha256=digest(config)
    audit={"classification":"REAL_PRICE_PARTIAL_SIMULATION_NOT_EXECUTABLE_RETURN",
           "period":[calendar[0],calendar[-1]],"coverage":coverage,
           "input_sha256":input_sha256,"config_sha256":config_sha256,
           "yearly_account_table":result["yearly"],
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
    p.add_argument("--start",default="2025-01-01")
    p.add_argument("--end",default="2025-01-31")
    p.add_argument("--max-sessions",type=int,default=20)
    p.add_argument("--cache",type=Path,default=Path("data/raw"))
    p.add_argument("--out",type=Path,default=Path("runs/smart-pilot"))
    p.add_argument("--config",type=Path,default=Path("config/goal_2025_2026.json"))
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
