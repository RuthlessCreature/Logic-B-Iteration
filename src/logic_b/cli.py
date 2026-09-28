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
from .neighborhood import build_threshold_neighborhood,evaluate_threshold_neighborhood
from .promotion import evaluate_promotion
from .providers.tushare import TushareProvider
from .providers.xuangubao import XuangubaoEvidenceProvider
from .providers.xuangubao_market import XuangubaoMarketProvider
from .readiness import assess_data_readiness
from .replay.runner import B0ReplayRunner
from .reporting import write_run_artifacts
from .storage import LocalParquetStore
from .strategy.b0 import B0Proxy
from .walkforward import evaluate_walk_forward
from .xgb_ingest import XuangubaoEvidenceIngestor
from .xgb_market_ingest import XuangubaoMarketIngestor
from .xgb_readiness import assess_xgb_candidate_readiness


def _date(v: str) -> date:
    return datetime.strptime(v,"%Y-%m-%d").date()


def _config(path: str) -> dict:
    cfg=yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required=["version","universe","portfolio","execution","research"]
    missing=[k for k in required if k not in cfg]
    if missing:
        raise SystemExit(f"missing config keys: {missing}")
    return cfg


def _read_json(path: str | None) -> dict | None:
    if not path:
        return None
    return json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )


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


def cmd_preflight_xgb(args: argparse.Namespace) -> int:
    day=_date(args.date)
    result=XuangubaoEvidenceProvider().preflight(
        day
    )
    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        default=str,
    ))
    return 0 if result["ok"] else 2


def cmd_preflight_xgb_market(args: argparse.Namespace) -> int:
    day=_date(args.date)
    evidence=XuangubaoEvidenceProvider()
    pool=evidence.limit_list(
        day,
        "涨停池",
    )

    code=args.code
    pre_close=args.pre_close
    source_row=None

    if code:
        if not pool.empty:
            matched=pool[
                pool["ts_code"].astype(str)
                ==str(code)
            ]
            if not matched.empty:
                source_row=matched.iloc[0]
    else:
        if pool.empty:
            print(json.dumps({
                "ok":False,
                "trade_date":day.strftime("%Y%m%d"),
                "error":"no limit-up sample available; pass --code and --pre-close",
            },ensure_ascii=False,indent=2))
            return 2
        source_row=pool.iloc[0]
        code=str(source_row["ts_code"])

    if pre_close is None and source_row is not None:
        value=source_row.get("prev_close")
        try:
            pre_close=float(value)
        except (TypeError,ValueError):
            pre_close=None

    market=XuangubaoMarketProvider()
    minute_day=market.historical_minute_day(
        str(code),
        day,
        pre_close_override=pre_close,
    )
    daily=market.daily_from_minute(
        minute_day
    )
    limits=market.limit_prices(
        minute_day
    )

    required_minute={
        "trade_time","open","high","low",
        "close","vol","amount",
    }
    result={
        "ok":(
            not minute_day.bars.empty
            and required_minute.issubset(
                minute_day.bars.columns
            )
            and not daily.empty
            and not limits.empty
        ),
        "trade_date":day.strftime("%Y%m%d"),
        "ts_code":str(code),
        "minute_rows":len(minute_day.bars),
        "minute_columns":list(
            minute_day.bars.columns
        ),
        "pre_close":minute_day.pre_close,
        "pre_close_source":
            minute_day.pre_close_source,
        "daily_rows":len(daily),
        "limit_rows":len(limits),
        "first_bar_time":(
            str(
                minute_day.bars.iloc[0][
                    "trade_time"
                ]
            )
            if not minute_day.bars.empty
            else None
        ),
        "last_bar_time":(
            str(
                minute_day.bars.iloc[-1][
                    "trade_time"
                ]
            )
            if not minute_day.bars.empty
            else None
        ),
    }
    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        default=str,
    ))
    return 0 if result["ok"] else 2


