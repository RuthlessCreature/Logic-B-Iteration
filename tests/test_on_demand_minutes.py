import pandas as pd

from logic_b.replay.runner import B0ReplayRunner
from logic_b.storage import LocalParquetStore


def test_on_demand_minute_loader_persists_and_reuses(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    calls=[]

    def loader(day_key,code):
        calls.append((day_key,code))
        return pd.DataFrame({
            "trade_time":["2026-09-28 09:36:00"],
            "open":[10.0],
            "high":[10.1],
            "low":[9.9],
            "close":[10.05],
            "vol":[1000],
        })

    runner=B0ReplayRunner(
        store,
        minute_loader=loader,
    )

    first=runner._minute("20260928","A")
    second=runner._minute("20260928","A")

    assert len(first)==1
    assert len(second)==1
    assert calls==[("20260928","A")]
    assert store.exists("minute_1m","20260928/A")
