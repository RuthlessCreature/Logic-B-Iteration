from __future__ import annotations

from datetime import datetime
import pandas as pd


class FutureDataLeakError(RuntimeError):
    pass


def assert_available_at(
    frame: pd.DataFrame,
    decision_time: datetime,
    available_col: str = "available_at",
) -> None:
    if available_col not in frame.columns:
        raise FutureDataLeakError(
            f"missing {available_col}; point-in-time safety cannot be verified"
        )
    available = pd.to_datetime(frame[available_col], errors="raise")
    leaked = frame[available > decision_time]
    if not leaked.empty:
        raise FutureDataLeakError(
            f"{len(leaked)} rows become available after decision_time={decision_time.isoformat()}"
        )
