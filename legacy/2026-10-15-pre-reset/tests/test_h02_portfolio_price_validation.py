import math
from datetime import datetime
import pytest
from logic_b.portfolio import Portfolio

ENTRY = datetime(2020, 1, 2, 9, 36)
EXIT = datetime(2020, 1, 3, 9, 36)

@pytest.mark.parametrize('price', [float('nan'), float('inf'), -float('inf'), 0.0, -1.0])
def test_buy_rejects_invalid_price_before_cash_mutation(price):
    p = Portfolio(initial_cash=100_000)
    with pytest.raises(ValueError, match='finite positive'):
        p.buy_all('000998.SZ', ENTRY, price)
    assert p.cash == 100_000 and p.position is None

@pytest.mark.parametrize('price', [float('nan'), float('inf'), -float('inf'), 0.0, -1.0])
def test_sell_rejects_invalid_price_before_position_mutation(price):
    p = Portfolio(initial_cash=100_000)
    position = p.buy_all('000998.SZ', ENTRY, 10.0)
    before = p.cash
    with pytest.raises(ValueError, match='finite positive'):
        p.sell_all(EXIT, price)
    assert p.position is position and p.cash == before

@pytest.mark.parametrize('price', [float('nan'), float('inf'), -float('inf'), 0.0, -1.0])
def test_mark_to_market_rejects_invalid_price(price):
    p = Portfolio(initial_cash=100_000)
    p.buy_all('000998.SZ', ENTRY, 10.0)
    with pytest.raises(ValueError, match='finite positive'):
        p.equity(price)


def test_valid_trade_preserves_t_plus_one_and_fees():
    p = Portfolio(initial_cash=100_000)
    position = p.buy_all('000998.SZ', ENTRY, 10.0)
    with pytest.raises(RuntimeError, match='T\\+1'):
        p.sell_all(datetime(2020, 1, 2, 14, 30), 10.5)
    assert p.position is position
    expected = position.shares * 10.5 - p.costs.sell_cost(position.shares * 10.5)
    assert p.sell_all(EXIT, 10.5) == pytest.approx(expected)
    assert p.position is None and math.isfinite(p.cash)
