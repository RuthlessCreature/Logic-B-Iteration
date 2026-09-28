from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import Position


@dataclass
class Portfolio:
    initial_cash: float = 1_000_000.0
    cash: float = 1_000_000.0
    position: Position | None = None

    def __post_init__(self):
        self.cash = float(self.initial_cash)

    def buy_all(self, ts_code: str, at: datetime, price: float, fee_rate: float = 0.0003) -> Position:
        if self.position is not None:
            raise RuntimeError("B0 allows at most one position")
        if price <= 0:
            raise ValueError("price must be positive")
        shares = int(self.cash / (price * (1 + fee_rate)) // 100 * 100)
        if shares <= 0:
            raise RuntimeError("insufficient cash")
        gross = shares * price
        fee = gross * fee_rate
        self.cash -= gross + fee
        self.position = Position(ts_code, at, price, shares, gross + fee)
        return self.position

    def sell_all(
        self,
        at: datetime,
        price: float,
        fee_rate: float = 0.0003,
        stamp_rate: float = 0.0005,
    ) -> float:
        if self.position is None:
            raise RuntimeError("no position")
        if at.date() <= self.position.entry_time.date():
            raise RuntimeError("T+1 violation: same-day sell is forbidden")
        gross = self.position.shares * price
        fees = gross * (fee_rate + stamp_rate)
        self.cash += gross - fees
        self.position = None
        return gross - fees

    def equity(self, mark_price: float | None = None) -> float:
        if self.position is None:
            return self.cash
        if mark_price is None:
            mark_price = self.position.entry_price
        return self.cash + self.position.shares * mark_price
