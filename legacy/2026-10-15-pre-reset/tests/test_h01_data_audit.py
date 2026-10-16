"""Market-wide pool vs vendor indicator consistency tests."""
import pandas as pd

from logic_b.h01_data_audit import audit_xgb_limit_up_counts
from logic_b.storage import LocalParquetStore


def _write(tmp_path, pool_size=2, indicator_count=2):
    s=LocalParquetStore(tmp_path)
    day="20250102"
    pool=pd.DataFrame({"ts_code":[f"{i:06d}.SZ" for i in range(pool_size)]})
    snap=pd.DataFrame({
        "timestamp":[1735786800,1735801200],
        "limit_up_count":[0,indicator_count],
    })
    s.write_frame("limit_up",day,pool)
    s.write_frame("market_indicator",day,snap)
    return s,day


def test_counts_match(tmp_path):
    s,day=_write(tmp_path)
    report,detail=audit_xgb_limit_up_counts(s,[day])
    assert report["status"]=="COUNT_CONSISTENT"
    assert detail.status.iloc[0]=="MATCH"


def test_mismatch_is_explicit_and_not_declared_complete(tmp_path):
    s,day=_write(tmp_path,2,4)
    report,detail=audit_xgb_limit_up_counts(s,[day])
    assert report["status"]=="REVIEW_POOL_COUNT_DISCREPANCY"
    assert report["max_abs_difference"]==2
    assert detail.status.iloc[0]=="SOURCE_DEFINITION_REVIEW"


def test_missing_vendor_count_blocks_claim(tmp_path):
    s,day=_write(tmp_path)
    s.write_frame("market_indicator",day,pd.DataFrame({"timestamp":[123]}))
    report,_=audit_xgb_limit_up_counts(s,[day])
    assert report["status"]=="BLOCKED_SOURCE_SUMMARY_MISSING"