def cmd_fetch_xgb_evidence(args: argparse.Namespace) -> int:
    start=_date(args.start)
    end=_date(args.end)
    store=LocalParquetStore(args.data_root)
    ingestor=XuangubaoEvidenceIngestor(
        XuangubaoEvidenceProvider(),
        store,
        inter_request_sleep=args.sleep,
    )
    dates=ingestor.fetch_range(
        start,
        end,
        force=args.force,
    )
    print(json.dumps({
        "status":"ok",
        "source":"xuangubao",
        "trade_days":len(dates),
        "first":dates[0] if dates else None,
        "last":dates[-1] if dates else None,
        "datasets":list(
            XuangubaoEvidenceIngestor.DATASETS
        ),
    },ensure_ascii=False,indent=2))
    return 0


def cmd_fetch_xgb_market(args: argparse.Namespace) -> int:
    start=_date(args.start)
    end=_date(args.end)
    store=LocalParquetStore(args.data_root)
    dates=_calendar_dates(
        store,
        start,
        end,
    )
    ingestor=XuangubaoMarketIngestor(
        XuangubaoMarketProvider(),
        store,
        inter_request_sleep=args.sleep,
    )
    summary=ingestor.materialize_range(
        trade_dates=dates,
        force=args.force,
    )
    print(json.dumps({
        "status":"ok",
        "source":"xuangubao",
        "start":args.start,
        "end":args.end,
        **summary,
    },ensure_ascii=False,indent=2))
    return 0


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


def cmd_xgb_readiness(args: argparse.Namespace) -> int:
    cfg=_config(args.config)
    start=_date(args.start)
    end=_date(args.end)
    store=LocalParquetStore(
        args.data_root
    )
    dates=_calendar_dates(
        store,
        start,
        end,
    )
    report=assess_xgb_candidate_readiness(
        store=store,
        trade_dates=dates,
        include_boards=tuple(
            cfg["universe"].get(
                "include_boards",
                [],
            )
        ),
        exclude_st=bool(
            cfg["universe"].get(
                "exclude_st",
                True,
            )
        ),
        exclude_no_limit_ipo_days=bool(
            cfg["universe"].get(
                "exclude_no_limit_ipo_days",
                True,
            )
        ),
    )
    payload=report.as_dict()
    print(json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    ))
    return 0 if report.ready else 2


def cmd_data_readiness(args: argparse.Namespace) -> int:
    cfg=_config(args.config)
    start=_date(args.start)
    end=_date(args.end)

    # Readiness can inspect holdout cache, but this command never runs or
    # reports strategy performance.
    store=LocalParquetStore(args.data_root)
    dates=_calendar_dates(store,start,end)

    report=assess_data_readiness(
        store=store,
        trade_dates=dates,
        include_boards=tuple(
            cfg["universe"].get(
                "include_boards",
                [],
            )
        ),
        exclude_st=bool(
            cfg["universe"].get(
                "exclude_st",
                True,
            )
        ),
        exclude_no_limit_ipo_days=bool(
            cfg["universe"].get(
                "exclude_no_limit_ipo_days",
                True,
            )
        ),
    )
    payload=report.as_dict()
    print(json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    ))
    return 0 if report.ready else 2


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

    if args.metrics_out:
        metrics_out=Path(
            args.metrics_out
        )
        metrics_out.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        metrics_out.write_text(
            json.dumps(
                metrics,
                ensure_ascii=False,
                allow_nan=True,
                indent=2,
            ),
            encoding="utf-8",
        )

    print(json.dumps(
        {"status":"ok","metrics":metrics,"audit_rows":len(audit)},
        ensure_ascii=False,
        allow_nan=True,
        indent=2,
    ))
    return 0


def cmd_promotion_check(args: argparse.Namespace) -> int:
    cfg=_config(args.config)
    result=evaluate_promotion(
        promotion_config=cfg["promotion"],
        conservative_metrics=_read_json(
            args.conservative
        ),
        walk_forward_summary=_read_json(
            args.walk_forward
        ),
        alignment_metrics=_read_json(
            args.alignment
        ),
        neighborhood_stability=_read_json(
            args.stability
        ),
        candidate_meta=_read_json(
            args.candidate_meta
        ),
    )

    if args.out:
        out=Path(args.out)
        out.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        out.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    ))
    return (
        0
        if result["status"]=="PASS"
        else 2
    )


