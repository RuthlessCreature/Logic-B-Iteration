from datetime import datetime
import pandas as pd
import pytest
from logic_b.point_in_time import FutureDataLeakError, assert_available_at
from logic_b.portfolio import Portfolio

def test_future_feature_is_rejected():
    frame=pd.DataFrame({"x":[1,2],"available_at":["2026-09-28 09:30:00","2026-09-28 15:05:00"]})
    with pytest.raises(FutureDataLeakError):
        assert_available_at(frame,datetime(2026,9,28,9,35))

def test_t_plus_one_enforced():
    p=Portfolio(100000)
    p.buy_all("X",datetime(2026,9,28,9,35),10)
    with pytest.raises(RuntimeError,match=r"T\+1"):
        p.sell_all(datetime(2026,9,28,14,30),10.5)
    p.sell_all(datetime(2026,9,29,9,35),10.5)
    assert p.position is None
