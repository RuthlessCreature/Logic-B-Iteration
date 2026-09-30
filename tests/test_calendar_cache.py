from datetime import date
import pandas as pd

from logic_b.cli import _calendar_dates,_calendar_dates_with_prior
from logic_b.storage import LocalParquetStore


def test_calendar_subrange_can_use_larger_cached_partition(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    store.write_frame(
        "calendar",
        "20240101_20261231",
        pd.DataFrame({"cal_date":["20260924","20260925","20260928","20260929"]}),
    )
    out=_calendar_dates(
        store,
        date(2026,9,25),
        date(2026,9,28),
    )
    assert out==["20260925","20260928"]


def test_calendar_subrange_can_prepend_prior_cached_trading_day(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    store.write_frame(
        "calendar",
        "20241001_20241231",
        pd.DataFrame({
            "cal_date":[
                "20241230",
                "20241231",
            ]
        }),
    )
    store.write_frame(
        "calendar",
        "20250102_20250331",
        pd.DataFrame({
            "cal_date":[
                "20250102",
                "20250103",
            ]
        }),
    )

    out=_calendar_dates_with_prior(
        store,
        date(2025,1,2),
        date(2025,1,3),
        prior_days=1,
    )

    assert out==[
        "20241231",
        "20250102",
        "20250103",
    ]
