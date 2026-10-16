import math
import pandas as pd

from logic_b.metrics import (
    max_consecutive_losses,
    monthly_equity_returns,
    summarize_equity,
)


def test_max_consecutive_losses():
    r=pd.Series([.1,-.02,-.03,.01,-.04,-.05,-.01,.02])
    assert max_consecutive_losses(r)==3


def test_monthly_returns_and_exposure_metrics():
    equity=pd.DataFrame({
        "date":[
            "2026-01-02",
            "2026-01-30",
            "2026-02-27",
            "2026-03-31",
        ],
        "equity":[100.0,110.0,99.0,108.9],
        "holding":[None,"A","A",None],
        "holding_suspended":[False,False,True,False],
    })
    trades=pd.DataFrame({
        "return":[.10,-.10,.10],
        "entry_cost":[1.0,1.0,1.0],
        "exit_cost":[2.0,2.0,2.0],
    })

    out=summarize_equity(
        equity,
        trades,
    )

    assert out["exposure_rate"]==0.5
    assert out["suspended_exposure_rate"]==0.25
    assert out["max_consecutive_losses"]==1.0
    assert round(out["average_win"],6)==0.10
    assert round(out["average_loss"],6)==-0.10
    assert round(out["payoff_ratio"],6)==1.0
    assert out["total_transaction_cost"]==9.0
    assert out["months"]==3.0
    assert out["positive_month_rate"]==2/3
    assert round(out["worst_month_return"],6)==-0.10


def test_single_equity_row_still_reports_exposure():
    equity=pd.DataFrame({
        "date":["2026-01-02"],
        "equity":[100.0],
        "holding":["A"],
        "holding_suspended":[False],
    })
    out=summarize_equity(equity)
    assert out["total_return"]==0.0
    assert out["exposure_rate"]==1.0
