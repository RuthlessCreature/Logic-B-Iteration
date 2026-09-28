from datetime import date
import pandas as pd

from logic_b.cli import _calendar_dates
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
