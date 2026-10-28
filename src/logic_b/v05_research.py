"""Historical Logic A v0.5: 1-minute completed-bar PROXY, not live tick replay.

Features at bar close; forward outcome is next trading day's 09:35 bar price,
NOT a claim of executable P&L. Neither human whitelist nor 09:25 orderbook is
reconstructed. Blind holdout stays locked and model never goes to Radar.
"""
from __future__ import annotations
import argparse
import json
from datetime import date,timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from .features import build_prev_day_candidate_features
from .providers.xuangubao import XuangubaoEvidenceProvider
from .providers.xuangubao_market import XuangubaoMarketProvider

VERSION="logic-a-v05-1m-bar-proxy"
FEATURES=("prev_score","prev_height","break_pct","retrace_pct","volume_ratio","vwap_gap","clock_minute")
BLIND_START=date(2026,7,1)
BLIND_END=date(2026,9,28)

def first_signal(bars,preclose,code=''):
    if not preclose or preclose<=0 or bars is None or len(bars)<7:return None
    f=bars.copy()
    needed={"trade_time","open","close","vol","amount"}
    if not needed.issubset(f.columns):raise ValueError("MISSING_MINUTE_FIELDS")
    f["trade_time"]=pd.to_datetime(f.trade_time).dt.tz_localize(None)
    f=f.drop_duplicates("trade_time").sort_values("trade_time").reset_index(drop=True)
    for col in ["open","close","vol","amount"]:f[col]=pd.to_numeric(f[col],errors="coerce")
    if f[["open","close","vol","amount"]].isna().any().any():return None
    if (f[["open","close"]]<=0).any().any() or (f[["vol","amount"]]<0).any().any():return None
    vwap=f.amount.cumsum()/f.vol.cumsum().replace(0,np.nan)
    dayopen=float(f.open.iloc[0])
    for end in range(5,len(f)-1):
        time=f.trade_time.iloc[end]
        hm=time.strftime("%H:%M")
        if hm<"09:35" or hm>"14:55" or ("11:30"<hm<"13:00"):continue
        daypart=0 if hm<"12:00" else 1
        window=f.iloc[max(0,end-9):end+1]
        window=window[(window.trade_time.dt.hour>=12)==bool(daypart)]
        if len(window)<6 or (window.trade_time.iloc[-1]-window.trade_time.iloc[0]).total_seconds()<90:continue
        close=window.close.to_numpy(float);vol=window.vol.to_numpy(float)
        latest=close[-1]
        cap=17.0 if str(code).startswith(('30','68')) else 8.2
        if not 1.8<=(latest/preclose-1)*100<cap or latest<=dayopen or latest<=vwap.iloc[end]:continue
        for i in range(len(close)-3,1,-1):
            high=max(close[:i]);first=close[i]
            if not first>high*1.002 or first<close[0]*1.008:continue
            for j in range(len(close)-2,i,-1):
                retrace=(first-close[j])/first
                if not .0035<=retrace<=.018 or close[j]<high*.995 or close[j]<=dayopen:continue
                if close[j]<=vwap.iloc[window.index[j]]:continue
                if np.any(close[j:-1]<high*.995):continue
                if latest<=max(close[i:-1])*1.001:continue
                base=np.median(vol[:-1])
                if base<=0 or len(vol)<5 or vol[-1]<1.35*base:continue
                return {
                  "signal_time":time.isoformat(),"phase":"BAR_PROXY_ONLY",
                  "break_pct":(first/high-1)*100,"retrace_pct":retrace*100,
                  "volume_ratio":vol[-1]/base,"vwap_gap":(latest/vwap.iloc[end]-1)*100,
                  "clock_minute":int((time-f.trade_time.iloc[0]).total_seconds()/60),
                  # Signal at completed bar, reference first possible later bar only.
                  "entry_reference_price":float(f.open.iloc[end+1]),
                  "entry_reference_time":f.trade_time.iloc[end+1].isoformat()
                }
    return None

