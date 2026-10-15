"""Fail-closed on BaoStock volume-less 5m and unsettled ex-right reference prices."""
from pathlib import Path
import json

from logic_b.replay import replay

CONFIG = json.loads(Path("config/research.json").read_text(encoding="utf-8"))


def snap(d, price=10, candidate=False, *, preclose=None, volume=12000, tradestatus=1):
    data = {
        "date": d,
        "limit_up": [{"symbol":"600001.SH","limit_up_days":1}] if candidate else [],
        "daily": {"600001.SH": {"close":price,"preclose":preclose,"tradestatus":tradestatus,"is_st":False}},
        "bars_5m": {"600001.SH": [{"time":"09:45","open":price,"high":price,"low":price,"close":price,"volume":volume}]}
    }
    return data


def test_zero_volume_cannot_fill():
    r = replay({"days":[snap("2020-01-02",candidate=True),
                        snap("2020-01-03",volume=0)]}, CONFIG)
    assert r["fills"] == []
    assert r["orders"][0]["reason"] == "ZERO_VOLUME_BAR"


def test_missing_trade_status_cannot_fill():
    r = replay({"days":[snap("2020-01-02",candidate=True),
                        snap("2020-01-03",tradestatus=None)]}, CONFIG)
    assert r["fills"] == []
    assert r["orders"][0]["reason"] == "TRADE_STATUS_UNKNOWN"


def test_corporate_action_price_ref_is_not_a_trading_profit():
    # Yesterday closes at CNY 10, today the unadjusted equity reference is CNY 5.
    # Without quantity/cash corporate action accounting, a fall to 5 must not
    # become an observed tradable 50% crash or fictitious limit-down fill.
    r = replay({"days":[snap("2020-01-02",candidate=True),
                        snap("2020-01-03",price=5,preclose=5)]}, CONFIG)
    assert not r["fills"]
    assert r["orders"][0]["reason"] == "CORPORATE_ACTION_UNRECONCILED"
    assert r["account_unresolved_corporate_actions"][0]["day"] == "2020-01-03"


def test_reference_price_equal_previous_close_keeps_fill():
    r = replay({"days":[snap("2020-01-02",candidate=True),
                        snap("2020-01-03",price=10,preclose=10)]}, CONFIG)
    assert len(r["fills"]) == 1
    assert r["fills"][0]["side"] == "BUY"


def test_unknown_current_still_preserves_identity_but_blocks_fill():
    d = snap("2020-01-03")
    d["daily"]["600001.SH"]["is_st"] = None
    r = replay({"days":[snap("2020-01-02",candidate=True),d]}, CONFIG)
    assert r["orders"][0]["reason"] == "LIMIT_BAND_UNKNOWN"
