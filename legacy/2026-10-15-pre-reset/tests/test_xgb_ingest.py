from datetime import date

import pandas as pd

from logic_b.providers.xuangubao import XuangubaoEvidenceProvider
from logic_b.storage import LocalParquetStore
from logic_b.xgb_ingest import XuangubaoEvidenceIngestor


class FakeProvider(XuangubaoEvidenceProvider):
    def __init__(self):
        pass

    def market_indicator_line(self,day):
        if day==date(2026,6,29):
            return pd.DataFrame()
        return pd.DataFrame([{
            "trade_date":day.strftime("%Y%m%d"),
            "timestamp":1,
            "limit_up_count":1,
            "limit_down_count":0,
            "limit_up_broken_count":0,
            "source":"xuangubao",
        }])

    def limit_list(self,day,limit_type="涨停池"):
        if limit_type!="涨停池":
            return pd.DataFrame(columns=[
                "trade_date","ts_code","tag","theme",
                "turnover_estimated","reason",
            ])
        return pd.DataFrame([{
            "trade_date":day.strftime("%Y%m%d"),
            "ts_code":"600000.SH",
            "tag":"首板",
            "theme":"银行",
            "turnover_estimated":100.0,
            "reason":"测试",
        }])


def test_xgb_evidence_ingestor_builds_calendar_and_theme(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    ingestor=XuangubaoEvidenceIngestor(
        FakeProvider(),
        store,
        inter_request_sleep=0,
    )

    dates=ingestor.fetch_range(
        date(2026,6,26),
        date(2026,6,30),
    )

    assert dates==[
        "20260626",
        "20260630",
    ]
    assert store.exists(
        "theme_limit_up",
        "20260630",
    )
    theme=store.read_frame(
        "theme_limit_up",
        "20260630",
    )
    assert theme.iloc[0]["theme"]=="银行"

    calendar=store.read_frame(
        "calendar",
        "20260626_20260630",
    )
    assert calendar["cal_date"].tolist()==dates


def test_xgb_evidence_range_reports_progress(tmp_path):
    store=LocalParquetStore(tmp_path/"data")

    class Provider:
        def market_indicator_line(self,day):
            if day.strftime("%Y%m%d")=="20260928":
                return pd.DataFrame({"trade_date":["20260928"]})
            return pd.DataFrame()

        def limit_list(self,day,pool_type):
            return pd.DataFrame(columns=["trade_date","ts_code"])

    ingestor=XuangubaoEvidenceIngestor(
        Provider(),
        store,
        inter_request_sleep=0,
    )
    events=[]
    dates=ingestor.fetch_range(
        date(2026,9,28),
        date(2026,9,29),
        progress_callback=events.append,
    )

    assert dates==["20260928"]
    assert len(events)==2
    assert events[0]["calendar_date"]=="20260928"
    assert events[0]["trading_day"] is True
    assert events[1]["calendar_date"]=="20260929"
    assert events[1]["trading_day"] is False
