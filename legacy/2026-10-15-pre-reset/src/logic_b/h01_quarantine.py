"""Audit-hardened postprocess for long H01-A forecasting.

Quarantine a market-count disagreement at D and D+1..D+3 (D+1
continuation label, three-session historical-experience window). This
is predefined, not optimized from predictor errors. Does not prove
psychological causality or after-cost trade returns.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from .h01_activity import expanding_window_h01, H01DataBlocked

MAX_MISMATCH_RATE=0.02
MAX_QUARANTINE_RATE=0.10

def quarantine_count_days(joined: pd.DataFrame, audited_counts: pd.DataFrame,
                          after: int=3) -> pd.DataFrame:
    if after < 1: raise ValueError("after must be >=1")
    x=joined.sort_values("trade_date").reset_index(drop=True).copy()
    audit=audited_counts.copy()
    if audit.empty or "trade_date" not in audit or "status" not in audit:
        raise H01DataBlocked("count audit is empty or missing status")
    audit["trade_date"]=pd.to_datetime(audit["trade_date"]).dt.strftime("%Y-%m-%d")
    if x.trade_date.duplicated().any() or audit.trade_date.duplicated().any():
        raise H01DataBlocked("duplicate observation date")
    if set(x.trade_date)!=set(audit.trade_date):
        raise H01DataBlocked("audited count days not identical to study days")
    mismatch=set(audit.loc[audit.status!="MATCH","trade_date"])
    q=set()
    for i,d in enumerate(x.trade_date):
        if d in mismatch:
            q.update(range(i,min(len(x),i+after+1)))
    x["count_audit_quarantine"]=[i in q for i in range(len(x))]
    x["evaluation_ready"]=x["evaluation_ready"].astype(bool) & ~x["count_audit_quarantine"]
    return x

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--joined",required=True)
    p.add_argument("--audit",required=True)
    p.add_argument("--out",required=True)
    ns=p.parse_args(argv)
    root=Path(ns.out)
    root.mkdir(parents=True,exist_ok=True)
    report={"status":"BLOCKED","scope":"H01-A prediction only; no P&L or actual investor IDs"}
    try:
        join=pd.read_parquet(ns.joined)
        audit=pd.read_csv(ns.audit,dtype={"trade_date":str})
        if not len(audit): raise H01DataBlocked("zero count-audited days")
        mismatches=int((audit.status!="MATCH").sum())
        x=quarantine_count_days(join,audit)
        q=int(x.count_audit_quarantine.sum())
        report.update({"dates":len(x),"vendor_mismatch_days":mismatches,
                       "quarantined_days":q,
                       "vendor_mismatch_fraction":mismatches/len(x),
                       "quarantined_fraction":q/len(x),
                       "excluded_rule":"mismatch date plus following 3 exchange sessions",
                       "max_mismatch_fraction":MAX_MISMATCH_RATE,
                       "max_quarantine_fraction":MAX_QUARANTINE_RATE})
        x.to_parquet(root/"joined_quarantined.parquet",index=False)
        if (mismatches/len(x)>MAX_MISMATCH_RATE or q/len(x)>MAX_QUARANTINE_RATE):
            raise H01DataBlocked("count mismatch or quarantine exceeds frozen research threshold")
        result,pred=expanding_window_h01(x,min_train_days=120,min_test_days=40)
        report["prediction"]=result
        report["status"]=result["status"]
        pred.to_parquet(root/"predictions_quarantined.parquet",index=False)
        (root/"audit_and_prediction.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 2 if result["status"].startswith("BLOCKED") else 0
    except (ValueError,KeyError,H01DataBlocked) as exc:
        report["reason"]=str(exc)
        (root/"audit_and_prediction.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
