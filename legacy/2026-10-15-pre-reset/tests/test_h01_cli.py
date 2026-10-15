"""End-to-end CLI smoke with synthesized data; DOES NOT validate real strategy alpha."""
import json

import numpy as np
import pandas as pd

from logic_b.h01_cli import main
from logic_b.storage import LocalParquetStore


def _synthetic_market(tmp_path, periods=28):
    root = tmp_path / "data"
    store = LocalParquetStore(root)
    days = pd.bdate_range("2026-01-05", periods=periods)
    dkeys = days.strftime("%Y%m%d").tolist()
    store.write_frame("calendar", dkeys[0] + "_" + dkeys[-1], pd.DataFrame({
        "cal_date": dkeys, "source": "test"
    }))
    for i, k in enumerate(dkeys):
        codes = [f"{v:06d}.SZ" for v in range(i % 4, i % 4 + 7 + i % 3)]
        store.write_frame(
            "limit_up", k,
            pd.DataFrame({"ts_code": codes, "trade_date": k})
        )
    return root, days


def test_readiness_only_exits_blocked_but_creates_activity(tmp_path):
    root, days = _synthetic_market(tmp_path)
    dest = tmp_path / "report"
    code = main([
        "--data-root", str(root),
        "--start", days[0].strftime("%Y-%m-%d"),
        "--end", days[-1].strftime("%Y-%m-%d"),
        "--out", str(dest),
    ])
    assert code == 2
    assert (dest / "h01_market_activity.parquet").exists()
    status = json.loads((dest / "h01_readiness.json").read_text())
    assert status["status"] == "BLOCKED_MISSING_EXECUTABLE_COHORT_LEDGER"


def test_completed_b0_portfolio_can_feed_h01_without_future_bar(tmp_path):
    root, days = _synthetic_market(tmp_path)
    eq = 1000000 * np.cumprod(
        1 + .003 * np.sin(np.arange(len(days)))
    )
    b0 = tmp_path / "daily_equity.parquet"
    pd.DataFrame({
        "date": days.strftime("%Y%m%d"),
        "equity": eq,
    }).to_parquet(b0, index=False)
    out = tmp_path / "analysis"
    code = main([
        "--data-root", str(root),
        "--start", days[0].strftime("%Y-%m-%d"),
        "--end", days[-1].strftime("%Y-%m-%d"),
        "--b0-daily-equity", str(b0),
        "--initial-cash", "1000000",
        "--out", str(out),
        "--min-train", "10",
        "--min-test", "5",
    ])
    assert code == 0
    result = json.loads((out / "h01_metrics.json").read_text())
    assert result["test_days"] >= 5
    assert result["cohort_id"] == "B0_SIMULATED_FOLLOWERS"
    assert result["cohort_is_actual_investor_pnl"] is False
    assert (out / "h01_predictions.parquet").exists()
