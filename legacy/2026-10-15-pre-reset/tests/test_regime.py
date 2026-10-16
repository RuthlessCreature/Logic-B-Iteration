import pandas as pd
from logic_b.replay.regime import build_completed_day_regime


def test_completed_day_regime_uses_prior_limit_pool_returns():
    up=pd.DataFrame({"ts_code":["A","B","C"],"tag":["6天6板","2天2板","首板"]})
    down=pd.DataFrame({"ts_code":["D"]})
    broken=pd.DataFrame({"ts_code":["E"]})
    prior=pd.DataFrame({"ts_code":["P1","P2"]})
    daily=pd.DataFrame({
        "ts_code":["P1","P2","OTHER"],
        "pct_chg":[2.0,4.0,-9.0],
    })
    snap=build_completed_day_regime(
        limit_up_df=up,
        limit_down_df=down,
        break_df=broken,
        daily_df=daily,
        prior_day_limit_up_df=prior,
    )
    assert snap.max_height==6
    assert round(snap.prev_limit_median_return,4)==0.03
    assert round(snap.break_rate,4)==0.25
