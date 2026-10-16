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


def test_higher_core_priority_beats_stronger_lower_tier_candidate():
    previous=pd.DataFrame({
        "ts_code":["LEADER","CAP","MATE1","MATE2"],
        "limit_times":[4,2,1,1],
        "amount":[5e8,2.5e9,3e8,2e8],
        "turnover_ratio":[8,14,5,4],
        "open_num":[1,0,1,1],
        "lu_limit_order":[2e7,2e8,1e7,1e7],
    })
    themes=pd.DataFrame({
        "ts_code":["CAP","MATE1","MATE2"],
        "theme":["机器人","机器人","机器人"],
        "status":["2连板","首板","首板"],
        "amount":[2.5e9,3e8,2e8],
    })
    cp=pd.DataFrame({
        "ts_code":["LEADER","CAP","MATE1","MATE2"],
        "pct_from_prev_close":[.07,.095,.01,.01],
        "relative_to_peer_median":[.04,.06,-.02,-.02],
        "checkpoint_amount_rank":[.70,1.0,.30,.20],
        "at_limit":[False,False,False,False],
        "one_price_limit":[False,False,False,False],
        "opened_after_limit":[False,True,False,False],
    })
    s=B0Proxy().decide(
        trade_date="20260928",
        decision_time=datetime(2026,9,28,9,35),
        prev_limit_df=previous,
        checkpoint_df=cp,
        market_regime=MarketRegime.TRIAL,
        prev_theme_df=themes,
    )
    assert s.action==Action.BUY_CORE
    assert s.ts_code=="LEADER"


def test_failed_top_priority_does_not_fall_back_to_lower_tier():
    previous=pd.DataFrame({
        "ts_code":["LEADER","CAP","MATE1","MATE2"],
        "limit_times":[4,2,1,1],
        "amount":[5e8,2.5e9,3e8,2e8],
        "turnover_ratio":[8,14,5,4],
        "open_num":[1,0,1,1],
        "lu_limit_order":[2e7,2e8,1e7,1e7],
    })
    themes=pd.DataFrame({
        "ts_code":["CAP","MATE1","MATE2"],
        "theme":["机器人","机器人","机器人"],
        "status":["2连板","首板","首板"],
        "amount":[2.5e9,3e8,2e8],
    })
    cp=pd.DataFrame({
        "ts_code":["LEADER","CAP","MATE1","MATE2"],
        "pct_from_prev_close":[-.02,.095,.01,.01],
        "relative_to_peer_median":[-.06,.06,-.02,-.02],
        "checkpoint_amount_rank":[.20,1.0,.30,.20],
        "at_limit":[False,False,False,False],
        "one_price_limit":[False,False,False,False],
        "opened_after_limit":[False,True,False,False],
    })
    s=B0Proxy().decide(
        trade_date="20260928",
        decision_time=datetime(2026,9,28,9,35),
        prev_limit_df=previous,
        checkpoint_df=cp,
        market_regime=MarketRegime.TRIAL,
        prev_theme_df=themes,
    )
    assert s.action==Action.CASH
    assert s.ts_code is None
    assert s.evidence["winner_before_gate"]=="LEADER"
