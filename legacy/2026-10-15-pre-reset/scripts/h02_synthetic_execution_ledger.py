"""Replay synthetic execution edge cases through the frozen B0 runner."""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from logic_b.costs import TradingCosts
from logic_b.execution import simulate_buy_fill
from logic_b.models import FillModel
from logic_b.portfolio import Portfolio
from logic_b.replay.runner import B0ReplayRunner
from logic_b.storage import LocalParquetStore
from logic_b.replay.checkpoint import build_minute_checkpoint

DAYS = ["20990104", "20990105", "20990106", "20990107", "20990108", "20990111", "20990112"]
CORE = "SYN-A"
ALTERNATIVE = "SYN-B"


def _empty(dataset: str) -> pd.DataFrame:
    cols = {
        "daily": ["trade_date", "ts_code", "close", "pct_chg"],
        "limit_prices": ["trade_date", "ts_code", "pre_close", "up_limit", "down_limit"],
        "limit_up": ["trade_date", "ts_code", "tag", "turnover", "turnover_rate", "open_num", "lu_limit_order"],
        "limit_down": ["trade_date", "ts_code", "tag"],
        "limit_break": ["trade_date", "ts_code", "tag"],
        "stock_st": ["trade_date", "ts_code", "type"],
        "suspend": ["trade_date", "ts_code", "suspend_type"],
    }
    return pd.DataFrame(columns=cols[dataset])


def _minute(day: str, prices: tuple[float, float, float], *, sealed: bool = False, strong_checkpoint: bool = False) -> pd.DataFrame:
    pre, up, _ = prices
    if sealed:
        vals = [(up, up, up, up, 2000)]
        vals = vals * 6
    else:
        vals = [(pre * 1.02, pre * 1.03, pre * 1.01, pre * 1.025, 1000)] * 5
        if strong_checkpoint:
            vals[4] = (10.85, up, 10.75, 10.9, 3000)
        vals.append((min(up, pre * 1.04), min(up, pre * 1.05), pre * 1.03, min(up, pre * 1.045), 2000))
    rows = []
    for minute, (open_, high, low, close, vol) in zip(range(31, 37), vals):
        rows.append({"trade_time": f"{day[:4]}-{day[4:6]}-{day[6:]} 09:{minute:02}:00", "open": open_, "high": high,
            "low": low, "close": close, "vol": vol, "amount": vol * close})
    return pd.DataFrame(rows)


def _locked_down_minute(day: str, down: float) -> pd.DataFrame:
    return pd.DataFrame([{"trade_time": f"{day[:4]}-{day[4:6]}-{day[6:]} 09:{minute:02}:00", "open": down,
        "high": down, "low": down, "close": down, "vol": 2000, "amount": down*2000} for minute in range(31, 37)])


