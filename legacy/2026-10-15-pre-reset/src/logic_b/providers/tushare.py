from __future__ import annotations

import os
import time as time_module
from datetime import date,datetime
from typing import Callable,TypeVar

import pandas as pd
import tushare as ts

from .base import MarketDataProvider


T=TypeVar("T")


def _d(v: date) -> str:
    return v.strftime("%Y%m%d")


class TushareProvider(MarketDataProvider):
    """Tushare historical provider with bounded transient retries.

    Required permissions vary by endpoint. The token is read from the
    TUSHARE_TOKEN environment variable unless supplied explicitly.

    stk_auction_o is vendor-published after the market close. In historical
    replay, its matched auction result may represent information observable by
    market participants at the open, but vendor publication time and market
    event time remain distinct concepts.
    """

    TRANSIENT_MARKERS=(
        "每分钟",
        "频率",
        "too many requests",
        "429",
        "timeout",
        "timed out",
        "connection",
        "temporarily",
        "temporary",
        "remote end closed",
        "reset by peer",
    )

    def __init__(
        self,
        token: str | None=None,
        *,
        max_attempts: int=5,
        retry_base_seconds: float=1.0,
        sleeper: Callable[[float],None]=time_module.sleep,
    ):
        self.token=token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise RuntimeError("TUSHARE_TOKEN is required")
        if max_attempts<1:
            raise ValueError("max_attempts must be >= 1")
        if retry_base_seconds<0:
            raise ValueError(
                "retry_base_seconds must be non-negative"
            )

        self.max_attempts=max_attempts
        self.retry_base_seconds=retry_base_seconds
        self.sleeper=sleeper

        ts.set_token(self.token)
        self.pro=ts.pro_api(self.token)

    @classmethod
    def _is_transient(cls,exc: Exception) -> bool:
        msg=str(exc).lower()
        return any(
            marker.lower() in msg
            for marker in cls.TRANSIENT_MARKERS
        )

    def _call(self,fn: Callable[[],T]) -> T:
        last: Exception | None=None
        for attempt in range(self.max_attempts):
            try:
                return fn()
            except Exception as exc:
                last=exc
                if (
                    not self._is_transient(exc)
                    or attempt+1>=self.max_attempts
                ):
                    raise
                delay=min(
                    self.retry_base_seconds*(2**attempt),
                    30.0,
                )
                self.sleeper(delay)
        assert last is not None
        raise last

    def trade_calendar(
        self,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        df=self._call(lambda:self.pro.trade_cal(
            exchange="SSE",
            start_date=_d(start),
            end_date=_d(end),
            is_open="1",
        ))
        return df.sort_values("cal_date")

    def limit_list(
        self,
        trade_date: date,
        limit_type: str="涨停池",
    ) -> pd.DataFrame:
        return self._call(
            lambda:self.pro.limit_list_ths(
                trade_date=_d(trade_date),
                limit_type=limit_type,
            )
        )

    def daily(self,trade_date: date) -> pd.DataFrame:
        return self._call(
            lambda:self.pro.daily(
                trade_date=_d(trade_date)
            )
        )

    def theme_limit_list(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        return self._call(
            lambda:self.pro.kpl_list(
                trade_date=_d(trade_date),
                tag="涨停",
            )
        )

    def limit_prices(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        return self._call(
            lambda:self.pro.stk_limit(
                trade_date=_d(trade_date)
            )
        )

    def opening_auction(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        return self._call(
            lambda:self.pro.stk_auction_o(
                trade_date=_d(trade_date)
            )
        )

    def st_status(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        return self._call(
            lambda:self.pro.stock_st(
                trade_date=_d(trade_date)
            )
        )

    def suspensions(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        return self._call(
            lambda:self.pro.suspend_d(
                trade_date=_d(trade_date),
                suspend_type="S",
            )
        )

    def stock_minute(
        self,
        ts_code: str,
        start: datetime,
        end: datetime,
        freq: str="1min",
    ) -> pd.DataFrame:
        df=self._call(lambda:ts.pro_bar(
            ts_code=ts_code,
            freq=freq,
            start_date=start.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            end_date=end.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        ))
        if df is None:
            return pd.DataFrame()
        if "trade_time" in df.columns:
            df["trade_time"]=pd.to_datetime(
                df["trade_time"]
            )
            df=df.sort_values("trade_time")
        return df.reset_index(drop=True)
