from __future__ import annotations

import time as time_module
from datetime import date,timedelta
from typing import Callable

import pandas as pd

from .providers.xuangubao import XuangubaoEvidenceProvider
from .storage import LocalParquetStore


class XuangubaoEvidenceIngestor:
    """Ingest public Xuangubao historical evidence into canonical datasets."""

    DATASETS=(
        "limit_up",
        "limit_down",
        "limit_break",
        "theme_limit_up",
        "market_indicator",
    )

    def __init__(
        self,
        provider: XuangubaoEvidenceProvider,
        store: LocalParquetStore,
        *,
        inter_request_sleep: float=0.15,
        sleeper: Callable[[float],None]=time_module.sleep,
    ):
        self.provider=provider
        self.store=store
        self.inter_request_sleep=inter_request_sleep
        self.sleeper=sleeper

    @staticmethod
    def key(day: date) -> str:
        return day.strftime("%Y%m%d")

    @staticmethod
    def _calendar_days(
        start: date,
        end: date,
    ) -> list[date]:
        days=[]
        current=start
        while current<=end:
            if current.weekday()<5:
                days.append(current)
            current+=timedelta(days=1)
        return days

    def _pause(self) -> None:
        if self.inter_request_sleep>0:
            self.sleeper(
                self.inter_request_sleep
            )

    def fetch_day(
        self,
        day: date,
        *,
        force: bool=False,
    ) -> dict[str,pd.DataFrame] | None:
        key=self.key(day)

        if (
            self.store.exists(
                "market_indicator",
                key,
            )
            and not force
        ):
            indicator=self.store.read_frame(
                "market_indicator",
                key,
            )
        else:
            indicator=self.provider.market_indicator_line(
                day
            )

        # Empty indicator line is treated as non-trading day / unavailable day.
        if indicator.empty:
            return None

        if (
            not self.store.exists(
                "market_indicator",
                key,
            )
            or force
        ):
            self.store.write_frame(
                "market_indicator",
                key,
                indicator,
                metadata={
                    "source":"xuangubao",
                    "trade_date":key,
                    "kind":"intraday_market_indicator_line",
                },
            )

        out={"market_indicator":indicator}

        pool_specs=(
            ("limit_up","涨停池"),
            ("limit_down","跌停池"),
            ("limit_break","炸板池"),
        )
        for dataset,pool_type in pool_specs:
            if (
                self.store.exists(
                    dataset,
                    key,
                )
                and not force
            ):
                frame=self.store.read_frame(
                    dataset,
                    key,
                )
            else:
                self._pause()
                frame=self.provider.limit_list(
                    day,
                    pool_type,
                )
                self.store.write_frame(
                    dataset,
                    key,
                    frame,
                    metadata={
                        "source":"xuangubao",
                        "trade_date":key,
                        "pool_type":pool_type,
                    },
                )
            out[dataset]=frame

        limit_up=out["limit_up"]
        if limit_up.empty:
            theme=pd.DataFrame(columns=[
                "trade_date",
                "ts_code",
                "theme",
                "status",
                "amount",
                "reason",
                "source",
            ])
        else:
            theme=pd.DataFrame({
                "trade_date":
                    limit_up["trade_date"],
                "ts_code":
                    limit_up["ts_code"],
                "theme":
                    limit_up["theme"],
                "status":
                    limit_up["tag"],
                "amount":
                    limit_up["turnover_estimated"],
                "reason":
                    limit_up["reason"],
                "source":
                    "xuangubao",
            })

        if (
            not self.store.exists(
                "theme_limit_up",
                key,
            )
            or force
        ):
            self.store.write_frame(
                "theme_limit_up",
                key,
                theme,
                metadata={
                    "source":"xuangubao",
                    "trade_date":key,
                },
            )
        else:
            theme=self.store.read_frame(
                "theme_limit_up",
                key,
            )
        out["theme_limit_up"]=theme
        return out

    def fetch_range(
        self,
        start: date,
        end: date,
        *,
        force: bool=False,
        progress_callback: Callable[[dict],None] | None=None,
    ) -> list[str]:
        trade_dates=[]
        for day in self._calendar_days(
            start,
            end,
        ):
            result=self.fetch_day(
                day,
                force=force,
            )
            if result is not None:
                trade_dates.append(
                    self.key(day)
                )
            if progress_callback is not None:
                progress_callback({
                    "calendar_date":self.key(day),
                    "trading_day":
                        result is not None,
                    "trade_days_found":
                        len(trade_dates),
                })
            self._pause()

        calendar=pd.DataFrame({
            "cal_date":trade_dates,
            "source":"xuangubao",
        })
        calendar_key=(
            f"{start:%Y%m%d}_"
            f"{end:%Y%m%d}"
        )
        self.store.write_frame(
            "calendar",
            calendar_key,
            calendar,
            metadata={
                "source":"xuangubao",
                "start":f"{start:%Y%m%d}",
                "end":f"{end:%Y%m%d}",
            },
        )
        return trade_dates
