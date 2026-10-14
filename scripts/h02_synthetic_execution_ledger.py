"""Replay synthetic execution edge cases through the frozen B0 runner."""
from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from logic_b.costs import TradingCosts
from logic_b.models import FillModel
from logic_b.replay.runner import B0ReplayRunner
from logic_b.storage import LocalParquetStore

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
    if scenario not in {"sealed_priority_no_fallback", "t1_locked_suspended_resume"}:
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


def run_scenario(root: Path, scenario: str) -> dict[str, Any]:
    store = make_store(root, scenario)
    runner = B0ReplayRunner(store, fill_model=FillModel.REALISTIC, initial_cash=100_000.0)
    result = runner.run(DAYS)
    costs = TradingCosts()
    initial_cash = 100_000.0
    trade = result.trades[0] if result.trades else None
    ledger = {"scenario": scenario, "classification": "SYNTHETIC_MECHANICS_ONLY_NO_REAL_MARKET_EVIDENCE",
        "strategy_version": "B0-P.1 (frozen)", "fill_model": "realistic", "checkpoint": "09:35 inclusive for signal; fills must occur strictly after checkpoint",
        "dates": DAYS, "initial_cash": initial_cash, "fills": [_fill_record(x) for x in result.fills],
        "signals": [{"date": s.trade_date, "action": s.action.value, "symbol": s.ts_code,
            "gate": s.evidence.get("gate"), "winner_before_gate": s.evidence.get("winner_before_gate")} for s in result.signals],
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
    return ledger


def build_report(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    sealed = run_scenario(root / "sealed", "sealed_priority_no_fallback")
    lifecycle = run_scenario(root / "lifecycle", "t1_locked_suspended_resume")
    return {"classification": "SYNTHETIC_MECHANICS_ONLY_NO_REAL_MARKET_EVIDENCE", "frozen_b0_config_modified": False,
        "protected_data_accessed": False, "scenarios": {"sealed_priority_no_fallback": sealed, "t1_locked_suspended_resume": lifecycle},
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
        "The lifecycle scenario records the next-session locked-limit sell rejection, a suspension-blocked sell, and a later post-09:35 exit. See the JSON for each attempt, round-lot quantity, cash path, fee lines and daily equity marks.", "",
        "No row refers to an actual security or market date. The scenario has no evidentiary weight for realized returns, execution probability or net expectancy.", ""]
    args.out_markdown.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": report["classification"], "sealed_fills": sealed["fills"], "lifecycle_fills": lifecycle["fills"], "trades": lifecycle["trades"]}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
