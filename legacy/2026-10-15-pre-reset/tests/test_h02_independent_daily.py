import pandas as pd
import pytest

from logic_b.h02_independent_daily import (
    H02IndependentDataInvalid,normalize_baostock_daily,
    compare_daily_to_historical_minutes
)

def raw(**kw):
    a=dict(date="2020-01-03",code="sh.600421",adjustflag="3",
           tradestatus="1",isST="1",preclose="8.57",open="8.80",
           high="9.00",low="8.58",close="8.79",volume="1000",amount="8790")
    a.update(kw)
    return a


def test_historical_st_is_not_normal_limit():
    row=normalize_baostock_daily(raw())
    assert row["ts_code"]=="600421.SH"
    assert row["is_st"] is True
    assert row["official_limit_prices_provided"] is False
    assert row["intraday_publication_audited"] is False


def test_reject_any_adjusted_daily_as_raw_replay():
    with pytest.raises(H02IndependentDataInvalid,match="adjustflag"):
        normalize_baostock_daily(raw(adjustflag="2"))


def test_unknown_st_and_trade_status_fail_closed():
    with pytest.raises(H02IndependentDataInvalid,match="ST"):
        normalize_baostock_daily(raw(isST=""))
    with pytest.raises(H02IndependentDataInvalid,match="ST"):
        normalize_baostock_daily(raw(tradestatus=""))


def test_minute_vs_daily_comparison_does_not_claim_fill():
    row=normalize_baostock_daily(raw())
    bars=pd.DataFrame({
        "trade_time":[pd.Timestamp("2020-01-03 09:31"),pd.Timestamp("2020-01-03 15:00")],
        "open":[8.80,8.79],"high":[9.00,8.79],
        "low":[8.58,8.79],"close":[8.80,8.79],
    })
    report=compare_daily_to_historical_minutes(row,bars)
    assert report["status"]=="MATCH_TICK_TOLERANCE"
    assert report["st_filter_needed"] is True
    assert report["proves_entry_fill"] is False


def test_duplicate_bar_time_blocks_comparison():
    row=normalize_baostock_daily(raw())
    b=pd.DataFrame({"trade_time":[pd.Timestamp("2020-01-03 09:31")]*2,
                    "open":[8.8,8.8],"high":[9,9],"low":[8.58,8.58],"close":[8.79,8.79]})
    assert compare_daily_to_historical_minutes(row,b)["status"]=="BLOCKED_TIME_INCONSISTENCY"
