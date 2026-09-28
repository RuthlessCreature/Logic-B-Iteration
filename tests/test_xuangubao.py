from datetime import date

import pandas as pd

from logic_b.providers.xuangubao import (
    XuangubaoEvidenceProvider,
    normalize_xgb_pool,
    normalize_xgb_symbol,
)


SAMPLE={
    "symbol":"603607.SS",
    "stock_chi_name":"京华激光",
    "limit_up_days":1,
    "m_days_n_boards_days":0,
    "m_days_n_boards_boards":0,
    "first_limit_up":1782784320,
    "last_limit_up":1782800609,
    "break_limit_up_times":1,
    "turnover_ratio":0.096089735,
    "non_restricted_capital":4391513280,
    "buy_lock_volume_ratio":0.0077086984,
    "sell_lock_volume_ratio":0,
    "prev_close_price":22.36,
    "price":24.6,
    "change_percent":0.1001788909,
    "is_new_stock":False,
    "listed_date":1508860800,
    "surge_reason":{
        "stock_reason":"测试涨停原因",
        "related_plates":[
            {"plate_name":"包装印刷"},
            {"plate_name":"激光"},
        ],
    },
}


def test_xgb_symbol_normalization():
    assert normalize_xgb_symbol("603607.SS")=="603607.SH"
    assert normalize_xgb_symbol("000001.SZ")=="000001.SZ"


def test_xgb_pool_normalization_uses_real_schema():
    frame=normalize_xgb_pool(
        [SAMPLE],
        trade_date=date(2026,6,30),
        pool_name="limit_up",
    )
    row=frame.iloc[0]
    assert row["ts_code"]=="603607.SH"
    assert row["name"]=="京华激光"
    assert row["tag"]=="首板"
    assert row["open_num"]==1
    assert row["theme"]=="包装印刷、激光"
    assert row["reason"]=="测试涨停原因"
    assert row["turnover_estimated"]>400_000_000


def test_xgb_multi_day_board_tag():
    sample=dict(SAMPLE)
    sample["limit_up_days"]=2
    sample["m_days_n_boards_days"]=7
    sample["m_days_n_boards_boards"]=5
    frame=normalize_xgb_pool(
        [sample],
        trade_date=date(2026,6,30),
        pool_name="limit_up",
    )
    assert frame.iloc[0]["tag"]=="7天5板"


class FakeXgb(XuangubaoEvidenceProvider):
    def __init__(self):
        pass

    def _json(self,path,params):
        if path=="/pool/detail":
            pool=params["pool_name"]
            rows=[SAMPLE] if pool=="limit_up" else []
            return {"code":200,"message":"ok","data":rows}
        return {
            "code":200,
            "message":"ok",
            "data":[{
                "rise_count":2902,
                "fall_count":2200,
                "limit_up_count":169,
                "limit_down_count":20,
                "limit_up_broken_count":35,
                "limit_up_broken_ratio":0.17156862745,
                "yesterday_limit_up_avg_pcp":0.0306418501,
                "market_temperature":54.816,
                "timestamp":1782802800,
            }],
        }


def test_xgb_preflight_and_theme_projection():
    client=FakeXgb()
    result=client.preflight(date(2026,6,30))
    assert result["ok"]
    assert result["limit_up_count"]==1
    assert result["indicator_rows"]==1

    themes=client.theme_limit_list(date(2026,6,30))
    assert themes.iloc[0]["theme"]=="包装印刷、激光"
    assert themes.iloc[0]["status"]=="首板"
