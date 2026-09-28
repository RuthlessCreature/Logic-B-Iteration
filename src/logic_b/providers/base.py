from __future__ import annotations

from abc import ABC,abstractmethod
from datetime import date,datetime

import pandas as pd


class MarketDataProvider(ABC):
    """Provider contract for point-in-time historical replay."""

    @abstractmethod
    def trade_calendar(
        self,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        ...

    @abstractmethod
    def limit_list(
        self,
        trade_date: date,
        limit_type: str="涨停池",
    ) -> pd.DataFrame:
        ...

    @abstractmethod
    def theme_limit_list(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        """Historical limit-up list with point-in-time theme labels."""
        ...

    @abstractmethod
    def daily(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        ...

    @abstractmethod
    def limit_prices(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        """Official exchange daily up/down price limits."""
        ...

    @abstractmethod
    def opening_auction(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        """Historical opening-auction summary."""
        ...

    @abstractmethod
    def st_status(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        """Historical risk-warning/ST list known before regular trading."""
        ...

    @abstractmethod
    def stock_minute(
        self,
        ts_code: str,
        start: datetime,
        end: datetime,
        freq: str="1min",
    ) -> pd.DataFrame:
        ...
