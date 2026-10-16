import pandas as pd

from logic_b.models import FillModel
from logic_b.replay.runner import B0ReplayRunner
from logic_b.storage import LocalParquetStore


def write(store,dataset,key,frame):
    store.write_frame(dataset,key,frame)


def test_empty_candidate_pool_without_columns_is_valid_cash_day(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    dates=["20260924","20260925","20260928"]

    for day in dates:
        write(store,"daily",day,pd.DataFrame(columns=[
            "ts_code","close","pct_chg"
        ]))
        write(store,"limit_prices",day,pd.DataFrame(columns=[
            "ts_code","pre_close","up_limit","down_limit"
        ]))
        write(store,"limit_down",day,pd.DataFrame())
        write(store,"limit_break",day,pd.DataFrame())
        write(store,"stock_st",day,pd.DataFrame(columns=["ts_code"]))
        write(store,"suspend",day,pd.DataFrame(columns=["ts_code"]))

    # Deliberately use a zero-column frame to reproduce public-source empty
    # partitions that previously raised KeyError('ts_code').
    write(store,"limit_up","20260924",pd.DataFrame())
    write(store,"limit_up","20260925",pd.DataFrame())
    write(store,"limit_up","20260928",pd.DataFrame())

    runner=B0ReplayRunner(
        store,
        fill_model=FillModel.REALISTIC,
        initial_cash=100000,
        exclude_no_limit_ipo_days=True,
    )
    result=runner.run(dates)

    assert len(result.trades)==0
    assert result.metrics["closed_trades"]==0
    assert result.metrics["ending_position"] is None
    assert result.signals
    assert all(
        signal.ts_code is None
        for signal in result.signals
    )
