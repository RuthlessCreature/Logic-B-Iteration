"""Market psychology-experience proxy temporal contract synthetic tests."""
import numpy as np
import pandas as pd
import pytest

from logic_b.h01_experience import build_vendor_limitup_experience
from logic_b.h01_activity import H01DataBlocked, limitup_continuation, join_feedback_activity, expanding_window_h01
from logic_b.h01_cli import main
from logic_b.storage import LocalParquetStore


def fixture(tmp_path, n=28):
    root=tmp_path/"data"
    s=LocalParquetStore(root)
    dates=pd.bdate_range("2026-02-02",periods=n)
    keys=dates.strftime("%Y%m%d").tolist()
    s.write_frame("calendar",keys[0]+"_"+keys[-1],pd.DataFrame({"cal_date":keys}))
    for i,day in enumerate(keys):
        s.write_frame("limit_up",day,pd.DataFrame({
            "ts_code":[f"{k:06d}.SZ" for k in range(i%5,i%5+5+i%3)],
            "trade_date":[day]*(5+i%3)
        }))
        s.write_frame("market_indicator",day,pd.DataFrame({
            "timestamp":[1000000000,1000000001],
            "yesterday_limit_up_avg_pcp":[-999, (i%9-4)*1.25],
            "limit_up_count":[0,5+i%3]
        }))
    return s,keys,dates


def test_vendor_feature_excludes_today_and_is_reported_as_raw_proxy(tmp_path):
    store,days,_=fixture(tmp_path)
    a=build_vendor_limitup_experience(store,days,lookback=3)
    assert a.status.iloc[0]=="BLOCKED_INSUFFICIENT_HISTORY"
    assert a.h01_experience_proxy.iloc[3] == pytest.approx(
        np.mean([-5,-3.75,-2.5])
    )
    old=a.h01_experience_proxy.iloc[-1]
    day=days[-1]
    snapshot=store.read_frame("market_indicator",day)
    snapshot.loc[1,"yesterday_limit_up_avg_pcp"]=1000000
    store.write_frame("market_indicator",day,snapshot)
    changed=build_vendor_limitup_experience(store,days,lookback=3)
    assert changed.h01_experience_proxy.iloc[-1]==pytest.approx(old)
    assert not a.actual_cohort_profit.any()


def test_vendor_feature_outcome_forecast_is_time_safe(tmp_path):
    store,days,_=fixture(tmp_path)
    features=build_vendor_limitup_experience(store,days,lookback=3)
    market=limitup_continuation(store,days)
    joined=join_feedback_activity(features,market,"VENDOR_PRIOR_LIMITUP_MARKET_PROXY")
    results,forecast=expanding_window_h01(joined,min_train_days=10,min_test_days=5)
    assert results["test_days"]>=5
    assert len(forecast)==results["test_days"]


def test_vendor_missing_indicator_partitions_block(tmp_path):
    s,days,_=fixture(tmp_path)
    s.frame_path("market_indicator",days[0]).unlink()
    with pytest.raises(H01DataBlocked,match="bad manifest"):
        build_vendor_limitup_experience(s,days)


def test_vendor_mode_cli_smoke(tmp_path):
    s,days,dates=fixture(tmp_path)
    path=tmp_path/"report"
    ret=main([
        "--data-root",str(s.root),"--out",str(path),
        "--start",dates[0].strftime("%Y-%m-%d"),
        "--end",dates[-1].strftime("%Y-%m-%d"),
        "--vendor-market-experience","--min-train","10","--min-test","5"
    ])
    assert ret==0
    import json
    result=json.loads((path/"h01_metrics.json").read_text())
    assert result["cohort_is_actual_investor_pnl"] is False
    assert result["experience_proxy_type"]=="market_yesterday_limitup_performance_raw"