def make_store(root: Path, scenario: str) -> LocalParquetStore:
    if scenario not in {"sealed_priority_no_fallback", "t1_locked_suspended_resume", "multi_day_locked_resume", "exit_before_new_candidate", "insufficient_cash"}:
        raise ValueError(f"unknown synthetic scenario: {scenario}")
    store = LocalParquetStore(root)
    for day in DAYS:
        for dataset in ("daily", "limit_prices", "limit_up", "limit_down", "limit_break", "stock_st", "suspend"):
            store.write_frame(dataset, day, _empty(dataset), metadata={"classification": "SYNTHETIC_ONLY", "scenario": scenario})
    # D-2 is needed only to calculate the prior-up median return in D-1 regime.
    store.write_frame("limit_up", DAYS[0], pd.DataFrame({"trade_date": [DAYS[0]], "ts_code": ["SYN-PREV"], "tag": ["首板"]}))
    store.write_frame("daily", DAYS[1], pd.DataFrame({"trade_date": [DAYS[1]], "ts_code": ["SYN-PREV"], "close": [10.2], "pct_chg": [2.0]}))
    candidate_rows = [{"trade_date": DAYS[1], "ts_code": CORE, "tag": "6天6板", "turnover": 1.2e9, "turnover_rate": 15.0, "open_num": 1, "lu_limit_order": 8e7},
        {"trade_date": DAYS[1], "ts_code": ALTERNATIVE, "tag": "5天5板", "turnover": 9e8, "turnover_rate": 13.0, "open_num": 1, "lu_limit_order": 6e7}]
    for i in range(58):
        candidate_rows.append({"trade_date": DAYS[1], "ts_code": f"SYN-{i:02}", "tag": "首板", "turnover": 1e7, "turnover_rate": 2.0, "open_num": 0, "lu_limit_order": 1e6})
    store.write_frame("limit_up", DAYS[1], pd.DataFrame(candidate_rows))
    store.write_frame("daily", DAYS[1], pd.DataFrame({"trade_date": [DAYS[1]], "ts_code": ["SYN-PREV"], "close": [10.2], "pct_chg": [2.0]}))
    entry_prices = pd.DataFrame([
        {"trade_date": DAYS[2], "ts_code": CORE, "pre_close": 10.0, "up_limit": 11.0, "down_limit": 9.0},
        {"trade_date": DAYS[2], "ts_code": ALTERNATIVE, "pre_close": 10.0, "up_limit": 11.0, "down_limit": 9.0},
    ])
    store.write_frame("limit_prices", DAYS[2], entry_prices)
    store.write_frame("daily", DAYS[2], pd.DataFrame({"trade_date": [DAYS[2]]*2, "ts_code": [CORE, ALTERNATIVE], "close": [10.9, 10.4], "pct_chg": [9.0, 4.0]}))
    core_bars = _minute(DAYS[2], (10.0, 11.0, 9.0), strong_checkpoint=True)
    if scenario == "sealed_priority_no_fallback":
        # Checkpoint gates pass, then the leader seals before the first eligible fill bar.
        core_bars.loc[core_bars.index[-1], ["open", "high", "low", "close"]] = 11.0
    store.write_frame("minute_1m", f"{DAYS[2]}/{CORE}", core_bars)
    store.write_frame("minute_1m", f"{DAYS[2]}/{ALTERNATIVE}", _minute(DAYS[2], (10.0, 11.0, 9.0)))
    if scenario == "exit_before_new_candidate":
        store.write_frame("limit_up", DAYS[2], pd.DataFrame({"trade_date": [DAYS[2]], "ts_code": [ALTERNATIVE], "tag": ["5天5板"], "turnover": [9e8], "turnover_rate": [13.0], "open_num": [1], "lu_limit_order": [6e7]}))
        store.write_frame("daily", DAYS[3], pd.DataFrame({"trade_date": [DAYS[3]]*2, "ts_code": [CORE, ALTERNATIVE], "close": [10.8, 10.5], "pct_chg": [-1.0, 1.0]}))
        store.write_frame("limit_prices", DAYS[3], pd.DataFrame({"trade_date": [DAYS[3]]*2, "ts_code": [CORE, ALTERNATIVE], "pre_close": [10.9, 10.4], "up_limit": [11.99, 11.44], "down_limit": [9.81, 9.36]}))
        store.write_frame("minute_1m", f"{DAYS[3]}/{CORE}", _minute(DAYS[3], (10.9, 11.99, 9.81)))
        store.write_frame("minute_1m", f"{DAYS[3]}/{ALTERNATIVE}", _minute(DAYS[3], (10.4, 11.44, 9.36), strong_checkpoint=True))
    if scenario == "t1_locked_suspended_resume":
        # First eligible exit session is locked at the synthetic lower limit.
        store.write_frame("daily", DAYS[3], pd.DataFrame({"trade_date": [DAYS[3]], "ts_code": [CORE], "close": [9.9], "pct_chg": [-10.0]}))
        store.write_frame("limit_prices", DAYS[3], pd.DataFrame({"trade_date": [DAYS[3]], "ts_code": [CORE], "pre_close": [11.0], "up_limit": [12.1], "down_limit": [9.9]}))
        store.write_frame("minute_1m", f"{DAYS[3]}/{CORE}", _locked_down_minute(DAYS[3], 9.9))
        store.write_frame("daily", DAYS[4], _empty("daily"))
        store.write_frame("suspend", DAYS[4], pd.DataFrame({"trade_date": [DAYS[4]], "ts_code": [CORE], "suspend_type": ["synthetic"]}))
        store.write_frame("daily", DAYS[5], pd.DataFrame({"trade_date": [DAYS[5]], "ts_code": [CORE], "close": [10.2], "pct_chg": [3.0]}))
        store.write_frame("limit_prices", DAYS[5], pd.DataFrame({"trade_date": [DAYS[5]], "ts_code": [CORE], "pre_close": [9.9], "up_limit": [10.89], "down_limit": [8.91]}))
        store.write_frame("minute_1m", f"{DAYS[5]}/{CORE}", _minute(DAYS[5], (9.9, 10.89, 8.91)))
    if scenario == "multi_day_locked_resume":
        for index in (3, 4):
            day = DAYS[index]
            pre = 11.0 if index == 3 else 9.9
            down = 9.9 if index == 3 else 8.91
            store.write_frame("daily", day, pd.DataFrame({"trade_date": [day], "ts_code": [CORE], "close": [down], "pct_chg": [-10.0]}))
            store.write_frame("limit_prices", day, pd.DataFrame({"trade_date": [day], "ts_code": [CORE], "pre_close": [pre], "up_limit": [pre*1.1], "down_limit": [down]}))
            store.write_frame("minute_1m", f"{day}/{CORE}", _locked_down_minute(day, down))
        store.write_frame("daily", DAYS[5], _empty("daily"))
        store.write_frame("suspend", DAYS[5], pd.DataFrame({"trade_date": [DAYS[5]], "ts_code": [CORE], "suspend_type": ["synthetic"]}))
        store.write_frame("daily", DAYS[6], pd.DataFrame({"trade_date": [DAYS[6]], "ts_code": [CORE], "close": [10.2], "pct_chg": [3.0]}))
        store.write_frame("limit_prices", DAYS[6], pd.DataFrame({"trade_date": [DAYS[6]], "ts_code": [CORE], "pre_close": [8.91], "up_limit": [9.801], "down_limit": [8.019]}))
        store.write_frame("minute_1m", f"{DAYS[6]}/{CORE}", _minute(DAYS[6], (8.91, 9.801, 8.019)))
    return store


