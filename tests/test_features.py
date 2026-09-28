import pandas as pd
from logic_b.features import build_prev_day_candidate_features, classify_market_regime
from logic_b.models import MarketRegime

def test_candidate_features_rank_highest_board_first():
    df=pd.DataFrame({"ts_code":["A","B","C"],"limit_times":[5,2,1],"amount":[8e8,2e9,4e8],"turnover_ratio":[12,18,7],"open_num":[1,0,3],"lu_limit_order":[5e7,9e7,1e7]})
    out=build_prev_day_candidate_features(df)
    assert out.loc[out.ts_code=="A","r_height"].iloc[0]==1.0
    assert out["prev_core_score"].between(0,1).all()

def test_ice_regime():
    assert classify_market_regime(limit_up_count=20,limit_down_count=31,break_rate=.44,max_height=2,prev_limit_median_return=-.04)==MarketRegime.ICE
