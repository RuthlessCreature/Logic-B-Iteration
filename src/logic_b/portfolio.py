from __future__ import annotations

from dataclasses import dataclass,field
from datetime import datetime

from .costs import TradingCosts
from .models import Position


@dataclass
class Portfolio:
    initial_cash: float=1_000_000.0
    costs: TradingCosts=field(
        default_factory=TradingCosts
    )
    cash: float=field(init=False)
    position: Position | None=None

    def __post_init__(self):
        self.cash=float(self.initial_cash)

    def buy_all(
        self,
        ts_code: str,
        at: datetime,
        price: float,
    ) -> Position:
        if self.position is not None:
            raise RuntimeError(
                "B0 allows at most one position"
            )
        if price<=0:
            raise ValueError(
                "price must be positive"
            )

        shares=int(
            self.cash/price//100*100
        )
        while shares>0:
            gross=shares*price
            total=gross+self.costs.buy_cost(
                gross
            )
            if total<=self.cash:
                break
            shares-=100

        if shares<=0:
            raise RuntimeError(
                "insufficient cash"
            )

        gross=shares*price
        buy_cost=self.costs.buy_cost(gross)
        cash_used=gross+buy_cost

        self.cash-=cash_used
        self.position=Position(
            ts_code,
            at,
            price,
            shares,
            cash_used,
        )
        return self.position

    def sell_all(
        self,
        at: datetime,
        price: float,
    ) -> float:
        if self.position is None:
            raise RuntimeError(
                "no position"
            )
        if (
            at.date()
            <=self.position.entry_time.date()
        ):
            raise RuntimeError(
                "T+1 violation: same-day sell is forbidden"
            )

        gross=self.position.shares*price
        sell_cost=self.costs.sell_cost(gross)
        net=gross-sell_cost

        self.cash+=net
        self.position=None
        return net

    def equity(
        self,
        mark_price: float | None=None,
    ) -> float:
        if self.position is None:
            return self.cash
        if mark_price is None:
            mark_price=self.position.entry_price
        return (
            self.cash
            +self.position.shares*mark_price
        )