def _xgb_pre_close_for_symbol_day(
    *,
    store: LocalParquetStore,
    trade_dates: list[str],
    day_key: str,
    code: str,
) -> float | None:
    limits=store.read_optional(
        "limit_prices",
        day_key,
    )
    if (
        limits is not None
        and not limits.empty
        and "ts_code" in limits.columns
        and "pre_close" in limits.columns
    ):
        row=limits[
            limits["ts_code"].astype(str)
            ==str(code)
        ]
        if not row.empty:
            value=pd.to_numeric(
                row.iloc[0]["pre_close"],
                errors="coerce",
            )
            if pd.notna(value) and float(value)>0:
                return float(value)

    normalized=[
        pd.to_datetime(value).strftime("%Y%m%d")
        for value in trade_dates
    ]
    try:
        index=normalized.index(
            pd.to_datetime(day_key).strftime("%Y%m%d")
        )
    except ValueError:
        index=-1

    if index>0:
        prev=normalized[index-1]

        daily=store.read_optional(
            "daily",
            prev,
        )
        if (
            daily is not None
            and not daily.empty
            and "ts_code" in daily.columns
            and "close" in daily.columns
        ):
            row=daily[
                daily["ts_code"].astype(str)
                ==str(code)
            ]
            if not row.empty:
                value=pd.to_numeric(
                    row.iloc[0]["close"],
                    errors="coerce",
                )
                if (
                    pd.notna(value)
                    and float(value)>0
                ):
                    return float(value)

        prior_pool=store.read_optional(
            "limit_up",
            prev,
        )
        if (
            prior_pool is not None
            and not prior_pool.empty
            and "ts_code" in prior_pool.columns
        ):
            row=prior_pool[
                prior_pool["ts_code"].astype(str)
                ==str(code)
            ]
            if not row.empty:
                return XuangubaoMarketIngestor.pre_close_from_prior_row(
                    row.iloc[0]
                )

    return None


def _loaders_for_run(
    *,
    enabled: bool,
    source: str,
    store: LocalParquetStore,
    trade_dates: list[str],
):
    if not enabled:
        return None,None

    if source=="tushare":
        ingestor=HistoricalIngestor(
            TushareProvider(),
            store,
        )

        def minute_loader(
            day_key: str,
            code: str,
        ) -> pd.DataFrame:
            day=pd.to_datetime(
                day_key
            ).date()
            ingestor.fetch_minutes(
                day,
                [code],
                force=False,
            )
            return store.read_frame(
                "minute_1m",
                f"{day_key}/{code}",
            )

        return minute_loader,None

    if source=="xuangubao":
        ingestor=XuangubaoMarketIngestor(
            XuangubaoMarketProvider(),
            store,
            inter_request_sleep=0.10,
        )

        def market_loader(
            day_key: str,
            code: str,
        ):
            pre_close=_xgb_pre_close_for_symbol_day(
                store=store,
                trade_dates=trade_dates,
                day_key=day_key,
                code=code,
            )
            result=ingestor.materialize_symbol_day(
                trade_date=pd.to_datetime(
                    day_key
                ).date(),
                ts_code=code,
                pre_close=pre_close,
                force=False,
            )
            return result

        def minute_loader(
            day_key: str,
            code: str,
        ) -> pd.DataFrame:
            result=market_loader(
                day_key,
                code,
            )
            return result["minute_1m"]

        return minute_loader,market_loader

    raise SystemExit(
        f"unsupported missing-minute source: {source}"
    )


