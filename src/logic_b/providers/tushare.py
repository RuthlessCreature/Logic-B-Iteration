from __future__ import annotations

import os
from datetime import date, datetime

import pandas as pd
import tushare as ts

from .base import MarketDataProvider


def _d(v: date) -> str:
    return v.strftime("%Y%m%d")


class TushareProvider(MarketDataProvider):
    """Tushare historical provider.

    Required:
      - TUSHARE_TOKEN
      - 8000-point permission for limit_list_ths
      - separate stock-minute permission for minute replay

    Note: stk_auction_o is published by Tushare after market close. In historical
    replay it represents auction information that market participants could
    observe during the auction, but it must not be described as a live Tushare
    feed available at 09:25.
    """

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise RuntimeError("TUSHARE_TOKEN is required")
        ts.set_token(self.token)
        self.pro = ts.pro_api(self.token)

    def trade_calendar(self, start: date, end: date) -> pd.DataFrame:
        return self.pro.trade_cal(
            exchange="SSE", start_date=_d(start), end_date=_d(end), is_open="1"
        ).sort_values("cal_date")

    def limit_list(self, trade_date: date, limit_type: str = "涨停池") -> pd.DataFrame:
        return self.pro.limit_list_ths(trade_date=_d(trade_date), limit_type=limit_type)

    def daily(self, trade_date: date) -> pd.DataFrame:
        return self.pro.daily(trade_date=_d(trade_date))

    def limit_prices(self, trade_date: date) -> pd.DataFrame:
        return self.pro.stk_limit(trade_date=_d(trade_date))

    def opening_auction(self, trade_date: date) -> pd.DataFrame:
        return self.pro.stk_auction_o(trade_date=_d(trade_date))

    def stock_minute(
        self, ts_code: str, start: datetime, end: datetime, freq: str = "1min"
    ) -> pd.DataFrame:
        df = ts.pro_bar(
            ts_code=ts_code,
            freq=freq,
            start_date=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=end.strftime("%Y-%m-%d %H:%M:%S"),
        )
        if df is None:
            return pd.DataFrame()
        if "trade_time" in df.columns:
            df["trade_time"] = pd.to_datetime(df["trade_time"])
            df = df.sort_values("trade_time")
        return df.reset_index(drop=True)
