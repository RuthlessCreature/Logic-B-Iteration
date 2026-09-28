from __future__ import annotations

import argparse
from datetime import date,datetime
import json
from pathlib import Path

import pandas as pd
import yaml

from .alignment import compare_human_proxy
from .audit import audit_auxiliary_bundle,audit_daily_bundle,summarize_issues
from .diagnostics import preflight_provider
from .features import classify_market_regime
from .ingest import HistoricalIngestor
from .models import FillModel
from .providers.tushare import TushareProvider
from .replay.runner import B0ReplayRunner
from .reporting import write_run_artifacts
from .storage import LocalParquetStore


def _date(v: str) -> date:
    return datetime.strptime(v,"%Y-%m-%d").date()


def _config(path: str) -> dict:
    cfg=yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required=["version","universe","portfolio","execution","research"]
    missing=[k for k in required if k not in cfg]
    if missing:
        raise SystemExit(f"missing config keys: {missing}")
    return cfg


def _read_table(path: str) -> pd.DataFrame:
    p=Path(path)
    if p.suffix.lower()==".parquet":
        return pd.read_parquet(p)
    if p.suffix.lower()==".csv":
        return pd.read_csv(p)
    raise SystemExit("supported table formats: .csv, .parquet")


def _calendar_dates(
    store: LocalParquetStore,
    start: date,
    end: date,
) -> list[str]:
    key=f"{start:%Y%m%d}_{end:%Y%m%d}"
    cal=store.read_optional("calendar",key)
    if cal is None:
        cal=store.read_all_parts("calendar")
    if cal.empty:
        raise SystemExit(
            "no cached trade calendar covers the requested range; "
            "run fetch-daily first"
        )
    col="cal_date" if "cal_date" in cal.columns else "trade_date"
    dates=sorted(
        set(pd.to_datetime(cal[col]).dt.strftime("%Y%m%d").tolist())
    )
    selected=[
        d for d in dates
        if f"{start:%Y%m%d}"<=d<=f"{end:%Y%m%d}"
    ]
    if not selected:
        raise SystemExit(
            "cached calendar has no trading days in requested range"
        )
    return selected


def assert_holdout_access(
    cfg: dict,
    start: date,
    end: date,
    *,
    unlock: bool,
) -> bool:
    research=cfg["research"]
    blind_start=_date(research["blind_holdout_start"])
    blind_end=_date(research["blind_holdout_end"])
    touches=end>=blind_start and start<=blind_end
    if touches and not unlock:
        raise SystemExit(
            f"blind holdout is locked: {blind_start}..{blind_end}; "
            "freeze a candidate version first, then rerun with "
            "--unlock-holdout"
        )
    return touches


def cmd_smoke(_: argparse.Namespace) -> int:
    r=classify_market_regime(
        limit_up_count=72,
        limit_down_count=4,
        break_rate=.16,
        max_height=7,
        prev_limit_median_return=.021,
    )
    print(json.dumps(
        {"status":"ok","example_regime":r.value},
        ensure_ascii=False,
    ))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    cfg=_config(args.path)
    print(json.dumps(
        {"status":"ok","version":cfg["version"]},
        ensure_ascii=False,
    ))
    return 0


def cmd_preflight_data(args: argparse.Namespace) -> int:
    day=_date(args.date)
    result=preflight_provider(
        TushareProvider(),
        day,
        sample_code=args.code,
    )
    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    ))
    return 0 if result["ok"] else 2


def cmd_fetch_daily(args: argparse.Namespace) -> int:
    start=_date(args.start)
    end=_date(args.end)
    store=LocalParquetStore(args.data_root)
    ing=HistoricalIngestor(TushareProvider(),store)
    dates=ing.fetch_range(start,end,force=args.force)
    print(json.dumps({
        "status":"ok",
        "days":len(dates),
        "first":dates[0] if dates else None,
        "last":dates[-1] if dates else None,
    },ensure_ascii=False))
    return 0