def _runner_from_config(
    *,
    cfg: dict,
    store: LocalParquetStore,
    model: FillModel,
    minute_loader=None,
    market_loader=None,
    strategy=None,
) -> B0ReplayRunner:
    if strategy is None:
        strategy_cfg=cfg.get(
            "strategy",
            {},
        )
        strategy=B0Proxy(
            min_confirmation=float(
                strategy_cfg.get(
                    "min_confirmation",
                    0.58,
                )
            ),
            min_tradability=float(
                strategy_cfg.get(
                    "min_tradability",
                    0.45,
                )
            ),
        )

    return B0ReplayRunner(
        store,
        strategy=strategy,
        fill_model=model,
        initial_cash=float(
            cfg["portfolio"].get(
                "initial_cash",
                1_000_000,
            )
        ),
        fee_rate=float(
            cfg["execution"].get(
                "commission_rate",
                0.0003,
            )
        ),
        minimum_commission=float(
            cfg["execution"].get(
                "minimum_commission",
                5.0,
            )
        ),
        transfer_fee_rate=float(
            cfg["execution"].get(
                "transfer_fee_rate",
                0.00001,
            )
        ),
        stamp_rate=float(
            cfg["execution"].get(
                "stamp_rate",
                0.0005,
            )
        ),
        checkpoint=datetime.strptime(
            cfg["execution"].get(
                "decision_checkpoint",
                "09:35",
            ),
            "%H:%M",
        ).time(),
        minute_loader=minute_loader,
        market_loader=market_loader,
        exclude_st=bool(
            cfg["universe"].get(
                "exclude_st",
                True,
            )
        ),
        include_boards=tuple(
            cfg["universe"].get(
                "include_boards",
                [],
            )
        ),
        exclude_no_limit_ipo_days=bool(
            cfg["universe"].get(
                "exclude_no_limit_ipo_days",
                True,
            )
        ),
    )


def cmd_run_b0(args: argparse.Namespace) -> int:
    cfg=_config(args.config)
    start=_date(args.start)
    end=_date(args.end)
    touches_holdout=assert_holdout_access(
        cfg,start,end,unlock=args.unlock_holdout
    )

    store=LocalParquetStore(args.data_root)
    dates=_calendar_dates(store,start,end)

    minute_loader,market_loader=_loaders_for_run(
        enabled=args.fetch_missing_minutes,
        source=args.missing_minute_source,
        store=store,
        trade_dates=dates,
    )

    selected=[FillModel(args.fill)] if args.fill!="all" else [
        FillModel.OPTIMISTIC,
        FillModel.REALISTIC,
        FillModel.CONSERVATIVE,
    ]

    outputs=[]
    for model in selected:
        runner=_runner_from_config(
            cfg=cfg,
            store=store,
            model=model,
            minute_loader=minute_loader,
            market_loader=market_loader,
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


def cmd_parameter_neighborhood_b0(args: argparse.Namespace) -> int:
    cfg=_config(args.config)
    start=_date(args.start)
    end=_date(args.end)

    assert_holdout_access(
        cfg,
        start,
        end,
        unlock=False,
    )

    store=LocalParquetStore(
        args.data_root
    )
    dates=_calendar_dates(
        store,
        start,
        end,
    )

    minute_loader,market_loader=_loaders_for_run(
        enabled=args.fetch_missing_minutes,
        source=args.missing_minute_source,
        store=store,
        trade_dates=dates,
    )

    strategy_cfg=cfg.get(
        "strategy",
        {},
    )
    base_confirmation=float(
        strategy_cfg.get(
            "min_confirmation",
            0.58,
        )
    )
    base_tradability=float(
        strategy_cfg.get(
            "min_tradability",
            0.45,
        )
    )
    neighborhood_cfg=strategy_cfg.get(
        "neighborhood",
        {},
    )

    points=build_threshold_neighborhood(
        base_confirmation=base_confirmation,
        base_tradability=base_tradability,
        confirmation_step=float(
            neighborhood_cfg.get(
                "confirmation_step",
                0.03,
            )
        ),
        tradability_step=float(
            neighborhood_cfg.get(
                "tradability_step",
                0.05,
            )
        ),
    )
    model=FillModel(args.fill)

    rows,summary=evaluate_threshold_neighborhood(
        trade_dates=dates,
        runner_factory=lambda point:_runner_from_config(
            cfg=cfg,
            store=store,
            model=model,
            minute_loader=minute_loader,
            market_loader=market_loader,
            strategy=B0Proxy(
                min_confirmation=
                    point.min_confirmation,
                min_tradability=
                    point.min_tradability,
            ),
        ),
        points=points,
        min_positive_expectancy_rate=float(
            neighborhood_cfg.get(
                "min_positive_expectancy_rate",
                0.75,
            )
        ),
        min_positive_total_return_rate=float(
            neighborhood_cfg.get(
                "min_positive_total_return_rate",
                0.75,
            )
        ),
        max_neighbor_drawdown_abs=float(
            neighborhood_cfg.get(
                "max_neighbor_drawdown_abs",
                0.30,
            )
        ),
        min_closed_trades_each=int(
            neighborhood_cfg.get(
                "min_closed_trades_each",
                20,
            )
        ),
    )

    run_dir=Path(args.run_root)/(
        f'neighborhood_{cfg["version"]}_'
        f'{start:%Y%m%d}_{end:%Y%m%d}_'
        f'{model.value}'
    )
    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    pd.DataFrame(rows).to_parquet(
        run_dir/"neighbors.parquet",
        index=False,
    )
    (run_dir/"neighborhood.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            allow_nan=True,
        ),
        encoding="utf-8",
    )
    (run_dir/"spec.json").write_text(
        json.dumps({
            "version":cfg["version"],
            "base_confirmation":
                base_confirmation,
            "base_tradability":
                base_tradability,
            "fill_model":model.value,
            "start":args.start,
            "end":args.end,
            "neighbor_count":len(points),
        },ensure_ascii=False,indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "status":"ok",
        "run_dir":str(run_dir),
        "summary":summary,
    },ensure_ascii=False,indent=2,allow_nan=True))
    return 0


