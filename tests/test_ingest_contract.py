from datetime import date,datetime

import pandas as pd

from logic_b.ingest import HistoricalIngestor
from logic_b.providers.base import MarketDataProvider
from logic_b.storage import LocalParquetStore


class FakeProvider(MarketDataProvider):
    def trade_calendar(self,start: date,end: date) -> pd.DataFrame:
        return pd.DataFrame({"cal_date":["20260925"]})

    def limit_list(
        self,
        trade_date: date,
        limit_type: str="涨停池",
    ) -> pd.DataFrame:
        return pd.DataFrame({
            "trade_date":["20260925"],
            "ts_code":["A"],
            "limit_type":[limit_type],
        })

    def theme_limit_list(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame({
            "trade_date":["20260925"],
            "ts_code":["A"],
            "theme":["机器人"],
            "status":["首板"],
            "amount":[100.0],
        })

    def daily(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame({
            "trade_date":["20260925"],
            "ts_code":["A"],
            "open":[10.0],
            "high":[11.0],
            "low":[9.9],
            "close":[11.0],
        })

    def limit_prices(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame({
            "trade_date":["20260925"],
            "ts_code":["A"],
            "pre_close":[10.0],
            "up_limit":[11.0],
            "down_limit":[9.0],
        })

    def opening_auction(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame({
            "trade_date":["20260925"],
            "ts_code":["A"],
            "close":[10.5],
        })

    def st_status(self,trade_date: date) -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "trade_date","ts_code","type"
        ])

    def stock_minute(
        self,
        ts_code: str,
        start: datetime,
        end: datetime,
        freq: str="1min",
    ) -> pd.DataFrame:
        return pd.DataFrame({
            "trade_time":["2026-09-25 09:36:00"],
            "open":[10.5],
            "high":[10.6],
            "low":[10.4],
            "close":[10.55],
            "vol":[1000],
        })


def test_daily_bundle_persists_point_in_time_contract(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    ingestor=HistoricalIngestor(
        FakeProvider(),
        store,
    )

    bundle=ingestor.fetch_daily_bundle(
        date(2026,9,25)
    )

    assert set(bundle)==set(
        HistoricalIngestor.DAILY_DATASETS
    )
    assert store.exists(
        "kpl_limit_up",
        "20260925",
    )
    assert store.exists(
        "stock_st",
        "20260925",
    )
    assert (
        store.read_frame(
            "kpl_limit_up",
            "20260925",
        ).iloc[0]["theme"]
        =="机器人"
    )
