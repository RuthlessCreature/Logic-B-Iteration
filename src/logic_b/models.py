from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class MarketRegime(StrEnum):
    ATTACK = "ATTACK"
    TRIAL = "TRIAL"
    NEUTRAL = "NEUTRAL"
    RETREAT = "RETREAT"
    ICE = "ICE"


class CoreType(StrEnum):
    TOTAL_MARKET_LEADER = "TOTAL_MARKET_LEADER"
    SECTOR_CAPACITY_CORE = "SECTOR_CAPACITY_CORE"
    TURNOVER_FRONT = "TURNOVER_FRONT"
    CATCHUP_CORE = "CATCHUP_CORE"
    NONE = "NONE"


class Action(StrEnum):
    BUY_CORE = "BUY_CORE"
    HOLD = "HOLD"
    SELL = "SELL"
    CASH = "CASH"


class FillModel(StrEnum):
    OPTIMISTIC = "optimistic"
    REALISTIC = "realistic"
    CONSERVATIVE = "conservative"


@dataclass(frozen=True)
class Signal:
    trade_date: str
    decision_time: datetime
    ts_code: str | None
    strategy_version: str
    market_regime: MarketRegime
    core_type: CoreType
    candidate_score: float
    confirmation_score: float
    tradability_score: float
    risk_score: float
    action: Action
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Fill:
    ts_code: str
    side: str
    signal_time: datetime
    fill_time: datetime | None
    fill_price: float | None
    filled: bool
    reason: str
    model: FillModel


@dataclass
class Position:
    ts_code: str
    entry_time: datetime
    entry_price: float
    shares: int
    cash_used: float
