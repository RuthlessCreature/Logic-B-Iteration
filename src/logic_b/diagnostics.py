from __future__ import annotations

from dataclasses import asdict,dataclass
from datetime import date,datetime,time
from typing import Callable

import pandas as pd

from .providers.base import MarketDataProvider


@dataclass(frozen=True)
class EndpointCheck:
    name: str
    ok: bool
    rows: int
    columns: list[str]
    error: str | None=None
    note: str | None=None

    def as_dict(self) -> dict:
        return asdict(self)


def _run_check(
    name: str,
    fn: Callable[[],pd.DataFrame],
    *,
    require_rows: bool=False,
) -> tuple[EndpointCheck,pd.DataFrame | None]:
    try:
        frame=fn()
        if frame is None:
            frame=pd.DataFrame()

        ok=(
            len(frame)>0
            if require_rows
            else True
        )
        note=(
            "returned zero rows"
            if require_rows and frame.empty
            else None
        )
        return (
            EndpointCheck(
                name=name,
                ok=ok,
                rows=int(len(frame)),
                columns=list(frame.columns),
                note=note,
            ),
            frame,
        )
    except Exception as exc:
        return (
            EndpointCheck(
                name=name,
                ok=False,
                rows=0,
                columns=[],
                error=f"{type(exc).__name__}: {exc}",
            ),
            None,
        )


def preflight_provider(
    provider: MarketDataProvider,
    trade_date: date,
    *,
    sample_code: str | None=None,
) -> dict:
    """Probe every data dependency before a long historical download."""

    checks: list[EndpointCheck]=[]

    calendar,_=_run_check(
        "trade_calendar",
        lambda:provider.trade_calendar(
            trade_date,
            trade_date,
        ),
        require_rows=True,
    )
    checks.append(calendar)

    daily_check,daily=_run_check(
        "daily",
        lambda:provider.daily(trade_date),
        require_rows=True,
    )
    checks.append(daily_check)

    up_check,limit_up=_run_check(
        "limit_list_ths",
        lambda:provider.limit_list(
            trade_date,
            "涨停池",
        ),
    )
    checks.append(up_check)

    kpl_check,kpl=_run_check(
        "kpl_list",
        lambda:provider.theme_limit_list(
            trade_date
        ),
    )
    checks.append(kpl_check)

    limit_check,_=_run_check(
        "stk_limit",
        lambda:provider.limit_prices(
            trade_date
        ),
        require_rows=True,
    )
    checks.append(limit_check)

    auction_check,_=_run_check(
        "stk_auction_o",
        lambda:provider.opening_auction(
            trade_date
        ),
        require_rows=True,
    )
    checks.append(auction_check)

    st_check,_=_run_check(
        "stock_st",
        lambda:provider.st_status(
            trade_date
        ),
    )
    checks.append(st_check)

    suspend_check,_=_run_check(
        "suspend_d",
        lambda:provider.suspensions(
            trade_date
        ),
    )
    checks.append(suspend_check)

    chosen=sample_code
    if not chosen:
        for frame in (limit_up,kpl,daily):
            if (
                frame is not None
                and not frame.empty
                and "ts_code" in frame.columns
            ):
                chosen=str(
                    frame.iloc[0]["ts_code"]
                )
                break

    if chosen:
        start=datetime.combine(
            trade_date,
            time(9,30),
        )
        end=datetime.combine(
            trade_date,
            time(9,40),
        )
        minute_check,_=_run_check(
            "stock_minute_1m",
            lambda:provider.stock_minute(
                chosen,
                start,
                end,
                "1min",
            ),
            require_rows=True,
        )
        if (
            not minute_check.ok
            and minute_check.error is None
        ):
            minute_check=EndpointCheck(
                **{
                    **minute_check.as_dict(),
                    "note":
                        "zero rows; verify historical minute permission "
                        "and that the sample code traded on this date",
                }
            )
        checks.append(minute_check)
    else:
        checks.append(
            EndpointCheck(
                name="stock_minute_1m",
                ok=False,
                rows=0,
                columns=[],
                note=(
                    "no sample code available; "
                    "pass --code explicitly"
                ),
            )
        )

    failed=[
        check.name
        for check in checks
        if not check.ok
    ]
    return {
        "trade_date":
            trade_date.strftime("%Y%m%d"),
        "sample_code":chosen,
        "ok":not failed,
        "failed":failed,
        "checks":[
            check.as_dict()
            for check in checks
        ],
    }
