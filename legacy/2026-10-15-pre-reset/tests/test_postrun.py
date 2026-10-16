import json

import pandas as pd

from logic_b.postrun import analyze_run


def test_postrun_attributes_losses_and_unfilled_reasons():
    signals=pd.DataFrame({
        "trade_date":["20260928","20260929","20260930"],
        "ts_code":["A",None,"B"],
        "action":["BUY_CORE","CASH","BUY_CORE"],
        "market_regime":["TRIAL","ICE","ATTACK"],
        "core_type":["TOTAL_MARKET_LEADER","NONE","TURNOVER_FRONT"],
        "candidate_score":[.8,0,.7],
        "confirmation_score":[.7,0,.65],
        "tradability_score":[.8,0,.7],
        "risk_score":[.2,1,.3],
        "evidence_json":[
            json.dumps({"gate":None}),
            json.dumps({"gate":"market_regime_blocked"}),
            json.dumps({"gate":None}),
        ],
    })
    fills=pd.DataFrame({
        "ts_code":["A","A","B"],
        "side":["BUY","SELL","BUY"],
        "filled":[True,False,False],
        "reason":["first_openable_post_signal_bar","locked_limit_down","sealed_limit_no_open"],
    })
    trades=pd.DataFrame({
        "ts_code":["A","B"],
        "entry_time":["2026-09-28 09:36:00","2026-09-30 09:36:00"],
        "entry_price":[10.0,20.0],
        "exit_time":["2026-09-29 09:36:00","2026-10-09 09:36:00"],
        "exit_price":[9.2,21.0],
        "net_return":[-.081,.01],
        "exit_rule":["E0","E0"],
    })

    summary,attribution=analyze_run(
        signals=signals,
        fills=fills,
        trades=trades,
    )

    assert summary["unfilled_fills"]==2
    assert summary["losing_trades"]==1
    assert summary["tail_losses_le_minus_5pct"]==1
    reasons={
        row["reason"]:row["count"]
        for row in summary["unfilled_by_reason"]
    }
    assert reasons["locked_limit_down"]==1
    assert reasons["sealed_limit_no_open"]==1

    gates={
        row["gate_reason"]:row["count"]
        for row in summary["cash_by_gate"]
    }
    assert gates["market_regime_blocked"]==1
    assert attribution.iloc[0]["ts_code"]=="A"
    assert attribution.iloc[0]["market_regime"]=="TRIAL"