def cmd_fetch_minutes(args: argparse.Namespace) -> int:
    start=_date(args.start)
    end=_date(args.end)
    store=LocalParquetStore(args.data_root)
    ing=HistoricalIngestor(TushareProvider(),store)
    dates=_calendar_dates(store,start,end)
    total=0
    for i in range(1,len(dates)):
        day=pd.to_datetime(dates[i]).date()
        prev=pd.to_datetime(dates[i-1]).date()
        total+=len(
            ing.fetch_prev_limit_candidates_minutes(
                day,prev,force=args.force
            )
        )
    print(json.dumps({
        "status":"ok",
        "trade_days":len(dates),
        "minute_symbol_days":total,
    },ensure_ascii=False))
    return 0


def cmd_audit_data(args: argparse.Namespace) -> int:
    start=_date(args.start)
    end=_date(args.end)
    store=LocalParquetStore(args.data_root)
    dates=_calendar_dates(store,start,end)

    daily_results=[]
    total_errors=0
    total_warnings=0
    for key in dates:
        try:
            limit_up=store.read_frame("limit_up",key)
            issues=audit_daily_bundle(
                daily=store.read_frame("daily",key),
                limit_prices=store.read_frame("limit_prices",key),
                limit_up=limit_up,
                limit_down=store.read_frame("limit_down",key),
                limit_break=store.read_optional("limit_break",key),
            )
            issues.extend(audit_auxiliary_bundle(
                limit_up=limit_up,
                kpl_limit_up=store.read_frame("kpl_limit_up",key),
                stock_st=store.read_frame("stock_st",key),
                suspend=store.read_frame("suspend",key),
                auction=store.read_frame("auction",key),
            ))
            summary=summarize_issues(issues)
        except FileNotFoundError as exc:
            summary={
                "errors":1,
                "warnings":0,
                "issue_types":1,
                "issues":[{
                    "severity":"ERROR",
                    "code":"MISSING_DATASET",
                    "message":str(exc),
                    "count":1,
                }],
            }
        total_errors+=int(summary["errors"])
        total_warnings+=int(summary["warnings"])
        if summary["issue_types"]:
            daily_results.append({
                "trade_date":key,
                **summary,
            })

    result={
        "status":"ok" if total_errors==0 else "failed",
        "trade_days":len(dates),
        "errors":total_errors,
        "warnings":total_warnings,
        "days_with_issues":len(daily_results),
        "details":daily_results,
    }
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if total_errors==0 else 2


def cmd_align_b0(args: argparse.Namespace) -> int:
    human=_read_table(args.human)
    proxy=_read_table(args.proxy)
    metrics,audit=compare_human_proxy(human,proxy)

    if args.out:
        out=Path(args.out)
        out.parent.mkdir(parents=True,exist_ok=True)
        if out.suffix.lower()==".parquet":
            audit.to_parquet(out,index=False)
        elif out.suffix.lower()==".csv":
            audit.to_csv(out,index=False)
        else:
            raise SystemExit("--out must end in .csv or .parquet")

    print(json.dumps(
        {"status":"ok","metrics":metrics,"audit_rows":len(audit)},
        ensure_ascii=False,
        allow_nan=True,
        indent=2,
    ))
    return 0


