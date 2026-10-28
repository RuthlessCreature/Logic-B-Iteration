"""Reproducible aggregation for v0.5 historical minute-bar proxy.

Only sanitized event features and aggregate data-quality summaries leave
the extraction job. Raw vendor historical minute candles stay in ephemeral
runner storage and are NEVER shipped as an artifact.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from .v05_research import FEATURES,walkforward

COLUMNS=["trade_date","outcome_date","label",*FEATURES]
DEV_END="2026-06-30"
BLIND_START="2026-07-01"

def sanitize_training_events(events:pd.DataFrame)->pd.DataFrame:
    """Export research features, labels and event dates, NO raw OHLCV or code."""
    if events is None or events.empty:
        return pd.DataFrame(columns=COLUMNS)
    missing=set(COLUMNS)-set(events.columns)
    if missing:
        raise ValueError("MISSING_EVENT_FIELDS:"+",".join(sorted(missing)))
    output=events[COLUMNS].copy()
    output["trade_date"]=output.trade_date.astype(str)
    output["outcome_date"]=output.outcome_date.astype(str)
    if output.trade_date.ge(BLIND_START).any() or output.outcome_date.gt(DEV_END).any():
        raise ValueError("BLIND_HOLDOUT_LOCKED")
    if (output.trade_date>=output.outcome_date).any():
        raise ValueError("LABEL_MUST_FOLLOW_SIGNAL_DATE")
    if not output.label.isin([0,1]).all():
        raise ValueError("CLASS_LABEL_INVALID")
    for col in FEATURES:
        output[col]=pd.to_numeric(output[col],errors="raise")
        if not output[col].map(lambda v:pd.notna(v) and abs(v)<1e10).all():
            raise ValueError("NONFINITE_FEATURE:"+col)
    return output.sort_values(["trade_date","outcome_date",*FEATURES]).reset_index(drop=True)

def merge_monthly_features(root:str|Path,expected_segments:int=3)->tuple[pd.DataFrame,dict]:
    root=Path(root)
    files=sorted(root.glob("**/public/features.csv"))
    if len(files)!=expected_segments:
        raise ValueError("MISSING_SEGMENTS:expected="+str(expected_segments)+" actual="+str(len(files)))
    observations=[]
    qualities=[]
    sessions=set()
    for path in files:
        shard=path.parent.parent
        qfile=shard/"quality.json"
        if not qfile.exists():
            raise ValueError("MISSING_SHARD_QUALITY:"+str(shard))
        quality=json.loads(qfile.read_text(encoding="utf-8"))
        if quality.get("missing_or_bad",0)>0:
            raise ValueError("SHARD_SOURCE_ERRORS:"+str(shard))
        if quality.get("candidate_stock_days",0)<=0:
            raise ValueError("EMPTY_CANDIDATE_SHARD:"+str(shard))
        calendar=quality.get("market_sessions")
        if not isinstance(calendar,list) or not calendar:
            raise ValueError("MISSING_DATED_SESSION_CALENDAR:"+str(shard))
        if any(str(day)>=BLIND_START or str(day)>DEV_END for day in calendar):
            raise ValueError("BLIND_HOLDOUT_LOCKED")
        sessions.update(str(day) for day in calendar)
        qualities.append(quality)
        data=pd.read_csv(path)
        observations.append(sanitize_training_events(data))
    combined=pd.concat(observations,ignore_index=True) if observations else pd.DataFrame(columns=COLUMNS)
    if not combined.empty:
        # Dedup only semantically identical event-features. A different event
        # on one date remains a separate row, even if it is the same symbol
        # (symbol deliberately absent from sanitized research export).
        combined=combined.drop_duplicates(subset=COLUMNS).sort_values(["trade_date","outcome_date"]).reset_index(drop=True)
    summary={
      "shards":len(files),"source":"independent-monthly-Xuangubao-1m-proxy",
      "candidate_stock_days":sum(int(q.get("candidate_stock_days",0)) for q in qualities),
      "usable_primary_minute_days":sum(int(q.get("usable_primary_minute_days",0)) for q in qualities),
      "missing_or_partial_primary_days":sum(int(q.get("missing_or_partial_primary_days",0)) for q in qualities),
      "signal_candidates":sum(int(q.get("historical_signal_candidates",0)) for q in qualities),
      "forward_minute_days":sum(int(q.get("usable_next_day_minutes",0)) for q in qualities),
      "missing_or_partial_forward_days":sum(int(q.get("missing_or_partial_next_day_minutes",0)) for q in qualities),
      "rows_after_dedup":len(combined),
      "unique_signal_days":int(combined.trade_date.nunique()) if not combined.empty else 0,
      "market_sessions":sorted(sessions),
      "market_session_count":len(sessions),
      "class_positive":int(combined.label.sum()) if not combined.empty else 0,
      "class_negative":int((combined.label==0).sum()) if not combined.empty else 0,
      "fill_certified":False,"market_0925_replayed":False,
      "human_whitelist_replayed":False,
      "train_validated":False,"strategy_return_validated":False
    }
    return combined,summary

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--expected-shards",type=int,default=3)
    a=p.parse_args(argv)
    data,summary=merge_monthly_features(a.input,expected_segments=a.expected_shards)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    if not data.empty:
        data.to_csv(out/"features.csv",index=False)
    # The 120+40-day study readiness remains frozen; no small-sample train
    # is passed off as validated research.
    outcome=walkforward(data,min_train_days=120,valid_days=40,calendar=summary['market_sessions'])
    summary["training_ready"]=bool(outcome.get("ready"))
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"training.json").write_text(json.dumps(outcome,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"coverage":summary,"training":outcome},ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
