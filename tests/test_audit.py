import pandas as pd

from logic_b.audit import audit_daily_bundle,summarize_issues


def fixtures():
    daily=pd.DataFrame({
        "ts_code":["A","B","C"],
        "open":[10.5,19.0,15.0],
        "high":[11.0,20.0,15.5],
        "low":[10.2,18.0,14.8],
        "close":[11.0,18.0,15.2],
    })
    limits=pd.DataFrame({
        "ts_code":["A","B","C"],
        "pre_close":[10.0,20.0,15.0],
        "up_limit":[11.0,22.0,16.5],
        "down_limit":[9.0,18.0,13.5],
    })
    up=pd.DataFrame({"ts_code":["A"]})
    down=pd.DataFrame({"ts_code":["B"]})
    broken=pd.DataFrame({"ts_code":["C"]})
    return daily,limits,up,down,broken


def test_clean_daily_bundle_has_no_errors():
    daily,limits,up,down,broken=fixtures()
    issues=audit_daily_bundle(
        daily=daily,
        limit_prices=limits,
        limit_up=up,
        limit_down=down,
        limit_break=broken,
    )
    summary=summarize_issues(issues)
    assert summary["errors"]==0


def test_limit_pool_mismatch_is_error():
    daily,limits,up,down,broken=fixtures()
    daily.loc[daily.ts_code=="A","close"]=10.7
    issues=audit_daily_bundle(
        daily=daily,
        limit_prices=limits,
        limit_up=up,
        limit_down=down,
        limit_break=broken,
    )
    codes={x.code for x in issues}
    assert "LIMIT_UP_CLOSE_MISMATCH" in codes


def test_invalid_ohlc_is_error():
    daily,limits,up,down,broken=fixtures()
    daily.loc[daily.ts_code=="C","high"]=14.0
    issues=audit_daily_bundle(
        daily=daily,
        limit_prices=limits,
        limit_up=up,
        limit_down=down,
        limit_break=broken,
    )
    assert any(x.code=="INVALID_OHLC" for x in issues)
