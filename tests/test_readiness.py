import pandas as pd

from logic_b.ingest import HistoricalIngestor
from logic_b.readiness import assess_data_readiness
from logic_b.storage import LocalParquetStore


DATES=["20260925","20260928"]


def empty_frame(dataset):
    schemas={
        "limit_up":["ts_code","tag"],
        "limit_down":["ts_code","tag"],
        "limit_break":["ts_code","tag"],
        "kpl_limit_up":["ts_code","theme","status"],
        "daily":["ts_code","open","high","low","close","pct_chg"],
        "limit_prices":["ts_code","pre_close","up_limit","down_limit"],
        "auction":["ts_code","close"],
        "stock_st":["ts_code","type"],
        "suspend":["ts_code","suspend_type"],
    }
    return pd.DataFrame(columns=schemas[dataset])


def seed_daily(store):
    for day in DATES:
        for dataset in HistoricalIngestor.DAILY_DATASETS:
            store.write_frame(
                dataset,
                day,
                empty_frame(dataset),
            )

    store.write_frame(
        "limit_up",
        "20260925",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "tag":["首板"],
        }),
    )
    store.write_frame(
        "daily",
        "20260928",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "open":[10.2],
            "high":[10.8],
            "low":[10.1],
            "close":[10.6],
            "pct_chg":[6.0],
        }),
    )
    store.write_frame(
        "limit_prices",
        "20260928",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "pre_close":[10.0],
            "up_limit":[11.0],
            "down_limit":[9.0],
        }),
    )


def test_readiness_reports_missing_candidate_minutes(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    seed_daily(store)

    report=assess_data_readiness(
        store=store,
        trade_dates=DATES,
        include_boards=("main","chinext","star"),
        exclude_st=True,
        exclude_no_limit_ipo_days=True,
    )

    assert not report.ready
    assert report.daily_partitions_missing==0
    assert report.minute_partitions_expected==1
    assert report.minute_partitions_missing==1
    assert report.missing_minutes==[
        "20260928/600000.SH"
    ]


def test_readiness_passes_after_minute_partition_exists(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    seed_daily(store)
    store.write_frame(
        "minute_1m",
        "20260928/600000.SH",
        pd.DataFrame({
            "trade_time":["2026-09-28 09:36:00"],
            "open":[10.5],
            "high":[10.6],
            "low":[10.4],
            "close":[10.55],
            "vol":[1000],
        }),
    )

    report=assess_data_readiness(
        store=store,
        trade_dates=DATES,
        include_boards=("main","chinext","star"),
        exclude_st=True,
        exclude_no_limit_ipo_days=True,
    )

    assert report.ready
    assert report.minute_partitions_missing==0
    assert report.manifest_failures==0
