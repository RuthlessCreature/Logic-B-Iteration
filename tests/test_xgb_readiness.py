import pandas as pd

from logic_b.storage import LocalParquetStore
from logic_b.xgb_readiness import assess_xgb_candidate_readiness


DATES=["20260925","20260928"]


def _write_day_skeleton(store,day):
    for dataset,columns in {
        "limit_down":["ts_code"],
        "limit_break":["ts_code"],
        "theme_limit_up":[
            "ts_code","theme","status"
        ],
        "market_indicator":["trade_date"],
        "daily":[
            "ts_code","close"
        ],
        "limit_prices":[
            "ts_code","pre_close",
            "up_limit","down_limit"
        ],
        "suspend":[
            "ts_code","suspend_type"
        ],
        "stock_st":["ts_code"],
    }.items():
        store.write_frame(
            dataset,
            day,
            pd.DataFrame(
                columns=columns
            ),
        )


def _build_store(tmp_path,with_minute):
    store=LocalParquetStore(
        tmp_path/"data"
    )
    for day in DATES:
        _write_day_skeleton(
            store,
            day,
        )

    store.write_frame(
        "limit_up",
        "20260925",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "name":["示例股份"],
        }),
    )
    store.write_frame(
        "limit_up",
        "20260928",
        pd.DataFrame(
            columns=["ts_code","name"]
        ),
    )
    store.write_frame(
        "daily",
        "20260928",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "close":[10.2],
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

    if with_minute:
        store.write_frame(
            "minute_1m",
            "20260928/600000.SH",
            pd.DataFrame({
                "trade_time":[
                    "2026-09-28 09:36:00"
                ],
                "open":[10.1],
                "high":[10.3],
                "low":[10.0],
                "close":[10.2],
                "vol":[1000],
                "amount":[10200],
            }),
        )
    return store


def test_xgb_candidate_slice_ready_when_complete(tmp_path):
    store=_build_store(
        tmp_path,
        with_minute=True,
    )
    report=assess_xgb_candidate_readiness(
        store=store,
        trade_dates=DATES,
        include_boards=(
            "main",
            "chinext",
            "star",
        ),
        exclude_st=True,
        exclude_no_limit_ipo_days=True,
    )
    assert report.ready
    assert (
        report.candidate_symbol_days_expected
        ==1
    )
    assert report.minute_partitions_missing==0


def test_xgb_readiness_names_missing_candidate_minute(tmp_path):
    store=_build_store(
        tmp_path,
        with_minute=False,
    )
    report=assess_xgb_candidate_readiness(
        store=store,
        trade_dates=DATES,
        include_boards=(
            "main",
            "chinext",
            "star",
        ),
        exclude_st=True,
        exclude_no_limit_ipo_days=True,
    )
    assert not report.ready
    assert report.missing_minutes==[
        "20260928/600000.SH"
    ]
