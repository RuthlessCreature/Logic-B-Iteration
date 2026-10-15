from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("h02_synthetic_execution_ledger", ROOT / "scripts" / "h02_synthetic_execution_ledger.py")
assert SPEC and SPEC.loader
LEDGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEDGER)


def test_locked_priority_candidate_does_not_fallback(tmp_path):
    result = LEDGER.run_scenario(tmp_path / "sealed", "sealed_priority_no_fallback")
    assert result["signals"][0]["symbol"] == "SYN-A"
    assert result["fills"] == [{
        "symbol": "SYN-A", "side": "BUY", "signal_time": "2099-01-06 09:35:00",
        "fill_time": None, "fill_price": None, "filled": False,
        "reason": "sealed_limit_no_open", "model": "realistic", "synthetic_only": True,
    }]
    assert result["metrics"]["ending_position"] is None
    # SYN-B had openable synthetic bars, but B0 made no replacement attempt.


def test_t1_locked_down_suspension_and_resumed_exit(tmp_path):
    result = LEDGER.run_scenario(tmp_path / "lifecycle", "t1_locked_suspended_resume")
    assert [fill["reason"] for fill in result["fills"]] == [
        "first_openable_post_signal_bar", "locked_limit_down", "suspended", "first_openable_post_signal_bar",
    ]
    trade = result["trades"][0]
    assert trade["round_lot"] is True
    assert trade["shares"] % 100 == 0
    assert trade["t_plus_one_compliant"] is True
    assert trade["entry_time"] == "2099-01-06 09:36:00"
    assert trade["exit_time"] == "2099-01-11 09:36:00"
    assert set(trade["buy_fee_lines"]) == {"commission", "transfer_fee", "stamp_duty"}
    assert set(trade["sell_fee_lines"]) == {"commission", "transfer_fee", "stamp_duty"}
    assert result["metrics"]["suspension_blocks"] == 1


def test_exportable_report_has_no_nonstandard_json_numbers(tmp_path):
    report = LEDGER._json_safe(LEDGER.build_report(tmp_path))
    encoded = json.dumps(report, allow_nan=False)
    assert "SYNTHETIC_MECHANICS_ONLY" in encoded
    assert report["frozen_b0_config_modified"] is False
    assert report["protected_data_accessed"] is False


def test_multiple_locked_sessions_then_resume_and_daily_attempt_limits(tmp_path):
    result = LEDGER.run_scenario(tmp_path / "multi", "multi_day_locked_resume")
    assert [f["reason"] for f in result["fills"]] == [
        "first_openable_post_signal_bar", "locked_limit_down", "locked_limit_down",
        "suspended", "first_openable_post_signal_bar"]
    assert all(x["buy_attempts"] <= 1 and x["sell_attempts"] <= 1 for x in result["daily_order_attempts"])
    assert result["trades"][0]["t_plus_one_compliant"] is True


def test_sell_after_checkpoint_blocks_same_day_new_buy_even_with_eligible_candidate(tmp_path):
    result = LEDGER.run_scenario(tmp_path / "sell", "exit_before_new_candidate")
    same_day = [f for f in result["fills"] if f["signal_time"].startswith("2099-01-07")]
    assert [f["side"] for f in same_day] == ["SELL"]
    assert result["pre_exit_candidate_checkpoint"]["checkpoint_codes"] == ["SYN-B"]
    assert result["daily_order_attempts"][-1]["buy_attempts"] == 0


def test_insufficient_cash_is_recorded_without_portfolio_mutation(tmp_path):
    result = LEDGER.run_scenario(tmp_path / "cash", "insufficient_cash")
    assert result["fills"][0]["reason"] == "insufficient_cash"
    assert result["metrics"]["ending_position"] is None
    assert result["equity"][-1]["cash"] == result["initial_cash"] == 100.0


def test_full_investment_uses_maximum_affordable_round_lot_after_fees(tmp_path):
    report = LEDGER.build_report(tmp_path)
    exact = report["account_boundary_checks"]["exact_one_lot_after_fees"]
    assert exact["shares"] == 100
    assert exact["cash_remaining"] >= 0
    assert exact["cannot_afford_next_lot"] is True
    assert report["account_boundary_checks"]["full_account_max_affordable_lot_check"]["cannot_afford_next_lot"] is True
    scenarios = report["execution_input_scenarios"]
    assert all(item["rejected"] for item in scenarios["invalid_inputs"].values())
    assert all(not item["filled"] for item in scenarios["no_fill_cases"].values())