def build_proxy_events(sessions,evidence,minute,per_day=2,eval_start=None,eval_end=None):
    events=[];failures=[];candidates=0
    usable_primary=0;empty_primary=0;signal_candidates=0
    usable_forward=0;empty_forward=0
    dates=sorted(set(sessions))
    if any(BLIND_START<=d<=BLIND_END for d in dates):raise ValueError("BLIND_HOLDOUT_LOCKED")
    for n in range(1,len(dates)-1):
        prior,day,future=dates[n-1:n+2]
        if eval_start is not None and day<eval_start:continue
        if eval_end is not None and day>eval_end:continue
        try:
            prev=evidence.limit_list(prior,"涨停池")
            if prev.empty:continue
            # The pool request can silently yield another day's list on
            # holidays. Keep only stocks with real exchange event timestamps
            # matching D-1 in Shanghai local time (no point-in-time leakage).
            event_day=pd.to_datetime(pd.to_numeric(prev.get('last_limit_up'),errors='coerce'),
                                      unit='s',utc=True).dt.tz_convert('Asia/Shanghai').dt.date
            prev=prev[event_day==prior].copy()
            if prev.empty:continue
            prev=build_prev_day_candidate_features(prev)
            prev=prev.sort_values(["prev_core_score","ts_code"],ascending=[False,True]).head(per_day)
        except Exception as ex:
            failures.append({"date":str(day),"phase":"D-1","reason":str(ex)[:120]});continue
        for _,stock in prev.iterrows():
            candidates+=1;code=str(stock["ts_code"])
            try:
                # Source provides dated bars. Empty or truncated sessions are
                # audited as unavailable, not treated as a legitimate no-signal.
                bars=minute.historical_minute_day(code,day).bars
                if bars.empty or len(bars)<180:
                    empty_primary+=1
                    continue
                usable_primary+=1
                price=float(stock.get("price") or stock.get("prev_close") or 0)
                s=first_signal(bars,price,code=code)
                if not s:continue
                signal_candidates+=1
                # The D+1 query is deliberately performed only AFTER a D
                # signal has been recognized from D's closed minute bars.
                later=minute.historical_minute_day(code,future).bars
                if later.empty or len(later)<180:
                    empty_forward+=1
                    continue
                usable_forward+=1
                futurebars=later.copy()
                futurebars["trade_time"]=pd.to_datetime(futurebars.trade_time)
                futurebars=futurebars[futurebars.trade_time.dt.strftime("%H:%M")>="09:35"]
                if futurebars.empty:continue
                exitproxy=float(futurebars.iloc[0]["close"])
                if s["entry_reference_price"]<=0 or exitproxy<=0:continue
                events.append({
                  "trade_date":str(day),"outcome_date":str(future),"code":code,
                  "prior_day":str(prior),"label":int(exitproxy>s["entry_reference_price"]),
                  "target_t1_proxy_return":exitproxy/s["entry_reference_price"]-1,
                  "prev_score":float(stock.get("prev_core_score") or 0),
                  "prev_height":float(stock.get("f_height") or 0),
                  **s
                })
            except Exception as ex:
                failures.append({"date":str(day),"code":code,"phase":"minute","reason":str(ex)[:120]})
    return pd.DataFrame(events),{
      "candidate_stock_days":candidates,"usable_primary_minute_days":usable_primary,
      "missing_or_partial_primary_days":empty_primary,
      "historical_signal_candidates":signal_candidates,
      "usable_next_day_minutes":usable_forward,
      "missing_or_partial_next_day_minutes":empty_forward,
      "labelled_events":len(events),
      "missing_or_bad":len(failures),"examples":failures[:5],
      "source":"dated-XGB-limit-pool + historical-1m-bars",
      "label":"T+1_09:35_REFERENCE_PRICE_NOT_FILL",
      "market_0925_replayed":False,"human_whitelist_replayed":False,
      "fill_certified":False,"strategy_return_calculated":False}

def fit_logistic(X,y,iterations=500):
    mu=X.mean(0);sd=X.std(0);sd=np.where(sd<1e-8,1.,sd)
    A=np.c_[np.ones(len(X)),(X-mu)/sd];w=np.zeros(A.shape[1])
    for _ in range(iterations):
        p=1/(1+np.exp(-np.clip(A@w,-20,20)))
        grad=A.T@(p-y)/len(y);grad[1:]+=.01*w[1:]
        w-=.1*grad
    return w,mu,sd

