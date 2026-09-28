from datetime import datetime
import pandas as pd

from logic_b.replay.checkpoint import build_auction_checkpoint, build_minute_checkpoint


def limits():
    return pd.DataFrame({
        "ts_code":["A","B"],
        "pre_close":[10.0,20.0],
        "up_limit":[11.0,22.0],
        "down_limit":[9.0,18.0],
    })


def test_auction_checkpoint_uses_actual_limit_prices():
    auction=pd.DataFrame({
        "ts_code":["A","B"],
        "close":[11.0,20.4],
        "high":[11.0,20.5],
        "low":[11.0,20.0],
        "amount":[8e7,2e7],
    })
    out=build_auction_checkpoint(["A","B"],auction,limits())
    a=out[out.ts_code=="A"].iloc[0]
    assert a["at_limit"]
    assert a["one_price_limit"]
    assert a["checkpoint_amount_rank"]==1.0


def test_minute_checkpoint_does_not_read_after_checkpoint():
    bars=pd.DataFrame({
        "trade_time":[
            "2026-09-28 09:31:00",
            "2026-09-28 09:35:00",
            "2026-09-28 09:36:00",
        ],
        "open":[10.2,10.4,11.0],
        "high":[10.3,10.5,11.0],
        "low":[10.1,10.3,10.9],
        "close":[10.2,10.5,11.0],
        "amount":[1e6,2e6,100e6],
    })
    out=build_minute_checkpoint(
        ["A"],{"A":bars},limits(),datetime(2026,9,28,9,35)
    )
    a=out.iloc[0]
    assert round(a["pct_from_prev_close"],4)==0.05
    assert a["checkpoint_amount"]==3e6
    assert not a["at_limit"]
