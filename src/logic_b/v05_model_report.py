"""Out-of-sample model diagnostics from already sanitized historical features.

No source network calls, no real broker orders and no claim of executable
returns. Production Radar is deliberately NOT a consumer of these weights.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .v05_research import FEATURES,fit_logistic,walkforward,BLIND_START

def _auc(y,prob):
    y=np.asarray(y).astype(int)
    if y.min()==y.max():return None
    positive=int(y.sum());negative=len(y)-positive
    rank=pd.Series(prob).rank(method="average").to_numpy()
    return round(float((rank[y==1].sum()-positive*(positive+1)/2)/(positive*negative)),6)

def evaluate_oos(events,calendar,min_train_days=120,validation_days=40,step_days=40):
    if events is None or events.empty:
        return {"ready":False,"reason":"NO_EVENTS","folds":[]}
    if not set(["trade_date","outcome_date","label",*FEATURES]).issubset(events.columns):
        raise ValueError("INCOMPLETE_FEATURE_FILE")
    sessions=sorted(set(str(day) for day in calendar))
    if any(day>=str(BLIND_START) for day in sessions):
        raise ValueError("BLIND_HOLDOUT_LOCKED")
    if len(sessions)<min_train_days+validation_days:
        return {"ready":False,"reason":"INSUFFICIENT_CALENDAR_SESSIONS",
            "sessions":len(sessions),"required":min_train_days+validation_days,"folds":[]}
    events=events.sort_values(["trade_date","outcome_date"]).copy()
    folds=[]
    for idx in range(min_train_days,len(sessions)-validation_days+1,step_days):
        first=sessions[idx];last=sessions[idx+validation_days-1]
        training=events[(events.trade_date<first)&(events.outcome_date<first)]
        validating=events[(events.trade_date>=first)&(events.trade_date<=last)]
        if len(training)<40 or len(validating)<10 or training.label.nunique()<2:
            folds.append({"start":first,"end":last,"ready":False,
               "reason":"INSUFFICIENT_EVENT_LABELS",
               "n_train":len(training),"n_validate":len(validating)})
            continue
        X=training[list(FEATURES)].to_numpy(float)
        y=training.label.to_numpy(float)
        weights,mu,sigma=fit_logistic(X,y)
        Z=validating[list(FEATURES)].to_numpy(float)
        actual=validating.label.to_numpy(float)
        pred=np.clip(1/(1+np.exp(-np.clip(
            np.c_[np.ones(len(Z)),(Z-mu)/sigma]@weights,-25,25))),1e-7,1-1e-7)
        baseline=float(np.mean(y))
        logloss=-float(np.mean(actual*np.log(pred)+(1-actual)*np.log(1-pred)))
        top=validating[["trade_date","label"]].copy()
        top["probability"]=pred
        top=top.sort_values(["trade_date","probability"],ascending=[True,False]).drop_duplicates("trade_date")
        # Temporal split purges any D+1 outcome at/after validation cutoff.
        assert training.outcome_date.max()<first
        folds.append({
          "ready":True,"start":first,"end":last,
          "train_last_outcome_date":str(training.outcome_date.max()),
          "n_train":int(len(training)),"n_validate":int(len(validating)),
          "auc":_auc(actual,pred),
          "brier":round(float(np.mean((pred-actual)**2)),6),
          "baseline_brier":round(float(np.mean((baseline-actual)**2)),6),
          "log_loss":round(logloss,6),
          "baseline_positive_rate_train":round(baseline,6),
          "validation_positive_rate":round(float(actual.mean()),6),
          "top1_daily_event_positive_rate":round(float(top.label.mean()),6),
          "top1_days":int(len(top)),
          "ranking_only":True
        })
    ready=[f for f in folds if f.get("ready")]
    return {
      "ready":bool(ready),
      "research_version":"v05-bar-proxy-logistic-l2",
      "fill_certified":False,
      "may_trade_live":False,
      "blind_holdout_used":False,
      "training_sessions_required":min_train_days,
      "validation_sessions_required":validation_days,
      "folds":folds,
      "n_valid_folds":len(ready),
      "mean_auc":round(float(np.mean([f["auc"] for f in ready if f["auc"] is not None])),6)
         if any(f["auc"] is not None for f in ready) else None,
      "mean_brier":round(float(np.mean([f["brier"] for f in ready])),6) if ready else None,
      "mean_baseline_brier":round(float(np.mean([f["baseline_brier"] for f in ready])),6) if ready else None,
      "all_models_research_only":True
    }

def fit_research_candidate(events,calendar,min_observations=60):
    """Research-only 2025 chronological refit; not Radar deployment weights."""
    if events is None or events.empty or len(events)<min_observations:
        return {"trained":False,"reason":"NOT_ENOUGH_EVENTS"}
    if not set(FEATURES).issubset(events.columns):raise ValueError("MISSING_FEATURE_COLUMNS")
    if events.label.nunique()<2:return {"trained":False,"reason":"SINGLE_CLASS"}
    sessions=sorted(set(str(day) for day in calendar))
    if any(day>=str(BLIND_START) for day in sessions):raise ValueError("BLIND_HOLDOUT_LOCKED")
    # All research labels must already be completed by the training cutoff.
    end=max(sessions)
    matured=events[events.outcome_date<=end].copy()
    if len(matured)<min_observations:
        return {"trained":False,"reason":"NOT_ENOUGH_MATURED_EVENTS"}
    values=matured[list(FEATURES)].to_numpy(float)
    weights,mu,std=fit_logistic(values,matured.label.to_numpy(float))
    digest=hashlib.sha256(np.concatenate([weights,mu,std]).astype("<f8").tobytes()).hexdigest()
    return {
      "trained":True,"state":"RESEARCH_ONLY_NOT_LIVE",
      "training_last_label_date":str(matured.outcome_date.max()),
      "n_training_events":len(matured),
      "features":list(FEATURES),
      "coefficients":[round(float(w),9) for w in weights],
      "train_feature_mean":[round(float(x),9) for x in mu],
      "train_feature_std":[round(float(x),9) for x in std],
      "sha256":digest,
      "algorithm":"l2-regularized-logistic",
      "blind_holdout_used":False,
      "human_whitelist_replayed":False,
      "model_promotable":False,
      "trade_permissions":"NEVER"
    }

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--features",required=True)
    parser.add_argument("--summary",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args(argv)
    features=pd.read_csv(args.features)
    summary=json.loads(Path(args.summary).read_text(encoding="utf8"))
    sessions=summary.get("market_sessions") or []
    if not sessions:raise ValueError("MISSING_CALENDAR")
    validation=evaluate_oos(features,sessions)
    model=fit_research_candidate(features,sessions)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/"oos-diagnostics.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf8")
    (out/"research-only-model.json").write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"validation":validation,"model":model},ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
