"""Deterministic replay: previous-day XGB selection; completed 09:45 five-minute bar execution.

This is a bar-based simulation, NOT certified real order fills. No future D
event pool is used for D selection. Dates outside 2020-01-01..2026-06-30 reject.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import math

from .fees import compute_fees
from .identity import canonical_code
from .strategy import select_core

FIRST = "2020-01-01"
LAST = "2026-06-30"


def _numeric(value) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite price")
    return number


def _tick(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _band(code: str, day: str, is_st: bool | None) -> float | None:
    if is_st is None:
        return None
    if is_st:
        return .05
    prefix = code[:3]
    if prefix in ("688", "689"):
        return .20
    if code.startswith(("300", "301")):
        return .10 if day < "2020-08-24" else .20
    if code.endswith(".BJ"):
        return .30
    if code.endswith((".SH", ".SZ")):
        return .10
    return None


def _limit_prices(previous_close: float, band: float) -> tuple[float, float]:
    if previous_close <= 0:
        raise ValueError("nonpositive previous close")
    return (_tick(previous_close * (1 + band)), _tick(previous_close * (1 - band)))


def _snapshot_map(raw: dict, key: str) -> dict:
    result = {}
    for code, detail in raw.get(key, {}).items():
        canon = canonical_code(code)
        if canon in result:
            raise ValueError(f"duplicate canonical code in {key}: {canon}")
        result[canon] = detail
    return result


def _bar(day: dict, code: str, execution_time: str) -> tuple[dict | None, str]:
    bars = _snapshot_map(day, "bars_5m").get(code)
    if not bars:
        return None, "MISSING_5M_BARS"
    eligible = []
    last = None
    for bar in bars:
        at = bar.get("time")
        if not isinstance(at, str) or len(at) != 5 or at[2] != ":" or not at[:2].isdigit() or not at[3:].isdigit() or not ("09:30" <= at <= "15:00"):
            return None, "INVALID_BAR_TIME"
        if last is not None and at <= last:
            return None, "UNSORTED_BAR_TIMES"
        last = at
        try:
            o, h, l, c = (_numeric(bar[k]) for k in ("open", "high", "low", "close"))
            vol = _numeric(bar.get("volume", 0))
            if min(o, h, l, c) <= 0 or vol < 0 or l > min(o, c) or h < max(o, c):
                return None, "INVALID_BAR_OHLC"
        except (ValueError, TypeError, KeyError):
            return None, "INVALID_BAR_OHLC"
        if at >= execution_time:
            eligible.append(bar)
    if not eligible:
        return None, "NO_COMPLETED_EXECUTION_BAR"
    chosen = eligible[0]
    if _numeric(chosen.get("volume", 0)) <= 0:
        return None, "ZERO_VOLUME_BAR"
    return chosen, "BAR_READY"


def _tradeable(day: dict, prev: dict, code: str, execution_time: str, side: str):
    daily = _snapshot_map(day, "daily").get(code)
    prev_daily = _snapshot_map(prev, "daily").get(code)
    if daily is None or prev_daily is None:
        return None, "MISSING_DAILY", None
    if daily.get("tradestatus") in (0, "0", False):
        return None, "SUSPENDED", None
    if daily.get("tradestatus") not in (1, "1", True):
        return None, "TRADE_STATUS_UNKNOWN", None
    previous_close = _numeric(prev_daily.get("close", 0))
    if previous_close <= 0:
        return None, "INVALID_PREVIOUS_CLOSE", None
    ref = daily.get("preclose")
    if ref is not None:
        reference_close = _numeric(ref)
        if reference_close <= 0:
            return None, "INVALID_REFERENCE_CLOSE", None
        # We cannot adjust owned shares/cash for splits, dividends or other
        # actions yet. Reject new fills rather than manufacture profitability.
        if abs(reference_close - previous_close) > 0.011:
            return None, "CORPORATE_ACTION_UNRECONCILED", None
    else:
        reference_close = previous_close
    previous_st = prev_daily.get("is_st", None)
    current_st = daily.get("is_st", None)
    if not isinstance(previous_st, bool) or not isinstance(current_st, bool):
        return None, "LIMIT_BAND_UNKNOWN", None
    if previous_st != current_st:
        return None, "ST_STATUS_CHANGE_NEEDS_PRICE_LIMIT", None
    ratio = _band(code, day["date"], current_st)
    if ratio is None:
        return None, "LIMIT_BAND_UNKNOWN", None
    if daily.get("no_price_limit", False) or prev_daily.get("no_price_limit", False):
        return None, "IPO_LIMIT_UNKNOWN", None
    upper, lower = _limit_prices(reference_close, ratio)
    bar, reason = _bar(day, code, execution_time)
    if bar is None:
        return None, reason, (upper, lower)
    price = _numeric(bar["close"])
    if side == "BUY" and price >= upper - 1e-8:
        return None, "NO_FILL_LIMIT_UP", (upper, lower)
    if side == "SELL" and price <= lower + 1e-8:
        return None, "NO_FILL_LIMIT_DOWN", (upper, lower)
    # If a vendor quote is beyond the inferred valid daily band, reject
    # rather than hiding a likely corporate-action or data mismatch.
    if price > upper + .011 or price < lower - .011:
        return None, "PRICE_OUTSIDE_BAND", (upper, lower)
    return price, "SIMULATED_BAR_CLOSE_FILL", (upper, lower)


def replay(dataset: dict, config: dict) -> dict:
    if config.get("start") != FIRST or config.get("end") != LAST:
        raise ValueError("unexpected research date boundary")
    starting = _numeric(config["initial_cash"])
    if starting <= 0:
        raise ValueError("initial cash must be positive")
    snapshots = dataset.get("days", [])
    if not isinstance(snapshots, list):
        raise ValueError("days must be list")
    dates = [d["date"] for d in snapshots]
    if dates != sorted(set(dates)):
        raise ValueError("trading days must be strictly sorted and unique")
    if any(not (FIRST <= d <= LAST) for d in dates):
        raise ValueError("protected or outside-range day")
    commission = float(config["commission_rate"])
    minimum = float(config["minimum_commission"])
    size = int(config["lot_size"])
    if size != 100 or starting != 10000 or commission != .00025 or minimum != 5:
        raise ValueError("base account contract altered")
    execution_time = config.get("execution_time", "09:45")
    if execution_time < "09:45":
        raise ValueError("cannot fill signal's own five-minute bar")
    cash = starting
    stock = None
    shares = 0
    bought_on = None
    entry_cost = 0.
    orders, fills, equity, round_trips = [], [], [], []
    last_mark = {}
    unadjusted_action_days = []
    previous_daily_close = {}
    for i, day in enumerate(snapshots):
        trade_day = day["date"]
        prior = snapshots[i - 1] if i else None
        if not isinstance(day.get("daily", {}), dict):
            raise ValueError("daily must be a map")
        for code, row in _snapshot_map(day, "daily").items():
            v = _numeric(row.get("close")) if row.get("close") is not None else 0.0
            observed_reference = row.get("preclose")
            if observed_reference is not None and code in previous_daily_close:
                if abs(_numeric(observed_reference) - previous_daily_close[code]) > 0.011:
                    unadjusted_action_days.append({"day": trade_day, "symbol": code,
                        "prior_unadjusted_close": previous_daily_close[code],
                        "provider_reference_close": _numeric(observed_reference)})
            if v > 0:
                last_mark[code] = v
                previous_daily_close[code] = v

        if stock and bought_on != trade_day and prior is not None:
            price, reason, limits = _tradeable(day, prior, stock, execution_time, "SELL")
            attempt = {"day": trade_day, "time": execution_time, "side": "SELL", "symbol": stock, "shares": shares,
                       "price": price, "reason": reason, "limits": limits}
            if price is not None:
                gross = round(shares * price, 6)
                fees = compute_fees(gross, "SELL", trade_day, rate=commission, minimum=minimum)
                net = gross - fees.total
                cash = round(cash + net, 6)
                attempt["fees"] = vars(fees)
                attempt["gross"] = gross
                pnl = round(net - entry_cost, 6)
                round_trips.append({"symbol": stock, "bought_on": bought_on, "sold_on": trade_day,
                                    "shares": shares, "net_pnl": pnl, "buy_including_fees": entry_cost,
                                    "sell_less_fees": net})
                fills.append(dict(attempt))
                stock, shares, bought_on, entry_cost = None, 0, None, 0.
            orders.append(attempt)

        # No buy on a day with any sell attempt (whether it filled or not).
        sold_or_attempted = any(x["day"] == trade_day and x["side"] == "SELL" for x in orders)
        if stock is None and not sold_or_attempted and prior is not None:
            candidate, reason = select_core(prior, config.get("baseline", {}))
            if candidate:
                price, fill_reason, limits = _tradeable(day, prior, candidate, execution_time, "BUY")
                attempt = {"day": trade_day, "time": execution_time, "side": "BUY", "symbol": candidate,
                           "price": price, "reason": fill_reason, "limits": limits}
                if price is not None:
                    lots = int(cash // (price * size))
                    while lots:
                        qty = lots * size
                        gross = round(qty * price, 6)
                        cost = compute_fees(gross, "BUY", trade_day, rate=commission, minimum=minimum)
                        total = gross + cost.total
                        if total <= cash + 1e-7:
                            break
                        lots -= 1
                    if not lots:
                        attempt.update(reason="INSUFFICIENT_CASH_FOR_100_SHARES", price=None)
                    else:
                        cash = round(cash - total, 6)
                        stock, shares, bought_on, entry_cost = candidate, qty, trade_day, total
                        attempt.update(shares=qty, gross=gross, fees=vars(cost))
                        fills.append(dict(attempt))
                orders.append(attempt)
            else:
                orders.append({"day": trade_day, "side": "CASH", "symbol": None, "reason": reason})
        value = shares * last_mark.get(stock, 0) if stock else 0.
        stale = bool(stock and stock not in _snapshot_map(day, "daily"))
        equity.append({"day": trade_day, "cash": round(cash, 6), "symbol": stock, "shares": shares,
                       "mark_stale": stale,
                       "corporate_action_unreconciled": bool(stock and any(
                           x["symbol"] == stock and bought_on is not None and x["day"] >= bought_on
                           for x in unadjusted_action_days)),
                       "equity": round(cash + value, 6)})

    last_equity = equity[-1]["equity"] if equity else cash
    peak = starting
    max_drawdown = 0.
    for row in equity:
        peak = max(peak, row["equity"])
        max_drawdown = min(max_drawdown, row["equity"] / peak - 1)
    grouped = {}
    for row in equity:
        yr = row["day"][:4]
        grouped.setdefault(yr, []).append(row)
    yearly = []
    prev = starting
    for yr, rows in grouped.items():
        ending = rows[-1]["equity"]
        yearly.append({"year": yr, "days": len(rows), "starting_equity": prev, "ending_equity": ending,
                       "return_pct": round((ending / prev - 1) * 100, 4) if prev else None})
        prev = ending
    account_incomplete = bool(unadjusted_action_days or any(x["mark_stale"] or x["corporate_action_unreconciled"] for x in equity))
    return {"classification": "BAR_CLOSE_SIMULATION_NOT_REAL_FILL",
            "status": "PARTIAL" if dataset.get("coverage_complete") is not True or account_incomplete else "SIMULATED_FULL_COVERAGE",
            "account_unresolved_corporate_actions": unadjusted_action_days,
            "initial_cash": starting, "final_equity": last_equity, "return_pct": round((last_equity / starting - 1) * 100, 4),
            "max_drawdown_pct": round(max_drawdown * 100, 4),
            "orders": orders, "fills": fills, "closed_trades": round_trips, "daily_equity": equity,
            "yearly": yearly, "warnings": ["Daily unadjusted close requires corporate-action accounting for accurate long holds.",
                "5-minute completed-bar close is a model assumption, not actual queue execution.",
                "Source coverage and 09:35 point-in-time availability must be verified before following live."]}