def _fill_record(fill) -> dict[str, Any]:
    return {"symbol": fill.ts_code, "side": fill.side, "signal_time": str(fill.signal_time),
        "fill_time": None if fill.fill_time is None else str(fill.fill_time), "fill_price": fill.fill_price,
        "filled": fill.filled, "reason": fill.reason, "model": fill.model.value, "synthetic_only": True}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _execution_input_scenarios() -> dict[str, Any]:
    signal = datetime(2099, 1, 6, 9, 35)
    openable = {"trade_time": "2099-01-06 09:36:00", "open": 10.0, "high": 10.2, "low": 9.9, "close": 10.1, "vol": 1000}
    no_fill = {}
    for name, frame in (("missing_minutes", pd.DataFrame()),
                        ("zero_volume", pd.DataFrame([{**openable, "vol": 0}])),
                        ("checkpoint_only", pd.DataFrame([{**openable, "trade_time": "2099-01-06 09:35:00"}]))):
        result = simulate_buy_fill(ts_code="SYN-X", signal_time=signal, minute_bars=frame, limit_up_price=11.0, model=FillModel.REALISTIC)
        no_fill[name] = {"filled": result.filled, "reason": result.reason, "synthetic_only": True}
    invalid = {
        "nan_price": [{**openable, "open": float("nan")}],
        "infinite_limit_price": [openable],
        "zero_price": [{**openable, "close": 0.0}],
        "negative_volume": [{**openable, "vol": -1}],
        "inconsistent_ohlc": [{**openable, "high": 9.0}],
        "invalid_timestamp": [{**openable, "trade_time": "not-a-time"}],
        "duplicate_timestamp": [openable, openable],
        "out_of_order_timestamp": [openable, {**openable, "trade_time": "2099-01-06 09:35:00"}],
    }
    failures = {}
    for name, rows in invalid.items():
        try:
            simulate_buy_fill(ts_code="SYN-X", signal_time=signal, minute_bars=pd.DataFrame(rows), limit_up_price=float("inf") if name == "infinite_limit_price" else 11.0, model=FillModel.REALISTIC)
        except (TypeError, ValueError) as exc:
            failures[name] = {"rejected": True, "exception": type(exc).__name__, "synthetic_only": True}
        else:
            failures[name] = {"rejected": False, "synthetic_only": True}
    return {"classification": "SYNTHETIC_ONLY", "no_fill_cases": no_fill, "invalid_inputs": failures}