def cmd_walk_forward_b0(args: argparse.Namespace) -> int:
    cfg=_config(args.config)
    start=_date(args.start)
    end=_date(args.end)

    # Walk-forward is a development-set diagnostic, never a holdout tool.
    assert_holdout_access(
        cfg,
        start,
        end,
        unlock=False,
    )

    store=LocalParquetStore(args.data_root)
    dates=_calendar_dates(
        store,
        start,
        end,
    )
    model=FillModel(args.fill)
    minute_loader,market_loader=_loaders_for_run(
        enabled=args.fetch_missing_minutes,
        source=args.missing_minute_source,
        store=store,
        trade_dates=dates,
    )

    initial_cash=float(
        cfg["portfolio"].get(
            "initial_cash",
            1_000_000,
        )
    )

    research=cfg["research"]
    min_train_days=(
        args.min_train_days
        if args.min_train_days is not None
        else int(research.get("walk_forward_min_train_days",120))
    )
    validation_days=(
        args.validation_days
        if args.validation_days is not None
        else int(research.get("walk_forward_validation_days",40))
    )
    step_days=(
        args.step_days
        if args.step_days is not None
        else int(research.get("walk_forward_step_days",40))
    )
    warmup_days=(
        args.warmup_days
        if args.warmup_days is not None
        else int(research.get("walk_forward_warmup_days",2))
    )

    fold_metrics,summary=evaluate_walk_forward(
        trade_dates=dates,
        runner_factory=lambda:_runner_from_config(
            cfg=cfg,
            store=store,
            model=model,
            minute_loader=minute_loader,
            market_loader=market_loader,
        ),
        initial_cash=initial_cash,
        min_train_days=min_train_days,
        validation_days=validation_days,
        step_days=step_days,
        warmup_days=warmup_days,
    )

    run_dir=Path(args.run_root)/(
        f'walk_forward_{cfg["version"]}_'
        f'{start:%Y%m%d}_{end:%Y%m%d}_'
        f'{model.value}'
    )
    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    pd.DataFrame(
        fold_metrics
    ).to_parquet(
        run_dir/"fold_metrics.parquet",
        index=False,
    )
    (run_dir/"summary.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            allow_nan=True,
        ),
        encoding="utf-8",
    )
    (run_dir/"spec.json").write_text(
        json.dumps({
            "version":cfg["version"],
            "start":args.start,
            "end":args.end,
            "fill_model":model.value,
            "min_train_days":min_train_days,
            "validation_days":validation_days,
            "step_days":step_days,
            "warmup_days":warmup_days,
        },ensure_ascii=False,indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "status":"ok",
        "run_dir":str(run_dir),
        "summary":summary,
    },ensure_ascii=False,indent=2,allow_nan=True))
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

    p=sub.add_parser("preflight-xgb")
    p.add_argument("--date",required=True)
    p.set_defaults(func=cmd_preflight_xgb)

    p=sub.add_parser("preflight-xgb-market")
    p.add_argument("--date",required=True)
    p.add_argument("--code")
    p.add_argument(
        "--pre-close",
        type=float,
    )
    p.set_defaults(
        func=cmd_preflight_xgb_market
    )

    p=sub.add_parser("fetch-xgb-evidence")
    _add_range_args(p,include_force=True)
    p.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="polite delay between public API requests",
    )
    p.set_defaults(func=cmd_fetch_xgb_evidence)

    p=sub.add_parser("fetch-xgb-market")
    _add_range_args(
        p,
        include_force=True,
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.10,
        help="polite delay between historical symbol-day requests",
    )
    p.set_defaults(
        func=cmd_fetch_xgb_market
    )

    p=sub.add_parser("fetch-daily")
    _add_range_args(p,include_force=True)
    p.set_defaults(func=cmd_fetch_daily)

    p=sub.add_parser("fetch-minutes")
    _add_range_args(p,include_force=True)
    p.set_defaults(func=cmd_fetch_minutes)

    p=sub.add_parser("xgb-readiness")
    _add_range_args(p)
    p.add_argument(
        "--config",
        default="config/b0.yaml",
    )
    p.set_defaults(
        func=cmd_xgb_readiness
    )

    p=sub.add_parser("data-readiness")
    _add_range_args(p)
    p.add_argument("--config",default="config/b0.yaml")
    p.set_defaults(func=cmd_data_readiness)

    p=sub.add_parser("audit-data")
    _add_range_args(p)
    p.set_defaults(func=cmd_audit_data)

    p=sub.add_parser("align-b0")
    p.add_argument("--human",required=True)
    p.add_argument("--proxy",required=True)
    p.add_argument("--out")
    p.add_argument("--metrics-out")
    p.set_defaults(func=cmd_align_b0)

    p=sub.add_parser("promotion-check")
    p.add_argument("--config",default="config/b0.yaml")
    p.add_argument("--conservative",required=True)
    p.add_argument("--walk-forward",required=True)
    p.add_argument("--alignment")
    p.add_argument("--stability")
    p.add_argument("--candidate-meta")
    p.add_argument("--out")
    p.set_defaults(func=cmd_promotion_check)

    p=sub.add_parser("parameter-neighborhood-b0")
    _add_range_args(p)
    p.add_argument(
        "--run-root",
        default="runs",
    )
    p.add_argument(
        "--config",
        default="config/b0.yaml",
    )
    p.add_argument(
        "--fill",
        choices=[
            "realistic",
            "conservative",
        ],
        default="conservative",
    )
    p.add_argument(
        "--fetch-missing-minutes",
        action="store_true",
    )
    p.add_argument(
        "--missing-minute-source",
        choices=["tushare","xuangubao"],
        default="tushare",
    )
    p.set_defaults(
        func=cmd_parameter_neighborhood_b0
    )

    p=sub.add_parser("walk-forward-b0")
    _add_range_args(p)
    p.add_argument("--run-root",default="runs")
    p.add_argument("--config",default="config/b0.yaml")
    p.add_argument(
        "--fill",
        choices=[
            "optimistic",
            "realistic",
            "conservative",
        ],
        default="realistic",
    )
    p.add_argument("--min-train-days",type=int)
    p.add_argument("--validation-days",type=int)
    p.add_argument("--step-days",type=int)
    p.add_argument("--warmup-days",type=int)
    p.add_argument(
        "--fetch-missing-minutes",
        action="store_true",
    )
    p.add_argument(
        "--missing-minute-source",
        choices=["tushare","xuangubao"],
        default="tushare",
    )
    p.set_defaults(func=cmd_walk_forward_b0)

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
        help="fetch missing market/minute data on demand and persist it locally",
    )
    p.add_argument(
        "--missing-minute-source",
        choices=["tushare","xuangubao"],
        default="tushare",
        help="source used only when --fetch-missing-minutes is enabled",
    )
    p.set_defaults(func=cmd_run_b0)

    args=parser.parse_args()
    return args.func(args)


if __name__=="__main__":
    raise SystemExit(main())
