from __future__ import annotations

from datetime import date, datetime, time
from typing import Iterable

import pandas as pd

from .providers.base import MarketDataProvider
from .storage import LocalParquetStore


class HistoricalIngestor:
    """Idempotent historical data downloader.

    Daily bundles are cheap relative to minute data. Minute data is intentionally
    fetched only for specified candidate codes.
    """

    def __init__(self, provider: MarketDataProvider, store: LocalParquetStore):
        self.provider = provider
        self.store = store

    @staticmethod
    def key(day: date) -> str:
        return day.strftime("%Y%m%d")

    def fetch_calendar(self, start: date, end: date, *, force: bool = False) -> pd.DataFrame:
        key = f"{start:%Y%m%d}_{end:%Y%m%d}"
        if self.store.exists("calendar", key) and not force:
            return self.store.read_frame("calendar", key)
        df = self.provider.trade_calendar(start, end)
        self.store.write_frame("calendar", key, df, metadata={"source": "provider"})
        return df

    def fetch_daily_bundle(self, day: date, *, force: bool = False) -> dict[str, pd.DataFrame]:
        k = self.key(day)
        getters = {
            "limit_up": lambda: self.provider.limit_list(day, "涨停池"),
            "limit_down": lambda: self.provider.limit_list(day, "跌停池"),
            "limit_break": lambda: self.provider.limit_list(day, "炸板池"),
            "daily": lambda: self.provider.daily(day),
            "limit_prices": lambda: self.provider.limit_prices(day),
            "auction": lambda: self.provider.opening_auction(day),
        }
        out: dict[str, pd.DataFrame] = {}
        for dataset, getter in getters.items():
            if self.store.exists(dataset, k) and not force:
                out[dataset] = self.store.read_frame(dataset, k)
                continue
            frame = getter()
            self.store.write_frame(
                dataset,
                k,
                frame,
                metadata={
                    "source": type(self.provider).__name__,
                    "trade_date": k,
                },
            )
            out[dataset] = frame
        return out

    def fetch_range(self, start: date, end: date, *, force: bool = False) -> list[str]:
        cal = self.fetch_calendar(start, end, force=force)
        col = "cal_date" if "cal_date" in cal.columns else "trade_date"
        dates = [pd.to_datetime(v).date() for v in cal[col].tolist()]
        completed = []
        for d in dates:
            self.fetch_daily_bundle(d, force=force)
            completed.append(self.key(d))
        return completed

    def fetch_minutes(
        self,
        day: date,
        codes: Iterable[str],
        *,
        force: bool = False,
        start_at: time = time(9, 15),
        end_at: time = time(15, 5),
    ) -> list[str]:
        done=[]
        for code in sorted(set(map(str, codes))):
            partition=f"{self.key(day)}/{code}"
            if self.store.exists("minute_1m", partition) and not force:
                done.append(code)
                continue
            start=datetime.combine(day,start_at)
            end=datetime.combine(day,end_at)
            frame=self.provider.stock_minute(code,start,end,"1min")
            self.store.write_frame(
                "minute_1m",
                partition,
                frame,
                metadata={
                    "source": type(self.provider).__name__,
                    "trade_date": self.key(day),
                    "ts_code": code,
                    "freq": "1min",
                },
            )
            done.append(code)
        return done

    def fetch_prev_limit_candidates_minutes(self, day: date, prev_day: date, *, force: bool = False) -> list[str]:
        prev_key=self.key(prev_day)
        if not self.store.exists("limit_up",prev_key):
            self.fetch_daily_bundle(prev_day,force=force)
        prev_up=self.store.read_frame("limit_up",prev_key)
        codes=prev_up["ts_code"].astype(str).tolist() if "ts_code" in prev_up.columns else []
        return self.fetch_minutes(day,codes,force=force)
