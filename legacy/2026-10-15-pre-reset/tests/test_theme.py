import pandas as pd

from logic_b.models import CoreType
from logic_b.strategy.b0 import B0Proxy
from logic_b.theme import build_prev_day_theme_evidence, split_themes


def test_split_kpl_themes():
    assert split_themes("机器人、人工智能,工业母机")==["机器人","人工智能","工业母机"]


def test_theme_evidence_prefers_broader_theme():
    df=pd.DataFrame({
        "ts_code":["A","B","C","D"],
        "theme":["机器人、消费","机器人","机器人","消费"],
        "status":["2连板","首板","3连板","首板"],
        "amount":[10,20,30,5],
    })
    out=build_prev_day_theme_evidence(df)
    a=out[out.ts_code=="A"].iloc[0]
    assert a["theme_name"]=="机器人"
    assert a["theme_limit_up_count"]==3
    assert bool(a["has_theme_evidence"])


def test_sector_capacity_core_requires_theme_evidence():
    naked=pd.Series({
        "f_height":2,
        "r_amount":.95,
        "r_turnover":.50,
        "prev_core_score":.80,
        "has_theme_evidence":False,
        "theme_limit_up_count":0,
        "theme_strength":0,
    })
    assert B0Proxy._core_type(naked,max_height=5)!=CoreType.SECTOR_CAPACITY_CORE

    themed=naked.copy()
    themed["has_theme_evidence"]=True
    themed["theme_limit_up_count"]=4
    themed["theme_strength"]=.85
    assert B0Proxy._core_type(themed,max_height=5)==CoreType.SECTOR_CAPACITY_CORE


def test_catchup_core_requires_theme_evidence():
    row=pd.Series({
        "f_height":1,
        "r_amount":.60,
        "r_turnover":.50,
        "prev_core_score":.72,
        "has_theme_evidence":False,
        "theme_limit_up_count":0,
        "theme_strength":0,
    })
    assert B0Proxy._core_type(row,max_height=5)==CoreType.NONE
