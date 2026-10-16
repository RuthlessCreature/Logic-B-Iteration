"""H02 Stage-0: persist *independent* BaoStock historical daily status.

Data are historical EOD reference observations, not 09:35 signals.
This module intentionally writes `h02_reference_daily`, never replacing
canonical `daily`, `limit_prices`, `stock_st` or `suspend` partitions.
Official daily price-limit and point-in-time publication certification
remain separate mandatory gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from .h02_independent_daily import H02IndependentDataInvalid, normalize_baostock_daily
from .storage import LocalParquetStore


FIELDS = ("date,code,open,high,low,close,preclose,volume,amount,"
          "adjustflag,tradestatus,isST")
PROVENANCE = "baostock_historical_daily_unadjusted"


class DailyQuery(Protocol):
    error_code: str
    error_msg: str
    fields: list[str]
    def next(self) -> bool: ...
    def get_row_data(self) -> list[str]: ...


class DailyBackend(Protocol):
    def query_history_k_data_plus(self, code: str, fields: str, *,
                                  start_date: str, end_date: str,
                                  frequency: str, adjustflag: str) -> DailyQuery: ...


def _bs_code(ts_code: str) -> str:
    value = str(ts_code).upper()
    if len(value) != 9 or value[6] != "." or not value[:6].isdigit() or value[7:] not in ("SH", "SZ"):
        raise H02IndependentDataInvalid(f"invalid security code: {ts_code}")
    return value[-2:].lower() + "." + value[:6]


@dataclass(frozen=True)
class H02ReferenceCoverage:
    days: int
    expected_symbol_days: int
    observed_symbol_days: int
    absent_symbol_days: int
    st_symbol_days: int
    suspended_symbol_days: int
    failed_symbols: tuple[str, ...]
    data_source: str = PROVENANCE
    official_price_limits_available: bool = False
    intraday_publication_certified: bool = False
    equity_backtest_ready: bool = False

    def as_dict(self) -> dict:
        return {
            "days": self.days,
            "expected_symbol_days": self.expected_symbol_days,
            "observed_symbol_days": self.observed_symbol_days,
            "absent_symbol_days": self.absent_symbol_days,
            "st_symbol_days": self.st_symbol_days,
            "suspended_symbol_days": self.suspended_symbol_days,
            "failed_symbols": list(self.failed_symbols),
            "source": self.data_source,
            "official_price_limits_available": self.official_price_limits_available,
            "intraday_publication_certified": self.intraday_publication_certified,
            "equity_backtest_ready": self.equity_backtest_ready,
        }


def expected_previous_limitup_candidates(
    store: LocalParquetStore, trade_dates: list[str],
) -> dict[str, set[str]]:
    """D only comes from D-1 pool. The first date is warmup only."""
    if len(trade_dates) < 2 or trade_dates != sorted(set(trade_dates)):
        raise H02IndependentDataInvalid("expected >=2 unique chronological exchange sessions")
    if any(len(day) != 8 or not day.isdigit() for day in trade_dates):
        raise H02IndependentDataInvalid("dates must be YYYYMMDD")
    if trade_dates[-1] > "20260630":
        raise H02IndependentDataInvalid("holdout date rejected before data requests")
    wanted: dict[str, set[str]] = {}
    for before, day in zip(trade_dates, trade_dates[1:]):
        if not store.exists("limit_up", before) or not store.verify("limit_up", before):
            raise H02IndependentDataInvalid(f"missing/invalid previous pool: {before}")
        prior = store.read_frame("limit_up", before)
        if prior.empty:
            wanted[day] = set()
            continue
        if "ts_code" not in prior or prior["ts_code"].isna().any() or prior.ts_code.duplicated().any():
            raise H02IndependentDataInvalid(f"invalid prior symbols: {before}")
        codes = set(prior.ts_code.astype(str))
        for code in codes:
            _bs_code(code)
        wanted[day] = codes
    return wanted


def collect_h02_reference_daily(
    store: LocalParquetStore, backend: DailyBackend, trade_dates: list[str],
) -> H02ReferenceCoverage:
    needed = expected_previous_limitup_candidates(store, trade_dates)
    by_symbol: dict[str, set[str]] = {}
    for day, symbols in needed.items():
        for symbol in symbols:
            by_symbol.setdefault(symbol, set()).add(day)

    rows_by_day = {day: [] for day in needed}
    failures = []
    for symbol, days in sorted(by_symbol.items()):
        request = backend.query_history_k_data_plus(
            _bs_code(symbol), FIELDS,
            start_date=pd.to_datetime(min(days)).strftime("%Y-%m-%d"),
            end_date=pd.to_datetime(max(days)).strftime("%Y-%m-%d"),
            frequency="d", adjustflag="3",
        )
        if str(request.error_code) != "0":
            failures.append(symbol)
            continue
        observed = set()
        while request.next():
            raw = dict(zip(request.fields, request.get_row_data()))
            record = normalize_baostock_daily(raw)
            day = record["trade_date"]
            if record["ts_code"] != symbol:
                raise H02IndependentDataInvalid(f"unexpected symbol from provider: {symbol}")
            if day not in days:
                # Provider may return unrelated dates from the query window.
                # Those dates must not enter the research output.
                continue
            if day in observed:
                raise H02IndependentDataInvalid(f"duplicate historical daily: {day}/{symbol}")
            observed.add(day)
            rows_by_day[day].append(record)

    seen = 0
    st = 0
    suspended = 0
    for day in sorted(needed):
        frame = pd.DataFrame(rows_by_day[day])
        if frame.empty:
            frame = pd.DataFrame(columns=[
                "trade_date","ts_code","is_st","is_trading","preclose",
                "open","high","low","close","volume_shares","turnover_cny",
                "source","intraday_publication_audited","official_limit_prices_provided"
            ])
        else:
            frame = frame.sort_values("ts_code").reset_index(drop=True)
            if frame.ts_code.duplicated().any():
                raise H02IndependentDataInvalid(f"duplicate symbols on {day}")
            seen += len(frame)
            st += int(frame.is_st.sum())
            suspended += int((~frame.is_trading).sum())
        store.write_frame(
            "h02_reference_daily", day, frame,
            metadata={
                "source": PROVENANCE,
                "purpose": "independent EOD reference status and OHLC only",
                "time_gate": "not_09_35_certified",
                "official_limit_prices": False,
                "needed_candidates": len(needed[day]),
                "returned_candidates": len(frame),
            },
        )

    expected = sum(len(v) for v in needed.values())
    if seen > expected:
        raise H02IndependentDataInvalid("excess matched reference rows")
    return H02ReferenceCoverage(
        days=len(needed), expected_symbol_days=expected,
        observed_symbol_days=seen, absent_symbol_days=expected-seen,
        st_symbol_days=st, suspended_symbol_days=suspended,
        failed_symbols=tuple(sorted(failures)),
    )
