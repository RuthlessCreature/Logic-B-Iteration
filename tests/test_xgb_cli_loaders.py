import pandas as pd

from logic_b.cli import _xgb_pre_close_for_symbol_day
from logic_b.storage import LocalParquetStore


def test_xgb_preclose_prefers_current_limit_price(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    store.write_frame(
        "limit_prices",
        "20260928",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "pre_close":[10.5],
            "up_limit":[11.55],
            "down_limit":[9.45],
        }),
    )
    store.write_frame(
        "daily",
        "20260925",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "close":[9.9],
        }),
    )

    value=_xgb_pre_close_for_symbol_day(
        store=store,
        trade_dates=["20260925","20260928"],
        day_key="20260928",
        code="600000.SH",
    )
    assert value==10.5


def test_xgb_preclose_falls_back_to_previous_daily_close(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    store.write_frame(
        "daily",
        "20260925",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "close":[9.9],
        }),
    )

    value=_xgb_pre_close_for_symbol_day(
        store=store,
        trade_dates=["20260925","20260928"],
        day_key="20260928",
        code="600000.SH",
    )
    assert value==9.9


def test_xgb_preclose_falls_back_to_prior_pool_price(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    store.write_frame(
        "limit_up",
        "20260925",
        pd.DataFrame({
            "ts_code":["600000.SH"],
            "price":[10.0],
        }),
    )

    value=_xgb_pre_close_for_symbol_day(
        store=store,
        trade_dates=["20260925","20260928"],
        day_key="20260928",
        code="600000.SH",
    )
    assert value==10.0