def run_scenario(root: Path, scenario: str) -> dict[str, Any]:
    store = make_store(root, scenario)
    initial_cash = 100.0 if scenario == "insufficient_cash" else 100_000.0
    runner = B0ReplayRunner(store, fill_model=FillModel.REALISTIC, initial_cash=initial_cash)
    result = runner.run(DAYS)
    costs = runner.costs
    trade = result.trades[0] if result.trades else None
    ledger = {"scenario": scenario, "classification": "SYNTHETIC_MECHANICS_ONLY_NO_REAL_MARKET_EVIDENCE",
        "strategy_version": "B0-P.1 (frozen)", "fill_model": "realistic", "checkpoint": "09:35 inclusive for signal; fills must occur strictly after checkpoint",
        "dates": DAYS, "initial_cash": initial_cash, "fills": [_fill_record(x) for x in result.fills],
        "signals": [{"date": s.trade_date, "action": s.action.value, "symbol": s.ts_code,
            "gate": s.evidence.get("gate"), "winner_before_gate": s.evidence.get("winner_before_gate"),
            "candidate_count_after_filters": s.evidence.get("candidate_count_after_filters")} for s in result.signals],
        "trades": [], "equity": result.daily_equity, "metrics": result.metrics}
    if trade:
        buy_gross = trade["shares"] * trade["entry_price"]
        sell_gross = trade["shares"] * trade["exit_price"]
        buy_fees = {"commission": costs.commission(buy_gross), "transfer_fee": costs.transfer_fee(buy_gross), "stamp_duty": 0.0}
        sell_fees = {"commission": costs.commission(sell_gross), "transfer_fee": costs.transfer_fee(sell_gross), "stamp_duty": sell_gross * costs.stamp_rate}
        net_proceeds = sell_gross - sum(sell_fees.values())
        ledger["trades"].append({"symbol": trade["ts_code"], "shares": trade["shares"], "round_lot": trade["shares"] % 100 == 0,
            "entry_time": str(trade["entry_time"]), "entry_price": trade["entry_price"], "buy_gross": buy_gross,
            "buy_fee_lines": buy_fees, "cash_after_buy": initial_cash - buy_gross - sum(buy_fees.values()),
            "exit_time": str(trade["exit_time"]), "exit_price": trade["exit_price"], "sell_gross": sell_gross,
            "sell_fee_lines": sell_fees, "cash_after_exit": initial_cash - buy_gross - sum(buy_fees.values()) + net_proceeds,
            "net_return_after_modelled_fees": trade["net_return"], "t_plus_one_compliant": trade["exit_time"].date() > trade["entry_time"].date()})
    ledger["daily_order_attempts"] = []
    if result.fills:
        fills_frame = pd.DataFrame([{"date": str(f.signal_time.date()), "side": f.side} for f in result.fills])
        for day, group in fills_frame.groupby("date", sort=True):
            ledger["daily_order_attempts"].append({"date": day, "buy_attempts": int((group.side == "BUY").sum()), "sell_attempts": int((group.side == "SELL").sum())})
    if scenario == "exit_before_new_candidate":
        candidate_codes = store.read_frame("limit_up", DAYS[2])["ts_code"].astype(str).tolist()
        minute = {code: store.read_frame("minute_1m", f"{DAYS[3]}/{code}") for code in candidate_codes}
        checkpoint = build_minute_checkpoint(candidate_codes, minute, store.read_frame("limit_prices", DAYS[3]), datetime.strptime(f"{DAYS[3]} 09:35:00", "%Y%m%d %H:%M:%S"))
        ledger["pre_exit_candidate_checkpoint"] = {"candidate_codes": candidate_codes, "checkpoint_codes": checkpoint.ts_code.astype(str).tolist() if not checkpoint.empty else [], "all_evidence_is_synthetic": True}
    return ledger


