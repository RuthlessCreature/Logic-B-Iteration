"""Explicit historical A-share broker commission, stamp tax, and transfer fee."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from math import isfinite

@dataclass(frozen=True)
class Fees:
    commission: float
    transfer: float
    stamp: float
    @property
    def total(self) -> float:
        return round(self.commission + self.transfer + self.stamp, 6)

def compute_fees(amount: float, side: str, day: str, *, rate: float = .00025, minimum: float = 5.) -> Fees:
    if not isfinite(amount) or amount <= 0 or not isfinite(rate) or rate < 0 or minimum < 0:
        raise ValueError("invalid trade amount or fee setting")
    when = date.fromisoformat(day)
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    commission = max(minimum, amount * rate)
    transfer = amount * (.00002 if when < date(2022, 4, 29) else .00001)
    stamp = amount * ((.001 if when < date(2023, 8, 28) else .0005) if side == "SELL" else 0.)
    return Fees(round(commission, 6), round(transfer, 6), round(stamp, 6))
