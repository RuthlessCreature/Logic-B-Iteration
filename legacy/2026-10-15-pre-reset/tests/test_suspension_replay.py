import pandas as pd

from logic_b.models import FillModel
from logic_b.replay.runner import B0ReplayRunner
from logic_b.storage import LocalParquetStore


DATES=[
    "20260924",
    "20260925",
    "20260928",
    "20260929",
    "20260930",
]


def write(store,dataset,key,frame):
    store.write_frame(dataset,key,frame)


def empty_limit():
    return pd.DataFrame(columns=[
        "trade_date","ts_code","tag"
    ])


def empty_prices():
    return pd.DataFrame(columns=[
        "trade_date","ts_code",
        "pre_close","up_limit","down_limit",
    ])


def empty_daily():
    return pd.DataFrame(columns=[
        "ts_code","close","pct_chg"
    ])


def empty_st():
    return pd.DataFrame(columns=[
        "trade_date","ts_code","type"
    ])


def empty_suspend():
    return pd.DataFrame(columns=[
        "trade_date","ts_code","suspend_type"
    ])


def test_suspended_position_is_carried_until_resume(tmp_path):
    store=LocalParquetStore(tmp_path/"data")

    for day in DATES:
        write(store,"daily",day,empty_daily())
        write(store,"limit_prices",day,empty_prices())
        write(store,"limit_up",day,empty_limit())
        write(store,"limit_down",day,empty_limit())
        write(store,"limit_break",day,empty_limit())
        write(store,"stock_st",day,empty_st())
        write(store,"suspend",day,empty_suspend())

    write(store,"limit_up","20260924",pd.DataFrame({
        "trade_date":["20260924"],
        "ts_code":["P"],
        "tag":["首板"],
    }))
    write(store,"daily","20260925",pd.DataFrame({
        "ts_code":["P"],
        "close":[10.2],
        "pct_chg":[2.0],
    }))

    write(store,"limit_up","20260925",pd.DataFrame({
        "trade_date":["20260925"],
        "ts_code":["A"],
        "tag":["4天4板"],
        "turnover":[1.2e9],
        "turnover_rate":[15.0],
        "open_num":[1],
        "lu_limit_order":[8e7],
    }))
    write(store,"kpl_limit_up","20260925",pd.DataFrame({
        "trade_date":["20260925"],
        "ts_code":["A"],
        "theme":["机器人"],
        "status":["4连板"],
        "amount":[1.2e9],
    }))

    write(store,"daily","20260928",pd.DataFrame({
        "ts_code":["A"],
        "close":[11.0],
        "pct_chg":[7.0],
    }))
    write(store,"limit_prices","20260928",pd.DataFrame({
        "trade_date":["20260928"],
        "ts_code":["A"],
        "pre_close":[10.0],
        "up_limit":[11.0],
        "down_limit":[9.0],
    }))
    write(store,"minute_1m","20260928/A",pd.DataFrame({
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
    }))

    write(store,"suspend","20260929",pd.DataFrame({
        "trade_date":["20260929"],
        "ts_code":["A"],
        "suspend_type":["S"],
    }))

    write(store,"daily","20260930",pd.DataFrame({
        "ts_code":["A"],
        "close":[11.4],
        "pct_chg":[3.6],
    }))
    write(store,"limit_prices","20260930",pd.DataFrame({
        "trade_date":["20260930"],
        "ts_code":["A"],
        "pre_close":[11.0],
        "up_limit":[12.1],
        "down_limit":[9.9],
    }))
    write(store,"minute_1m","20260930/A",pd.DataFrame({
        "trade_time":[
            "2026-09-30 09:35:00",
            "2026-09-30 09:36:00",
        ],
        "open":[11.2,11.3],
        "high":[11.3,11.4],
        "low":[11.1,11.2],
        "close":[11.25,11.35],
        "vol":[2000,3000],
        "amount":[2e6,3e6],
    }))

    runner=B0ReplayRunner(
        store,
        fill_model=FillModel.REALISTIC,
        initial_cash=100000,
    )
    result=runner.run(DATES)

    assert len(result.trades)==1
    assert result.trades[0]["exit_time"]==pd.Timestamp(
        "2026-09-30 09:36:00"
    )
    suspended_fill=[
        fill
        for fill in result.fills
        if fill.reason=="suspended"
    ]
    assert len(suspended_fill)==1
    day4=[
        row
        for row in result.daily_equity
        if row["date"]=="20260929"
    ][0]
    assert day4["holding"]=="A"
    assert day4["holding_suspended"] is True
    assert day4["mark_price"]==11.0
    assert result.metrics["suspension_blocks"]==1
