import pandas as pd
import pytest

from logic_b.storage import LocalParquetStore
from logic_b.h02_baostock_ingest import (
    FIELDS, collect_h02_reference_daily, expected_previous_limitup_candidates,
)
from logic_b.h02_independent_daily import H02IndependentDataInvalid


class FakeQuery:
    error_code = "0"
    error_msg = "success"
    fields = FIELDS.split(",")

    def __init__(self, rows):
        self.rows = rows
        self.pos = 0

    def next(self):
        if self.pos >= len(self.rows):
            return False
        self.pos += 1
        return True

    def get_row_data(self):
        return [str(self.rows[self.pos - 1].get(col, "")) for col in self.fields]


class FakeBackend:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query_history_k_data_plus(
        self, code, fields, *, start_date, end_date, frequency, adjustflag,
    ):
        self.calls.append((code, start_date, end_date, frequency, adjustflag))
        assert fields == FIELDS
        assert frequency == "d" and adjustflag == "3"
        return FakeQuery([
            row for row in self.rows if row["code"] == code
            and start_date <= row["date"] <= end_date
        ])


def sample(date, code="sz.000998", **kwargs):
    row = {
        "date": date, "code": code, "adjustflag": "3",
        "tradestatus": "1", "isST": "0",
        "open": "10.1", "high": "11", "low": "10", "close": "10.6",
        "preclose": "10", "volume": "6000", "amount": "63000",
    }
    row.update(kwargs)
    return row


def source(tmp_path):
    store = LocalParquetStore(tmp_path)
    store.write_frame("limit_up", "20200102", pd.DataFrame({
        "ts_code": ["000998.SZ", "600421.SH"]
    }))
    store.write_frame("limit_up", "20200103", pd.DataFrame({
        "ts_code": ["000998.SZ"]
    }))
    return store


def test_candidate_window_derived_only_from_previous_day(tmp_path):
    store = source(tmp_path)
    got = expected_previous_limitup_candidates(
        store, ["20200102", "20200103", "20200106"],
    )
    assert got["20200103"] == {"000998.SZ", "600421.SH"}
    assert got["20200106"] == {"000998.SZ"}


def test_realistic_status_ingestion_writes_only_separate_reference_partitions(tmp_path):
    store = source(tmp_path)
    backend = FakeBackend([
        sample("2020-01-03"),
        sample("2020-01-06", isST="1"),
        sample("2020-01-03", code="sh.600421", isST="1"),
    ])
    report = collect_h02_reference_daily(
        store, backend, ["20200102", "20200103", "20200106"],
    )
    assert report.expected_symbol_days == 3
    assert report.observed_symbol_days == 3
    assert report.absent_symbol_days == 0
    assert report.st_symbol_days == 2
    assert report.equity_backtest_ready is False
    assert len(backend.calls) == 2  # batch per symbol, not one call per trade-day
    assert store.verify("h02_reference_daily", "20200103")
    assert store.verify("h02_reference_daily", "20200106")
    assert not store.exists("stock_st", "20200103")
    assert not store.exists("limit_prices", "20200103")
    assert store.read_frame("h02_reference_daily", "20200106").iloc[0]["is_st"]


def test_source_rows_missing_are_visible_not_synthetic_negative_status(tmp_path):
    store = source(tmp_path)
    backend = FakeBackend([sample("2020-01-03")])
    report = collect_h02_reference_daily(
        store, backend, ["20200102", "20200103", "20200106"],
    )
    assert report.observed_symbol_days == 1
    assert report.absent_symbol_days == 2
    assert store.read_frame("h02_reference_daily", "20200106").empty


def test_future_and_broken_previous_pool_block_before_query(tmp_path):
    store = source(tmp_path)
    backend = FakeBackend([])
    with pytest.raises(H02IndependentDataInvalid, match="holdout"):
        collect_h02_reference_daily(
            store, backend, ["20260630", "20260701"],
        )
    assert not backend.calls
    store.manifest_path("limit_up", "20200102").unlink()
    with pytest.raises(H02IndependentDataInvalid, match="previous pool"):
        collect_h02_reference_daily(
            store, backend, ["20200102", "20200103"],
        )


def test_unknown_st_values_are_never_filled_as_false(tmp_path):
    store = source(tmp_path)
    backend = FakeBackend([sample("2020-01-03", isST="")])
    with pytest.raises(H02IndependentDataInvalid, match="ST"):
        collect_h02_reference_daily(
            store, backend, ["20200102", "20200103"],
        )


def test_duplicate_status_from_provider_fails_closed(tmp_path):
    store = source(tmp_path)
    backend = FakeBackend([sample("2020-01-03"), sample("2020-01-03")])
    with pytest.raises(H02IndependentDataInvalid, match="duplicate"):
        collect_h02_reference_daily(
            store, backend, ["20200102", "20200103"],
        )
