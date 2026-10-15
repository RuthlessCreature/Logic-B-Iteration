"""Frozen transparent v0 heuristic, replaceable only through versioned research proposals."""
from __future__ import annotations
from .identity import canonical_code

def select_core(previous: dict, cfg: dict) -> tuple[str | None, str]:
    """Only yesterday's completed Xuangubao pool and market summary are consulted."""
    candidates = previous.get("limit_up", [])
    market = previous.get("market", {})
    if not isinstance(candidates, list) or not isinstance(market, dict):
        return None, "SOURCE_UNAVAILABLE"
    floor = cfg.get("min_market_temperature")
    if floor is not None:
        t = market.get("market_temperature")
        if t is None or float(t) < float(floor):
            return None, "MARKET_GATE"
    allowed = []
    for c in candidates:
        try:
            sym = canonical_code(c["symbol"])
            streak = int(c.get("limit_up_days", 1))
            breaks = int(c.get("break_limit_up_times", 0))
        except (ValueError, TypeError