def build_report(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    sealed = run_scenario(root / "sealed", "sealed_priority_no_fallback")
    lifecycle = run_scenario(root / "lifecycle", "t1_locked_suspended_resume")
    multi_lock = run_scenario(root / "multi-lock", "multi_day_locked_resume")
    sell_before_buy = run_scenario(root / "sell-before-buy", "exit_before_new_candidate")
    insufficient_cash = run_scenario(root / "insufficient-cash", "insufficient_cash")
    costs = TradingCosts()
    exact_cash = 100 * 123.45 + costs.buy_cost(100 * 123.45)
    boundary = Portfolio(initial_cash=exact_cash, costs=costs)
    bought = boundary.buy_all("SYN-BOUNDARY", pd.Timestamp("2099-01-06 09:36").to_pydatetime(), 123.45)
    next_lot_cost = 100 * 123.45 + costs.buy_cost(200 * 123.45) - costs.buy_cost(100 * 123.45)
    lifecycle_trade = lifecycle["trades"][0]
    full_next_lot = 100 * lifecycle_trade["entry_price"] + costs.buy_cost((lifecycle_trade["shares"] + 100) * lifecycle_trade["entry_price"]) - costs.buy_cost(lifecycle_trade["shares"] * lifecycle_trade["entry_price"])
    boundary_evidence = {"classification": "SYNTHETIC_ONLY", "cash_too_small": {"initial_cash": insufficient_cash["initial_cash"], "fills": insufficient_cash["fills"], "position": insufficient_cash["metrics"]["ending_position"], "ending_cash": insufficient_cash["equity"][-1]["cash"]},
        "exact_one_lot_after_fees": {"initial_cash": exact_cash, "shares": bought.shares, "cash_remaining": boundary.cash, "next_lot_incremental_cost": next_lot_cost, "cannot_afford_next_lot": boundary.cash < next_lot_cost},
        "full_account_max_affordable_lot_check": {"initial_cash": lifecycle_trade["cash_after_buy"] + lifecycle_trade["buy_gross"] + sum(lifecycle_trade["buy_fee_lines"].values()),
            "shares": lifecycle_trade["shares"], "cash_after_buy": lifecycle_trade["cash_after_buy"], "next_100_share_incremental_cost": full_next_lot,
            "cannot_afford_next_lot": lifecycle_trade["cash_after_buy"] < full_next_lot}}
    return {"classification": "SYNTHETIC_MECHANICS_ONLY_NO_REAL_MARKET_EVIDENCE", "frozen_b0_config_modified": False,
        "protected_data_accessed": False, "scenarios": {"sealed_priority_no_fallback": sealed, "t1_locked_suspended_resume": lifecycle,
            "multi_day_locked_resume": multi_lock, "exit_before_new_candidate": sell_before_buy, "insufficient_cash": insufficient_cash},
        "account_boundary_checks": boundary_evidence,
        "execution_input_scenarios": _execution_input_scenarios(),
        "cost_parameters": {"commission_rate": .0003, "minimum_commission": 5.0, "transfer_fee_rate": .00001, "sell_stamp_rate": .0005},
        "semantics": ["All inputs, symbols and 2099 dates are synthetic fixtures.", "B0-P.1 and its configured thresholds/cost logic are not changed.",
            "The ledger verifies code mechanics only; it is not real-data evidence of fills, profit or execution edge."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-markdown", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="h02-synthetic-ledger-") as tmp:
        report = build_report(Path(tmp))
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    report = _json_safe(report)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8")
    sealed = report["scenarios"]["sealed_priority_no_fallback"]
    lifecycle = report["scenarios"]["t1_locked_suspended_resume"]
    lines = ["# H02 synthetic execution mechanics ledger", "", "**Synthetic only. This is not historical trading or fill evidence.**", "",
        f"B0 version: `{sealed['strategy_version']}`; configured B0 thresholds and `config/b0.yaml` unchanged.", "",
        "## Locked-up priority candidate and no fallback", "",
        f"Signal: `{sealed['signals'][0]['symbol']}`; selected buy attempt: `{sealed['fills'][0]['symbol']}` / `{sealed['fills'][0]['reason']}`. No alternative buy attempt was made.", "",
        "## T+1, locked lower limit, suspension, resumed exit", "",
        "The lifecycle scenario records the next-session locked-limit sell rejection, a suspension-blocked sell, and a later post-09:35 exit. Additional scenarios cover two consecutive locked sessions, a same-day old-position exit that suppresses an otherwise eligible replacement, insufficient cash, and exact maximum round-lot sizing after fees. The report records daily buy/sell attempt caps.", "",
        "Missing/zero-volume/checkpoint-only bars do not fill. Non-finite/non-positive prices or official limits, negative volume, inconsistent OHLC, and invalid/duplicate/out-of-order timestamps are rejected before any fill. Costs are calculated from the same `TradingCosts` instance used by the replay runner.", "",
        "No row refers to an actual security or market date. The scenario has no evidentiary weight for realized returns, execution probability or net expectancy.", ""]
    args.out_markdown.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": report["classification"], "sealed_fills": sealed["fills"], "lifecycle_fills": lifecycle["fills"], "trades": lifecycle["trades"]}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
