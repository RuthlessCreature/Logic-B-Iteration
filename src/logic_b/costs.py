from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingCosts:
    """Retail A-share cash-equity cost model.

    commission_rate is treated as broker all-in commission excluding
    transfer fee and stamp duty. The actual broker schedule is account-specific.
    """

    commission_rate: float=0.0003
    minimum_commission: float=5.0
    transfer_fee_rate: float=0.00001
    stamp_rate: float=0.0005

    def __post_init__(self):
        for name in (
            "commission_rate",
            "minimum_commission",
            "transfer_fee_rate",
            "stamp_rate",
        ):
            if getattr(self,name)<0:
                raise ValueError(
                    f"{name} must be non-negative"
                )

    def commission(self,gross: float) -> float:
        if gross<=0:
            return 0.0
        return max(
            gross*self.commission_rate,
            self.minimum_commission,
        )

    def transfer_fee(self,gross: float) -> float:
        if gross<=0:
            return 0.0
        return gross*self.transfer_fee_rate

    def buy_cost(self,gross: float) -> float:
        return (
            self.commission(gross)
            +self.transfer_fee(gross)
        )

    def sell_cost(self,gross: float) -> float:
        return (
            self.commission(gross)
            +self.transfer_fee(gross)
            +gross*self.stamp_rate
        )
