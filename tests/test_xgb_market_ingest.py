from datetime import date

import pandas as pd

from logic_b.providers.xuangubao_market import XuangubaoMinuteDay
from logic_b.storage import LocalParquetStore
from logic_b.xgb_market_ingest import XuangubaoMarketIngestor


class FakeMarketProvider:
    def __init__(self):
        self.calls=[]

    def historical_minute_day(
        self,
        ts_code,
        trade_date,
        *,
        pre_close_override=None,
    ):
        self.calls.append(
            (ts_code,trade_date,pre_close_override)
        )
        bars=pd.DataFrame({
            "trade_time":[
                pd.Timestamp(
                    f"{trade_date} 09:31:00"
                ),
                pd.Timestamp(
                    f"{trade_date} 09:36:00"
                ),
            ],
            "open":[10.0,10.2],
            "high":[10.3,10.4],
            "low":[9.9,10.1],
            "close":[10.2,10.3],
            "vol":[1000,1200],
            "amount":[10000,12360],
            "avg_price":[10.1,10.25],
        })
        return XuangubaoMinuteDay(
            ts_code=ts_code,
            trade_date=trade_date.strftime("%Y%m%d"),
            bars=bars,
            pre_close=pre_close_override,
            pre_close_source="override",
            raw_lines=len(bars),
        )

    @staticmethod
    def daily_from_minute(minute_day):
        bars=minute_day.bars
        return pd.DataFrame([{
            "trade_date":minute_day.trade_date,
            "ts_code":minute_day.ts_code,
            "open":float(bars.iloc[0]["open"]),
            "high":float(bars["high"].max()),
            "low":float(bars["low"].min()),
            "close":float(bars.iloc[-1]["close"]),
            "vol":float(bars["vol"].sum()),
            "amount":float(bars["amount"].sum()),
            "pct_chg":3.0,
            "source":"fake",
        }])

    @staticmethod
    def limit_prices(minute_day):
        pre=float(minute_day.pre_close)
        return pd.DataFrame([{
            "trade_date":minute_day.trade_date,
            "ts_code":minute_day.ts_code,
            "pre_close":pre,
            "up_limit":round(pre*1.1,2),
            "down_limit":round(pre*0.9,2),
            "source":"fake",
        }])


def test_cached_dataframes_return_without_truth_value_error(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    provider=FakeMarketProvider()
    ingestor=XuangubaoMarketIngestor(
        provider,
        store,
    )

    store.write_frame(
        "minute_1m",
        "20260928/600000.SH",
        pd.DataFrame({
            "trade_time":[
                "2026-09-28 09:36:00"
            ],
            "open":[10.0],
            "high":[10.1],
            "low":[9.9],
            "close":[10.0],
            "vol":[100],
            "amount":[1000],
        }),
    )
    store.write_frame(
        "daily",
        "20260928",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "close":[10.0],
        }),
    )
    store.write_frame(
        "limit_prices",
        "20260928",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "pre_close":[9.8],
            "up_limit":[10.78],
            "down_limit":[8.82],
        }),
    )

    result=ingestor.materialize_symbol_day(
        trade_date=date(2026,9,28),
        ts_code="600000.SH",
        pre_close=9.8,
    )

    assert len(result["daily"])==1
    assert len(result["limit_prices"])==1
    assert provider.calls==[]


def test_materialize_range_uses_prior_limit_up_price_as_preclose(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    provider=FakeMarketProvider()
    ingestor=XuangubaoMarketIngestor(
        provider,
        store,
    )

    store.write_frame(
        "limit_up",
        "20260925",
        pd.DataFrame({
            "ts_code":[
                "600000.SH",
                "000001.SZ",
            ],
            "price":[10.0,20.0],
        }),
    )

    summary=ingestor.materialize_range(
        trade_dates=[
            "20260925",
            "20260928",
        ]
    )

    assert summary["candidate_symbol_days"]==2
    assert store.exists(
        "minute_1m",
        "20260928/600000.SH",
    )
    assert store.exists(
        "minute_1m",
        "20260928/000001.SZ",
    )
    assert (
        "600000.SH",
        date(2026,9,28),
        10.0,
    ) in provider.calls
    assert (
        "000001.SZ",
        date(2026,9,28),
        20.0,
    ) in provider.calls


def test_range_materializes_empty_suspend_and_prior_name_st_state(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    provider=FakeMarketProvider()
    ingestor=XuangubaoMarketIngestor(
        provider,
        store,
    )

    store.write_frame(
        "limit_up",
        "20260925",
        pd.DataFrame({
            "ts_code":[
                "600000.SH",
                "000001.SZ",
            ],
            "name":[
                "普通股份",
                "*ST示例",
            ],
            "price":[10.0,20.0],
        }),
    )

    ingestor.materialize_range(
        trade_dates=[
            "20260925",
            "20260928",
        ]
    )

    suspend=store.read_frame(
        "suspend",
        "20260928",
    )
    stock_st=store.read_frame(
        "stock_st",
        "20260928",
    )

    assert suspend.empty
    assert stock_st["ts_code"].tolist()==[
        "000001.SZ"
    ]
    assert (
        stock_st.iloc[0]["source"]
        =="xuangubao_prior_name_inference"
    )
