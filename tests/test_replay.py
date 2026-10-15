import copy
import json
from pathlib import Path

import pytest

from logic_b.identity import canonical_code
from logic_b.fees import compute_fees
from logic_b.replay import replay, _band


CONFIG = json.loads(Path("config/research.json").read_text(encoding="utf-8"))


def day(d, symbol="600001.SH", px=10, *, st=False, cand=False, exec_px=None, tradestatus=1):
    return {"date": d,
            "limit_up": [{"symbol": symbol, "limit_up_days": 1, "break_limit_up_times": 0}] if cand else [],
            "market": {"market_temperature": 50},
            "daily": {symbol: {"close": px, "is_st": st, "tradestatus": tradestatus}},
            "bars_5m": {symbol: [{"time": "09:45", "open": exec_px if exec_px is not None else px,
                                  "high": exec_px if exec_px is not None else px,
                                  "low": exec_px if exec_px is not None else px,
                                  "close": exec_px if exec_px is not None else px, "volume": 1000}]}}


def test_symbol_does_not_change_with_st_name():
    assert canonical_code("sh.600001") == canonical_code("600001.SS") == "600001.SH"
    assert canonical_code("sz.000001") == "000001.SZ"
    assert _band("600001.SH", "2022-01-01", True) == .05
    assert _band("600001.SH", "2022-01-01", False) == .1
    with pytest.raises(ValueError):
        canonical_code("600001")


def test_fee_minimum_and_timeline():
    assert compute_fees(9800, "BUY", "2024-01-02").commission == 5
    assert compute_fees(9800, "SELL", "2023-01-02").stamp == 9.8
    assert compute_fees(9800, "SELL", "2024-01-02").stamp == 4.9
    assert compute_fees(10000, "BUY", "2021-01-01").transfer == .2
    assert compute_fees(10000, "BUY", "2023-01-01").transfer == .1


def test_entry_exit_full_account_one_lot_and_T_plus_one():
    data = {"days": [day("2020-01-02", cand=True), day("2020-01-03", px=10.2),
                     day("2020-01-06", px=10.3)], "coverage_complete": False}
    r = replay(data, CONFIG)
    assert len(r["fills"]) == 2
    buy, sell = r["fills"]
    assert buy["side"] == "BUY" and buy["day"] == "2020-01-03"
    assert buy["shares"] == 900
    assert sell["side"] == "SELL" and sell["day"] == "2020-01-06"
    assert r["final_equity"] > 10000
    assert r["status"] == "PARTIAL"
    assert all(x["day"] <= "2026-06-30" for x in r["orders"])


def test_limit_up_no_buy_and_no_fallback():
    d = day("2020-01-02", cand=True)
    d["limit_up"].append({"symbol": "000001.SZ", "limit_up_days": 0})
    r = replay({"days": [d, day("2020-01-03", px=11)]}, CONFIG)
    assert not r["fills"]
    assert any(o.get("reason") == "NO_FILL_LIMIT_UP" for o in r["orders"])


def test_limit_down_sell_remains_held_across_days():
    data = [day("2020-01-02", cand=True), day("2020-01-03", px=10),
            day("2020-01-06", px=9.0), day("2020-01-07", px=9.3)]
    # Third day has 10% limit down: from 10 to 9, sell blocked. Next day can sell.
    r = replay({"days": data}, CONFIG)
    assert any(x["reason"] == "NO_FILL_LIMIT_DOWN" for x in r["orders"])
    assert r["daily_equity"][2]["symbol"] == "600001.SH"
    assert r["daily_equity"][3]["symbol"] is None


def test_st_is_dated_attribute_not_identity():
    data = [day("2020-01-02", cand=True, st=True), day("2020-01-03", px=10.1, st=True)]
    result = replay({"days": data}, CONFIG)
    assert result["fills"][0]["symbol"] == "600001.SH"
    data[1]["daily"]["600001.SH"]["is_st"] = False
    result2 = replay({"days": data}, CONFIG)
    assert result2["orders"][0]["reason"] == "ST_STATUS_CHANGE_NEEDS_PRICE_LIMIT"


def test_future_data_refused():
    data = {"days": [day("2020-01-02"), day("2026-07-01")]}
    with pytest.raises(ValueError, match="outside-range"):
        replay(data, CONFIG)


def test_no_same_day_sell_and_bad_bar_rejected():
    a = day("2020-01-02", cand=True)
    b = day("2020-01-03")
    b["bars_5m"]["600001.SH"][0]["time"] = "09:35"
    r = replay({"days": [a, b]}, CONFIG)
    assert not r["fills"]
    assert r["orders"][0]["reason"] == "NO_COMPLETED_EXECUTION_BAR"


def test_not_look_ahead_into_current_pool():
    x = day("2020-01-02", cand=False)
    y = day("2020-01-03", cand=True)
    r = replay({"days": [x, y]}, CONFIG)
    assert all(o.get("side") != "BUY" for o in r["orders"])


def test_insufficient_cash_for_lot_does_not_borrow():
    a = day("2020-01-02", px=999, cand=True)
    b = day("2020-01-03", px=999)
    r = replay({"days": [a, b]}, CONFIG)
    assert any(x["reason"] == "INSUFFICIENT_CASH_FOR_100_SHARES" for x in r["orders"])
    assert r["final_equity"] == 10000


def test_invalid_dates_duplicate_rejected():
    a = day("2020-01-02")
    with pytest.raises(ValueError, match="sorted and unique"):
        replay({"days": [a, copy.deepcopy(a)]}, CONFIG)
