from __future__ import annotations

from datetime import date,datetime,time
from typing import Iterable

import pandas as pd

from .providers.base import MarketDataProvider
from .storage import LocalParquetStore


class HistoricalIngestor:
    """Idempotent historical downloader backed by local Parquet partitions."""

    DAILY_DATASETS=(
        "limit_up",
        "limit_down",
        "limit_break",
        "kpl_limit_up",
        "daily",
        "limit_prices",
        "auction",
        "stock_st",
    )

    def __init__(
        self,
        provider: MarketDataProvider,
        store: LocalParquetStore,
    ):
        self.provider=provider
        self.store=store

    @staticmethod
    def key(day: date) -> str:
        return day.strftime("%Y%m%d")

    def fetch_calendar(
        self,
        start: date,
        end: date,
        *,
        force: bool=False,
    ) -> pd.DataFrame:
        key=f"{start:%Y%m%d}_{end:%Y%m%d}"
        if self.store.exists("calendar",key) and not force:
            return self.store.read_frame("calendar",key)

        frame=self.provider.trade_calendar(start,end)
        self.store.write_frame(
            "calendar",
            key,
            frame,
            metadata={
                "source":type(self.provider).__name__,
                "start":f"{start:%Y%m%d}",
                "end":f"{end:%Y%m%d}",
            },
        )
        return frame

    def fetch_daily_bundle(
        self,
        day: date,
        *,
        force: bool=False,
    ) -> dict[str,pd.DataFrame]:
        key=self.key(day)
        getters={
            "limit_up":lambda:self.provider.limit_list(
                day,"涨停池"
            ),
            "limit_down":lambda:self.provider.limit_list(
                day,"跌停池"
            ),
            "limit_break":lambda:self.provider.limit_list(
                day,"炸板池"
            ),
            "kpl_limit_up":lambda:self.provider.theme_limit_list(
                day
            ),
            "daily":lambda:self.provider.daily(day),
            "limit_prices":lambda:self.provider.limit_prices(
                day
            ),
            "auction":lambda:self.provider.opening_auction(day),
            "stock_st":lambda:self.provider.st_status(day),
        }

        out={}
        for dataset in self.DAILY_DATASETS:
            if self.store.exists(dataset,key) and not force:
                out[dataset]=self.store.read_frame(dataset,key)
                continue

            frame=getters[dataset]()
            self.store.write_frame(
                dataset,
                key,
                frame,
                metadata={
                    "source":type(self.provider).__name__,
                    "trade_date":key,
                },
            )
            out[dataset]=frame
        return out

    def fetch_range(
        self,
        start: date,
        end: date,
        *,
        force: bool=False,
    ) -> list[str]:
        calendar=self.fetch_calendar(
            start,end,force=force
        )
        col=(
            "cal_date"
            if "cal_date" in calendar.columns
            else "trade_date"
        )
        dates=[
            pd.to_datetime(value).date()
            for value in calendar[col].tolist()
        ]

        completed=[]
        for day in dates:
            self.fetch_daily_bundle(
                day,
                force=force,
            )
            completed.append(self.key(day))
        return completed

    def fetch_minutes(
        self,
        day: date,
        codes: Iterable[str],
        *,
        force: bool=False,
        start_at: time=time(9,15),
        end_at: time=time(15,5),
    ) -> list[str]:
        done=[]
        for code in sorted(set(map(str,codes))):
            partition=f"{self.key(day)}/{code}"
            if (
                self.store.exists(
                    "minute_1m",
                    partition,
                )
                and not force
            ):
                done.append(code)
                continue

            start=datetime.combine(day,start_at)
            end=datetime.combine(day,end_at)
            frame=self.provider.stock_minute(
                code,
                start,
                end,
                "1min",
            )
            self.store.write_frame(
                "minute_1m",
                partition,
                frame,
                metadata={
                    "source":type(self.provider).__name__,
                    "trade_date":self.key(day),
                    "ts_code":code,
                    "freq":"1min",
                },
            )
            done.append(code)
        return done

    def fetch_prev_limit_candidates_minutes(
        self,
        day: date,
        prev_day: date,
        *,
        force: bool=False,
    ) -> list[str]:
        prev_key=self.key(prev_day)
        if not self.store.exists("limit_up",prev_key):
            self.fetch_daily_bundle(
                prev_day,
                force=force,
            )

        prev_up=self.store.read_frame(
            "limit_up",
            prev_key,
        )
        codes=(
            prev_up["ts_code"].astype(str).tolist()
            if "ts_code" in prev_up.columns
            else []
        )
        return self.fetch_minutes(
            day,
            codes,
            force=force,
        )
