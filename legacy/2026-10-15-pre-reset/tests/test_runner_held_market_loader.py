from datetime import datetime

import pandas as pd

from logic_b.models import FillModel
from logic_b.replay.runner import B0ReplayRunner
from logic_b.storage import LocalParquetStore


DATES=["20260924","20260925","20260928","20260929"]


def write(store,dataset,key,frame):
    store.write_frame(dataset,key,frame)


def empty_limit():
    return pd.DataFrame(columns=["trade_date","ts_code","tag"])


def empty_daily():
    return pd.DataFrame(columns=["ts_code","close","pct_chg"])


def empty_prices():
    return pd.DataFrame(columns=[
        "trade_date","ts_code","pre_close","up_limit","down_limit"
    ])


def seed_common_day_state(store):
    for d in DATES:
        write(store,"daily",d,empty_daily())
        write(store,"limit_prices",d,empty_prices())
        write(store,"limit_up",d,empty_limit())
        write(store,"limit_down",d,empty_limit())
        write(store,"limit_break",d,empty_limit())
        write(
            store,
            "stock_st",
            d,
            pd.DataFrame(columns=["ts_code","trade_date","type"]),
        )
        write(
            store,
            "suspend",
            d,
            pd.DataFrame(columns=["ts_code","trade_date","suspend_type"]),
        )


def test_held_symbol_day_is_loaded_before_next_day_exit(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    seed_common_day_state(store)

    # D-2 pool exists only to construct D-1 market regime.
    write(
        store,
        "limit_up",
        "20260924",
        pd.DataFrame({
            "trade_date":["20260924"],
            "ts_code":["P"],
            "tag":["首板"],
        }),
    )
    write(
        store,
        "daily",
        "20260925",
        pd.DataFrame({
            "ts_code":["P"],
            "close":[10.2],
            "pct_chg":[2.0],
        }),
    )

    # A is a D-1 high-board core and is bought on D.
    write(
        store,
        "limit_up",
        "20260925",
        pd.DataFrame({
            "trade_date":["20260925"],
            "ts_code":["A"],
            "tag":["4天4板"],
            "turnover":[1.2e9],
            "turnover_rate":[15.0],
            "open_num":[1],
            "lu_limit_order":[8e7],
        }),
    )
    write(
        store,
        "kpl_limit_up",
        "20260925",
        pd.DataFrame({
            "trade_date":["20260925"],
            "ts_code":["A"],
            "theme":["机器人"],
            "status":["4连板"],
            "amount":[1.2e9],
        }),
    )
    write(
        store,
        "daily",
        "20260928",
        pd.DataFrame({
            "ts_code":["A"],
            "close":[11.0],
            "pct_chg":[7.0],
        }),
    )
    write(
        store,
        "limit_prices",
        "20260928",
        pd.DataFrame({
            "trade_date":["20260928"],
            "ts_code":["A"],
            "pre_close":[10.0],
            "up_limit":[11.0],
            "down_limit":[9.0],
        }),
    )
    write(
        store,
        "minute_1m",
        "20260928/A",
        pd.DataFrame({
            "trade_time":[
                "2026-09-28 09:31:00",
                "2026-09-28 09:32:00",
                "2026-09-28 09:33:00",
                "2026-09-28 09:34:00",
                "2026-09-28 09:35:00",
                "2026-09-28 09:36:00",
            ],
            "open":[10.4,10.5,10.6,10.65,10.7,10.8],
            "high":[10.5,10.6,10.7,10.75,10.8,10.9],
            "low":[10.3,10.4,10.5,10.55,10.6,10.7],
            "close":[10.45,10.55,10.65,10.7,10.75,10.85],
            "vol":[1000,1000,1000,1000,1000,2000],
            "amount":[1e6,1e6,1e6,1e6,3e6,5e6],
        }),
    )

    calls=[]

    def market_loader(day_key,code):
        calls.append((day_key,code))
        assert day_key=="20260929"
        assert code=="A"

        write(
            store,
            "daily",
            day_key,
            pd.DataFrame({
                "ts_code":["A"],
                "close":[11.3],
                "pct_chg":[2.7],
            }),
        )
        write(
            store,
            "limit_prices",
            day_key,
            pd.DataFrame({
                "trade_date":[day_key],
                "ts_code":["A"],
                "pre_close":[11.0],
                "up_limit":[12.1],
                "down_limit":[9.9],
            }),
        )
        write(
            store,
            "minute_1m",
            f"{day_key}/A",
            pd.DataFrame({
                "trade_time":[
                    "2026-09-29 09:35:00",
                    "2026-09-29 09:36:00",
                ],
                "open":[11.1,11.2],
                "high":[11.2,11.3],
                "low":[11.0,11.1],
                "close":[11.15,11.25],
                "vol":[2000,3000],
                "amount":[2e6,3e6],
            }),
        )
        return {
            "daily":store.read_frame("daily",day_key),
            "limit_prices":store.read_frame("limit_prices",day_key),
            "minute_1m":store.read_frame("minute_1m",f"{day_key}/A"),
        }

    runner=B0ReplayRunner(
        store,
        fill_model=FillModel.REALISTIC,
        initial_cash=100000,
        market_loader=market_loader,
    )
    result=runner.run(DATES)

    assert calls==[("20260929","A")]
    assert len(result.trades)==1
    assert result.trades[0]["ts_code"]=="A"
    assert result.trades[0]["exit_time"]==pd.Timestamp(
        "2026-09-29 09:36:00"
    )
    assert result.metrics["closed_trades"]==1
