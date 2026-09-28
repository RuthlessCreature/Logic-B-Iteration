from datetime import date

import pandas as pd
import pytest

from logic_b.providers.xuangubao_market import (
    XuangubaoMarketProvider,
    XuangubaoMinuteDay,
    to_xgb_market_symbol,
)


def test_market_symbol_conversion():
    assert to_xgb_market_symbol("603607.SH")=="603607.SS"
    assert to_xgb_market_symbol("000001.SZ")=="000001.SZ"


class FakeMarket(XuangubaoMarketProvider):
    def __init__(self):
        pass

    def _json(self,path,params):
        assert path=="/kline"
        assert params["timestamp"]>0
        assert params["period_type"]==60
        fields=[
            "open_px","close_px","high_px","low_px",
            "px_change","px_change_rate","turnover_volume",
            "turnover_value","tick_at","avg_px",
        ]
        return {
            "code":20000,
            "message":"OK",
            "data":{
                "fields":fields,
                "candle":{
                    "603607.SS":{
                        "pre_close_px":22.36,
                        "lines":[
                            [22.4,22.5,22.6,22.3,0.14,0.6,1000,22400,1782783000,22.45],
                            [24.6,24.6,24.6,24.6,0,0,2000,49200,1782802620,24.05],
                        ],
                    }
                },
            },
        }


def test_historical_minute_normalization_and_limits():
    p=FakeMarket()
    result=p.historical_minute_day(
        "603607.SH",
        date(2026,6,30),
    )

    assert result.pre_close==22.36
    assert result.pre_close_source=="api"
    assert not result.bars.empty
    assert set([
        "trade_time","open","high","low","close","vol","amount"
    ])<=set(result.bars.columns)

    daily=p.daily_from_minute(result)
    assert daily.iloc[0]["close"]==24.6

    limits=p.limit_prices(result)
    assert limits.iloc[0]["up_limit"]==24.60
    assert limits.iloc[0]["down_limit"]==20.12


def test_historical_pre_close_override_wins_when_api_is_zero():
    class ZeroPreClose(FakeMarket):
        def _json(self,path,params):
            payload=super()._json(path,params)
            payload["data"]["candle"]["603607.SS"]["pre_close_px"]=0
            return payload

    result=ZeroPreClose().historical_minute_day(
        "603607.SH",
        date(2026,6,30),
        pre_close_override=22.36,
    )
    assert result.pre_close==22.36
    assert result.pre_close_source=="override"
    assert XuangubaoMarketProvider.limit_prices(
        result
    ).iloc[0]["up_limit"]==24.60


def test_chinext_limit_is_twenty_percent():
    result=XuangubaoMinuteDay(
        ts_code="300001.SZ",
        trade_date="20260630",
        bars=pd.DataFrame(),
        pre_close=10.0,
        pre_close_source="test",
        raw_lines=0,
    )
    limits=XuangubaoMarketProvider.limit_prices(result)
    assert limits.iloc[0]["up_limit"]==12.0
    assert limits.iloc[0]["down_limit"]==8.0
