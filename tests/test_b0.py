from datetime import datetime
import pandas as pd
from logic_b.models import Action, MarketRegime
from logic_b.strategy.b0 import B0Proxy

def prev():
    return pd.DataFrame({"ts_code":["LEADER","BACK"],"limit_times":[5,2],"amount":[1.6e9,8e8],"turnover_ratio":[15,9],"open_num":[1,2],"lu_limit_order":[1.2e8,3e7]})

def test_blocked_regime_forces_cash():
    s=B0Proxy().decide(trade_date="20260928",decision_time=datetime(2026,9,28,9,35),prev_limit_df=prev(),checkpoint_df=pd.DataFrame({"ts_code":["LEADER"]}),market_regime=MarketRegime.RETREAT)
    assert s.action==Action.CASH

def test_core_can_be_selected_when_confirmed_and_tradeable():
    cp=pd.DataFrame({"ts_code":["LEADER","BACK"],"pct_from_prev_close":[.075,.01],"relative_to_peer_median":[.045,-.02],"checkpoint_amount_rank":[.95,.3],"at_limit":[False,False],"one_price_limit":[False,False],"opened_after_limit":[True,False]})
    s=B0Proxy().decide(trade_date="20260928",decision_time=datetime(2026,9,28,9,35),prev_limit_df=prev(),checkpoint_df=cp,market_regime=MarketRegime.TRIAL)
    assert s.action==Action.BUY_CORE
    assert s.ts_code=="LEADER"