def walkforward(events,min_train_days=120,valid_days=40,step_days=40,calendar=None):
    if events is None or events.empty:return {"ready":False,"reason":"NO_EVENTS","folds":[]}
    rows=events.sort_values("trade_date").copy()
    if any(BLIND_START<=date.fromisoformat(str(x))<=BLIND_END for x in rows.trade_date):
        raise ValueError("BLIND_HOLDOUT_LOCKED")
    if not set(FEATURES).issubset(rows.columns) or "label" not in rows:
        raise ValueError("MISSING_FEATURES_OR_LABEL")
    # Calendar spans ALL observed market sessions, even CASH/no-signal days.
    # Counting only event dates would silently convert 120 trading sessions
    # into 120 unusually active signal days and misalign the benchmark.
    days=sorted(set(str(d) for d in calendar)) if calendar is not None else sorted(rows.trade_date.unique())
    if any(BLIND_START<=date.fromisoformat(str(d))<=BLIND_END for d in days):
        raise ValueError("BLIND_HOLDOUT_LOCKED")
    if days and (rows.trade_date.lt(days[0]).any() or rows.trade_date.gt(days[-1]).any()):
        raise ValueError("EVENT_OUTSIDE_RESEARCH_CALENDAR")
    if len(days)<min_train_days+valid_days:
        return {"ready":False,"reason":"INSUFFICIENT_TRADING_DAYS","observed_days":len(days),
          "required_days":min_train_days+valid_days,"folds":[]}
    folds=[]
    for idx in range(min_train_days,len(days)-valid_days+1,step_days):
        start=days[idx];last=days[idx+valid_days-1]
        train=rows[(rows.trade_date<start)&(rows.outcome_date<start)]
        valid=rows[(rows.trade_date>=start)&(rows.trade_date<=last)]
        train=train.dropna(subset=list(FEATURES)+["label"])
        valid=valid.dropna(subset=list(FEATURES)+["label"])
        if len(train)<40 or len(valid)<10 or train.label.nunique()<2:
            folds.append({"start":start,"ready":False,"reason":"INSUFFICIENT_LABELS"});continue
        w,mu,sd=fit_logistic(train[list(FEATURES)].to_numpy(float),train.label.to_numpy(float))
        X=valid[list(FEATURES)].to_numpy(float)
        p=1/(1+np.exp(-np.clip(np.c_[np.ones(len(X)),(X-mu)/sd]@w,-20,20)))
        y=valid.label.to_numpy(float);pred=(p>=.5)
        folds.append({"start":start,"end":last,"ready":True,"training":len(train),"validation":len(valid),
          "brier":round(float(np.mean((p-y)**2)),6),
          "base_rate":round(float(y.mean()),6),
          "accuracy":round(float(np.mean(pred==y)),6),
          "precision_on_positive_predictions":round(float(y[pred].mean()),6) if pred.any() else None})
    return {"ready":any(f["ready"] for f in folds),"folds":folds,
      "blind_holdout_used":False,"fill_certified":False,
      "promotable_to_radar":False,"model_version":"v05-bar-proxy-logistic-l2"}

def run_pilot(start,end,per_day=2):
    if end>=BLIND_START:raise ValueError("DEVELOPMENT_ONLY")
    evidence=XuangubaoEvidenceProvider(timeout=12,max_attempts=2)
    minute=XuangubaoMarketProvider(timeout=12,max_attempts=2)
    dates=[];d=start-timedelta(days=8)
    while d<=end:
        if d.weekday()<5:
            try:
                line=evidence.market_indicator_line(d,["limit_up_count"])
                if not line.empty:dates.append(d)
            except Exception:pass
        d+=timedelta(days=1)
    if len(dates)<3:raise RuntimeError("HISTORICAL_DATE_SOURCE_NOT_READY")
    events,quality=build_proxy_events(dates,evidence,minute,per_day,eval_start=start,eval_end=end)
    # This list is safe metadata for shard aggregation: exchange-local
    # market dates only, no vendor minute bars or symbol identifiers.
    quality["market_sessions"]=[str(d) for d in dates if start<=d<=end]
    quality["market_session_count"]=len(quality["market_sessions"])
    quality["requested_start"]=str(start)
    quality["requested_end"]=str(end)
    return events,quality

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--start",default="2025-01-06")
    ap.add_argument("--end",default="2025-01-15")
    ap.add_argument("--per-day",type=int,default=2)
    ap.add_argument("--out",default="runs/v05-pilot")
    ap.add_argument("--events",default=None)
    ap.add_argument("--min-train-days",type=int,default=120)
    ap.add_argument("--valid-days",type=int,default=40)
    a=ap.parse_args(argv)
    folder=Path(a.out);folder.mkdir(parents=True,exist_ok=True)
    if a.events:
        events=pd.read_parquet(a.events) if a.events.endswith(".parquet") else pd.read_csv(a.events)
        quality={"source":"private-labelled-event-file","labelled_events":len(events)}
    else:
        events,quality=run_pilot(date.fromisoformat(a.start),date.fromisoformat(a.end),a.per_day)
        if not events.empty:events.to_parquet(folder/"private-labels.parquet",index=False)
    report=walkforward(events,min_train_days=a.min_train_days,valid_days=a.valid_days,
       calendar=quality.get("market_sessions"))
    (folder/"quality.json").write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding="utf8")
    (folder/"training.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"quality":quality,"training":report},ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())
