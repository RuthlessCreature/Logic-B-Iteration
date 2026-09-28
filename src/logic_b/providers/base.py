from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
import pandas as pd


class MarketDataProvider(ABC):
    """Provider contract for historical replay."""

    @abstractmethod
    def trade_calendar(self, start: date, end: date) -> pd.DataFrame: ...

    @abstractmethod
    def limit_list(self, trade_date: date, limit_type: str = "涨停池") -> pd.DataFrame: ...

    @abstractmethod
    def daily(self, trade_date: date) -> pd.DataFrame: ...

    @abstractmethod
    def limit_prices(self, trade_date: date) -> pd.DataFrame:
        """Actual exchange daily up/down limits, preferably pre-open published."""
        ...

    @abstractmethod
    def opening_auction(self, trade_date: date) -> pd.DataFrame:
        """Historical opening-auction summary used for replay."""
        ...

    @abstractmethod
    def stock_minute(
        self, ts_code: str, start: datetime, end: datetime, freq: str = "1min"
    ) -> pd.DataFrame: ...
