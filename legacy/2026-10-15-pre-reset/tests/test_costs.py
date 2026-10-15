from datetime import datetime
import math

import pytest

from logic_b.costs import TradingCosts
from logic_b.portfolio import Portfolio


def test_trading_cost_components():
    costs=TradingCosts(
        commission_rate=0.0003,
        minimum_commission=5.0,
        transfer_fee_rate=0.00001,
        stamp_rate=0.0005,
    )

    assert costs.commission(10000)==5.0
    assert costs.transfer_fee(10000)==pytest.approx(0.1)
    assert costs.buy_cost(10000)==pytest.approx(5.1)
    assert costs.sell_cost(10000)==pytest.approx(10.1)


def test_large_trade_uses_rate_instead_of_minimum_commission():
    costs=TradingCosts(
        commission_rate=0.0003,
        minimum_commission=5.0,
        transfer_fee_rate=0.00001,
        stamp_rate=0.0005,
    )
    assert costs.commission(1_000_000)==pytest.approx(300.0)


@pytest.mark.parametrize("field", [
    "commission_rate", "minimum_commission", "transfer_fee_rate", "stamp_rate",
])
@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_trading_costs_reject_non_finite_values(field, invalid):
    with pytest.raises(ValueError, match=f"{field} must be finite"):
        TradingCosts(**{field: invalid})


@pytest.mark.parametrize("field", [
    "commission_rate", "minimum_commission", "transfer_fee_rate", "stamp_rate",
])
def test_trading_costs_reject_negative_values(field):
    with pytest.raises(ValueError, match=f"{field} must be finite and non-negative"):
        TradingCosts(**{field: -0.01})


@pytest.mark.parametrize("invalid", [0, -1, math.nan, math.inf, -math.inf])
def test_portfolio_rejects_invalid_initial_cash(invalid):
    with pytest.raises(ValueError, match="initial_cash must be finite and positive"):
        Portfolio(initial_cash=invalid)


def test_portfolio_cash_includes_buy_and_sell_costs():
    costs=TradingCosts(
        commission_rate=0.0003,
        minimum_commission=5.0,
        transfer_fee_rate=0.00001,
        stamp_rate=0.0005,
    )
    p=Portfolio(
        100000,
        costs=costs,
    )
    position=p.buy_all(
        "600000.SH",
        datetime(2026,9,28,9,36),
        10.0,
    )

    entry_cost=(
        position.cash_used
        -position.shares*position.entry_price
    )
    assert entry_cost>0
    assert p.cash>=0

    net=p.sell_all(
        datetime(2026,9,29,9,36),
        10.5,
    )
    gross=position.shares*10.5
    assert net==pytest.approx(
        gross-costs.sell_cost(gross)
    )
