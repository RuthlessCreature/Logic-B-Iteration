from datetime import date,datetime

import pandas as pd

from logic_b.diagnostics import preflight_provider
from logic_b.providers.base import MarketDataProvider


class HealthyProvider(MarketDataProvider):
    def trade_calendar(self,start: date,end: date) -> pd.DataFrame:
        return pd.DataFrame({"cal_date":["20260925"]})

    def limit_list(
        self,
        trade_date: date,
        limit_type: str="涨停池",
    ) -> pd.DataFrame:
        return pd.DataFrame({"ts_code":["A"]})

    def theme_limit_list(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code":["A"],
            "theme":["机器人"],
        })

    def daily(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code":["A"],
            "close":[10.0],
        })

    def limit_prices(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code":["A"],
            "up_limit":[11.0],
            "down_limit":[9.0],
        })

    def opening_auction(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code":["A"],
            "close":[10.1],
        })

    def st_status(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame(columns=["ts_code"])

    def stock_minute(
        self,
        ts_code: str,
        start: datetime,
        end: datetime,
        freq: str="1min",
    ) -> pd.DataFrame:
        return pd.DataFrame({
            "trade_time":["2026-09-25 09:31:00"],
            "close":[10.1],
        })


class NoMinuteProvider(HealthyProvider):
    def stock_minute(
        self,
        ts_code: str,
        start: datetime,
        end: datetime,
        freq: str="1min",
    ) -> pd.DataFrame:
        return pd.DataFrame()


def test_preflight_checks_full_data_contract():
    result=preflight_provider(
        HealthyProvider(),
        date(2026,9,25),
    )
    assert result["ok"]
    names={
        item["name"]
        for item in result["checks"]
    }
    assert {
        "trade_calendar",
        "daily",
        "limit_list_ths",
        "kpl_list",
        "stk_limit",
        "stk_auction_o",
        "stock_st",
        "stock_minute_1m",
    }<=names


def test_preflight_fails_when_minute_data_is_unavailable():
    result=preflight_provider(
        NoMinuteProvider(),
        date(2026,9,25),
        sample_code="A",
    )
    assert not result["ok"]
    assert "stock_minute_1m" in result["failed"]
