import pandas as pd

from logic_b.models import FillModel
from logic_b.replay.runner import B0ReplayRunner
from logic_b.storage import LocalParquetStore


DATES=["20260924","20260925","20260928","20260929"]


def write(store,dataset,key,df):
    store.write_frame(dataset,key,df)


def empty_limit():
    return pd.DataFrame(columns=["trade_date","ts_code","tag"])


def empty_prices():
    return pd.DataFrame(columns=["trade_date","ts_code","pre_close","up_limit","down_limit"])


def test_b0_replay_enters_and_exits_t_plus_one(tmp_path):
    s=LocalParquetStore(tmp_path/"data")

    # Daily/limit-price frames are required every replay day.
    for d in DATES:
        write(s,"daily",d,pd.DataFrame(columns=["ts_code","close","pct_chg"]))
        write(s,"limit_prices",d,empty_prices())
        write(s,"limit_up",d,empty_limit())
        write(s,"limit_down",d,empty_limit())
        write(s,"limit_break",d,empty_limit())
        write(s,"stock_st",d,pd.DataFrame(columns=["ts_code","trade_date","type"]))
        write(s,"suspend",d,pd.DataFrame(columns=["ts_code","trade_date","suspend_type"]))

    # D1's limit-up is used only to calculate D2's previous-limit premium.
    write(s,"limit_up","20260924",pd.DataFrame({
        "trade_date":["20260924"],"ts_code":["P"],"tag":["首板"]
    }))
    write(s,"daily","20260925",pd.DataFrame({
        "ts_code":["P"],"close":[10.2],"pct_chg":[2.0]
    }))

    # A is the D2 high-board candidate for D3.
    write(s,"limit_up","20260925",pd.DataFrame({
        "trade_date":["20260925"],
        "ts_code":["A"],
        "tag":["4天4板"],
        "turnover":[1.2e9],
        "turnover_rate":[15.0],
        "open_num":[1],
        "lu_limit_order":[8e7],
    }))
    write(s,"kpl_limit_up","20260925",pd.DataFrame({
        "trade_date":["20260925"],
        "ts_code":["A"],
        "theme":["机器人"],
        "status":["4连板"],
        "amount":[1.2e9],
    }))

    write(s,"daily","20260928",pd.DataFrame({
        "ts_code":["A"],"close":[11.0],"pct_chg":[7.0]
    }))
    write(s,"limit_prices","20260928",pd.DataFrame({
        "trade_date":["20260928"],"ts_code":["A"],
        "pre_close":[10.0],"up_limit":[11.0],"down_limit":[9.0]
    }))
    d3bars=pd.DataFrame({
        "trade_time":[
            "2026-09-28 09:31:00","2026-09-28 09:32:00",
            "2026-09-28 09:33:00","2026-09-28 09:34:00",
            "2026-09-28 09:35:00","2026-09-28 09:36:00",
        ],
        "open":[10.4,10.5,10.6,10.65,10.7,10.8],
        "high":[10.5,10.6,10.7,10.75,10.8,10.9],
        "low":[10.3,10.4,10.5,10.55,10.6,10.7],
        "close":[10.45,10.55,10.65,10.7,10.75,10.85],
        "vol":[1000,1000,1000,1000,1000,2000],
        "amount":[1e6,1e6,1e6,1e6,3e6,5e6],
    })
    write(s,"minute_1m","20260928/A",d3bars)

    # Next day E0 exit from 09:35; actual fill occurs on next bar.
    write(s,"daily","20260929",pd.DataFrame({
        "ts_code":["A"],"close":[11.3],"pct_chg":[2.7]
    }))
    write(s,"limit_prices","20260929",pd.DataFrame({
        "trade_date":["20260929"],"ts_code":["A"],
        "pre_close":[11.0],"up_limit":[12.1],"down_limit":[9.9]
    }))
    d4bars=pd.DataFrame({
        "trade_time":["2026-09-29 09:35:00","2026-09-29 09:36:00"],
        "open":[11.1,11.2],"high":[11.2,11.3],"low":[11.0,11.1],
        "close":[11.15,11.25],"vol":[2000,3000],"amount":[2e6,3e6],
    })
    write(s,"minute_1m","20260929/A",d4bars)

    runner=B0ReplayRunner(s,fill_model=FillModel.REALISTIC,initial_cash=100000)
    result=runner.run(DATES)

    assert len(result.trades)==1
    assert result.trades[0]["ts_code"]=="A"
    assert result.trades[0]["entry_time"]==pd.Timestamp("2026-09-28 09:36:00")
    assert result.trades[0]["exit_time"]==pd.Timestamp("2026-09-29 09:36:00")
    assert result.trades[0]["net_return"]>0
    assert result.metrics["closed_trades"]==1
    assert result.metrics["buy_attempts"]==1
    assert result.metrics["sell_attempts"]==1
    assert result.metrics["unfilled_buy_rate"]==0.0
    assert result.metrics["unfilled_sell_rate"]==0.0
    assert result.signals[0].evidence["theme_data_available"]
    assert result.signals[0].evidence["st_exclusion_enabled"]
