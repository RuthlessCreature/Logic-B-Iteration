import pandas as pd
from logic_b.alignment import compare_human_proxy


def test_human_proxy_alignment_metrics():
    human=pd.DataFrame({
        "trade_date":["20260928","20260929","20260930"],
        "decision_time":[
            "2026-09-28 09:35:00",
            "2026-09-29 09:35:00",
            "2026-09-30 09:35:00",
        ],
        "action":["BUY_CORE","CASH","BUY_CORE"],
        "selected_code":["A",None,"C"],
        "core_type":["TOTAL_MARKET_LEADER","NONE","TURNOVER_FRONT"],
    })
    proxy=pd.DataFrame({
        "trade_date":["20260928","20260929","20260930"],
        "decision_time":[
            "2026-09-28 09:35:00",
            "2026-09-29 09:35:00",
            "2026-09-30 09:35:00",
        ],
        "action":["BUY_CORE","CASH","BUY_CORE"],
        "ts_code":["A",None,"D"],
        "core_type":["TOTAL_MARKET_LEADER","NONE","TURNOVER_FRONT"],
    })
    metrics,audit=compare_human_proxy(human,proxy)
    assert metrics["coverage"]==1.0
    assert metrics["action_agreement"]==1.0
    assert metrics["selection_agreement"]==0.5
    assert metrics["core_type_agreement"]==1.0
    assert len(audit)==3
