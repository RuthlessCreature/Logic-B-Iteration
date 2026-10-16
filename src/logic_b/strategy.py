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
        except (ValueError, TypeError, KeyError):
            continue
        allowed.append((-streak, breaks, sym))
    if not allowed:
        return None, "NO_PRIOR_DAY_CANDIDATE"
    allowed.sort()
    if cfg.get("leader_only", False):
        # Logic-A-style core selection is made before eligibility gates. If
        # that leader fails, stay in cash; do not silently promote a rear row.
        neg_streak, breaks, symbol = allowed[0]
        if -neg_streak < int(cfg.get("min_streak", 1)) or breaks > int(cfg.get("max_breaks", 100)):
            return None, "LEADER_VETOED"
        return symbol, "PRIOR_DAY_LEADER"
    eligible = [row for row in allowed if -row[0] >= int(cfg.get("min_streak", 1))
                and row[1] <= int(cfg.get("max_breaks", 100))]
    if not eligible:
        return None, "NO_PRIOR_DAY_CANDIDATE"
    return eligible[0][2], "PRIOR_DAY_CORE"
