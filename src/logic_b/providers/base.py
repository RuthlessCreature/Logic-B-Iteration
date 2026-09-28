from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
import pandas as pd


class MarketDataProvider(ABC):
    """Provider contract. Returned frames must contain only requested historical data."""

    @abstractmethod
    def trade_calendar(self, start: date, end: date) -> pd.DataFrame: ...

    @abstractmethod
    def limit_list(self, trade_date: date, limit_type: str = "涨停池") -> pd.DataFrame: ...

    @abstractmethod
    def daily(self, trade_date: date) -> pd.DataFrame: ...

    @abstractmethod
    def stock_minute(
        self, ts_code: str, start: datetime, end: datetime, freq: str = "1min"
    ) -> pd.DataFrame: ...