def cmd_run_b0(args: argparse.Namespace) -> int:
    cfg=_config(args.config)
    start=_date(args.start)
    end=_date(args.end)
    touches_holdout=assert_holdout_access(
        cfg,start,end,unlock=args.unlock_holdout
    )

    store=LocalParquetStore(args.data_root)
    dates=_calendar_dates(store,start,end)

    minute_loader=None
    if args.fetch_missing_minutes:
        ingestor=HistoricalIngestor(
            TushareProvider(),
            store,
        )

        def minute_loader(day_key: str,code: str) -> pd.DataFrame:
            day=pd.to_datetime(day_key).date()
            ingestor.fetch_minutes(day,[code],force=False)
            return store.read_frame(
                "minute_1m",
                f"{day_key}/{code}",
            )

    selected=[FillModel(args.fill)] if args.fill!="all" else [
        FillModel.OPTIMISTIC,
        FillModel.REALISTIC,
        FillModel.CONSERVATIVE,
    ]

    outputs=[]
    for model in selected:
        runner=B0ReplayRunner(
            store,
            fill_model=model,
            initial_cash=float(
                cfg["portfolio"].get("initial_cash",1_000_000)
            ),
            fee_rate=float(
                cfg["execution"].get("commission_rate",0.0003)
            ),
            stamp_rate=float(
                cfg["execution"].get("stamp_rate",0.0005)
            ),
            checkpoint=datetime.strptime(
                cfg["execution"].get("decision_checkpoint","09:35"),
                "%H:%M",
            ).time(),
            minute_loader=minute_loader,
            exclude_st=bool(
                cfg["universe"].get(
                    "exclude_st",
                    True,
                )
            ),
        )
        result=runner.run(dates)
        run_dir=Path(args.run_root)/(
            f'{cfg["version"]}_{start:%Y%m%d}_'
            f'{end:%Y%m%d}_{model.value}'
        )
        write_run_artifacts(
            run_dir=run_dir,
            signals=result.signals,
            fills=result.fills,
            trades=result.trades,
            daily_equity=result.daily_equity,
            metrics=result.metrics,
            config=cfg,
            metadata={
                "start":args.start,
                "end":args.end,
                "fill_model":model.value,
                "blind_holdout_touched":touches_holdout,
                "holdout_explicitly_unlocked":bool(
                    args.unlock_holdout
                ),
            },
        )
        outputs.append({
            "fill_model":model.value,
            "run_dir":str(run_dir),
            "metrics":result.metrics,
        })

    print(json.dumps(
        {"status":"ok","runs":outputs},
        ensure_ascii=False,
        default=str,
        indent=2,
    ))
    return 0


def _add_range_args(
    p: argparse.ArgumentParser,
    *,
    include_force: bool=False,
) -> None:
    p.add_argument("--start",required=True)
    p.add_argument("--end",required=True)
    p.add_argument("--data-root",default="data")
    if include_force:
        p.add_argument("--force",action="store_true")


def main() -> int:
    parser=argparse.ArgumentParser(prog="logic-b")
    sub=parser.add_subparsers(dest="cmd",required=True)

    p=sub.add_parser("smoke")
    p.set_defaults(func=cmd_smoke)

    p=sub.add_parser("validate-config")
    p.add_argument("path")
    p.set_defaults(func=cmd_validate)

    p=sub.add_parser("preflight-data")
    p.add_argument("--date",required=True)
    p.add_argument("--code")
    p.set_defaults(func=cmd_preflight_data)

    p=sub.add_parser("fetch-daily")
    _add_range_args(p,include_force=True)
    p.set_defaults(func=cmd_fetch_daily)

    p=sub.add_parser("fetch-minutes")
    _add_range_args(p,include_force=True)
    p.set_defaults(func=cmd_fetch_minutes)

    p=sub.add_parser("audit-data")
    _add_range_args(p)
    p.set_defaults(func=cmd_audit_data)

    p=sub.add_parser("align-b0")
    p.add_argument("--human",required=True)
    p.add_argument("--proxy",required=True)
    p.add_argument("--out")
    p.set_defaults(func=cmd_align_b0)

    p=sub.add_parser("run-b0")
    _add_range_args(p)
    p.add_argument("--run-root",default="runs")
    p.add_argument("--config",default="config/b0.yaml")
    p.add_argument(
        "--fill",
        choices=[
            "optimistic","realistic","conservative","all"
        ],
        default="all",
    )
    p.add_argument(
        "--unlock-holdout",
        action="store_true",
        help="explicitly allow final blind-holdout evaluation",
    )
    p.add_argument(
        "--fetch-missing-minutes",
        action="store_true",
        help="fetch missing minute bars on demand and persist them locally",
    )
    p.set_defaults(func=cmd_run_b0)

    args=parser.parse_args()
    return args.func(args)


if __name__=="__main__":
    raise SystemExit(main())
