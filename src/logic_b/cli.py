from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path

import pandas as pd
import yaml

from .features import classify_market_regime
from .ingest import HistoricalIngestor
from .models import FillModel
from .providers.tushare import TushareProvider
from .replay.runner import B0ReplayRunner
from .reporting import write_run_artifacts
from .storage import LocalParquetStore


def _date(v: str) -> date:
    return datetime.strptime(v, "%Y-%m-%d").date()


def _config(path: str) -> dict:
    cfg=yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required=["version","universe","portfolio","execution","research"]
    missing=[k for k in required if k not in cfg]
    if missing:
        raise SystemExit(f"missing config keys: {missing}")
    return cfg


def _calendar_dates(store: LocalParquetStore, start: date, end: date) -> list[str]:
    key=f"{start:%Y%m%d}_{end:%Y%m%d}"
    cal=store.read_frame("calendar",key)
    col="cal_date" if "cal_date" in cal.columns else "trade_date"
    dates=sorted(pd.to_datetime(cal[col]).dt.strftime("%Y%m%d").tolist())
    return [d for d in dates if f"{start:%Y%m%d}"<=d<=f"{end:%Y%m%d}"]


def cmd_smoke(_: argparse.Namespace) -> int:
    r=classify_market_regime(
        limit_up_count=72,limit_down_count=4,break_rate=.16,
        max_height=7,prev_limit_median_return=.021,
    )
    print(json.dumps({"status":"ok","example_regime":r.value},ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    cfg=_config(args.path)
    print(json.dumps({"status":"ok","version":cfg["version"]},ensure_ascii=False))
    return 0


def cmd_fetch_daily(args: argparse.Namespace) -> int:
    start=_date(args.start); end=_date(args.end)
    store=LocalParquetStore(args.data_root)
    ing=HistoricalIngestor(TushareProvider(),store)
    dates=ing.fetch_range(start,end,force=args.force)
    print(json.dumps({"status":"ok","days":len(dates),"first":dates[0] if dates else None,"last":dates[-1] if dates else None},ensure_ascii=False))
    return 0


def cmd_fetch_minutes(args: argparse.Namespace) -> int:
    start=_date(args.start); end=_date(args.end)
    store=LocalParquetStore(args.data_root)
    ing=HistoricalIngestor(TushareProvider(),store)
    dates=_calendar_dates(store,start,end)
    total=0
    for i in range(1,len(dates)):
        day=pd.to_datetime(dates[i]).date()
        prev=pd.to_datetime(dates[i-1]).date()
        total+=len(ing.fetch_prev_limit_candidates_minutes(day,prev,force=args.force))
    print(json.dumps({"status":"ok","trade_days":len(dates),"minute_symbol_days":total},ensure_ascii=False))
    return 0


def cmd_run_b0(args: argparse.Namespace) -> int:
    cfg=_config(args.config)
    start=_date(args.start); end=_date(args.end)
    store=LocalParquetStore(args.data_root)
    dates=_calendar_dates(store,start,end)

    selected=[FillModel(args.fill)] if args.fill!="all" else [
        FillModel.OPTIMISTIC,FillModel.REALISTIC,FillModel.CONSERVATIVE
    ]
    outputs=[]
    for model in selected:
        runner=B0ReplayRunner(
            store,
            fill_model=model,
            initial_cash=float(cfg["portfolio"].get("initial_cash",1_000_000)),
            fee_rate=float(cfg["execution"].get("commission_rate",0.0003)),
            stamp_rate=float(cfg["execution"].get("stamp_rate",0.0005)),
            checkpoint=datetime.strptime(cfg["execution"].get("decision_checkpoint","09:35"),"%H:%M").time(),
        )
        result=runner.run(dates)
        run_dir=Path(args.run_root)/f'{cfg["version"]}_{start:%Y%m%d}_{end:%Y%m%d}_{model.value}'
        write_run_artifacts(
            run_dir=run_dir,
            signals=result.signals,
            fills=result.fills,
            trades=result.trades,
            daily_equity=result.daily_equity,
            metrics=result.metrics,
            config=cfg,
            metadata={"start":args.start,"end":args.end,"fill_model":model.value},
        )
        outputs.append({"fill_model":model.value,"run_dir":str(run_dir),"metrics":result.metrics})
    print(json.dumps({"status":"ok","runs":outputs},ensure_ascii=False,default=str,indent=2))
    return 0


def main() -> int:
    parser=argparse.ArgumentParser(prog="logic-b")
    sub=parser.add_subparsers(dest="cmd",required=True)

    p=sub.add_parser("smoke"); p.set_defaults(func=cmd_smoke)
    p=sub.add_parser("validate-config"); p.add_argument("path"); p.set_defaults(func=cmd_validate)

    for name,func in [("fetch-daily",cmd_fetch_daily),("fetch-minutes",cmd_fetch_minutes)]:
        p=sub.add_parser(name)
        p.add_argument("--start",required=True)
        p.add_argument("--end",required=True)
        p.add_argument("--data-root",default="data")
        p.add_argument("--force",action="store_true")
        p.set_defaults(func=func)

    p=sub.add_parser("run-b0")
    p.add_argument("--start",required=True)
    p.add_argument("--end",required=True)
    p.add_argument("--data-root",default="data")
    p.add_argument("--run-root",default="runs")
    p.add_argument("--config",default="config/b0.yaml")
    p.add_argument("--fill",choices=["optimistic","realistic","conservative","all"],default="all")
    p.set_defaults(func=cmd_run_b0)

    args=parser.parse_args()
    return args.func(args)


if __name__=="__main__":
    raise SystemExit(main())
