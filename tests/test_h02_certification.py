import pandas as pd
import pytest

from logic_b.h02_certification import inspect_h02_executable_provenance
from logic_b.storage import LocalParquetStore


def fixture_store(tmp_path, *, status_source="TushareProvider", limit_source="TushareProvider"):
    store=LocalParquetStore(tmp_path)
    d0,d1="20200102","20200103"
    store.write_frame("limit_up",d0,pd.DataFrame({"ts_code":["000998.SZ"]}),metadata={"source":"xuangubao"})
    for day in [d0,d1]:
        store.write_frame("limit_prices",day,pd.DataFrame({
            "ts_code":["000998.SZ"],"up_limit":[11.0],"down_limit":[9.0]
        }),metadata={"source":limit_source})
        store.write_frame("stock_st",day,pd.DataFrame(columns=["ts_code"]),metadata={"source":status_source})
        store.write_frame("suspend",day,pd.DataFrame(columns=["ts_code"]),metadata={"source":status_source})
    store.write_frame("minute_1m","20200103/000998.SZ",
        pd.DataFrame({"trade_time":[pd.Timestamp("2020-01-03 09:34"),pd.Timestamp("2020-01-03 09:35")]})
        ,metadata={"source":"xuangubao"})
    return store


def test_attested_h02_data_gate_can_pass_source_readiness(tmp_path):
    store=fixture_store(tmp_path)
    r=inspect_h02_executable_provenance(store,["20200102","20200103"])
    assert r["status"]=="READY_FOR_FURTHER_EXECUTION_AUDIT"
    assert r["candidate_symbol_days"]==1
    assert r["minute_date_verified_symbol_days"]==1
    assert r["source_provenance_gate_passed"] is True
    assert r["net_equity_validated"] is False


def test_inferred_price_st_and_halt_block_promotion_even_if_minute_data_present(tmp_path):
    store=fixture_store(tmp_path,status_source="xuangubao_prior_name_inference",
                        limit_source="xuangubao_derived")
    r=inspect_h02_executable_provenance(store,["20200102","20200103"])
    assert r["status"]=="BLOCKED_UNCERTIFIED_EXECUTION_INPUTS"
    assert r["candidate_official_limit_rows_missing"]==1
    assert r["source_provenance_gate_passed"] is False


def test_missing_one_minute_partition_blocks_replay(tmp_path):
    store=fixture_store(tmp_path)
    store.frame_path("minute_1m","20200103/000998.SZ").unlink()
    r=inspect_h02_executable_provenance(store,["20200102","20200103"])
    assert r["status"]=="BLOCKED_UNCERTIFIED_EXECUTION_INPUTS"
    assert r["minute_date_verified_symbol_days"]==0


def test_original_blind_holdout_remains_locked(tmp_path):
    with pytest.raises(ValueError,match="holdout"):
        inspect_h02_executable_provenance(LocalParquetStore(tmp_path),["20260630","20260701"])
