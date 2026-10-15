from __future__ import annotations

import math
import pandas as pd


KNOWN_BOARDS={"main","chinext","star"}


def board_of(ts_code: str) -> str:
    """Classify A-share board from Tushare code suffix/prefix."""
    code=str(ts_code).upper()
    symbol=code.split(".")[0]
    exchange=code.split(".")[-1] if "." in code else ""

    if exchange=="SH" and symbol.startswith("688"):
        return "star"

    if exchange=="SZ" and (
        symbol.startswith("300")
        or symbol.startswith("301")
    ):
        return "chinext"

    if exchange=="SH" and symbol.startswith("60"):
        return "main"

    if exchange=="SZ" and symbol.startswith(
        ("000","001","002","003")
    ):
        return "main"

    return "other"


def filter_boards(
    frame: pd.DataFrame,
    include_boards: tuple[str,...] | list[str],
) -> pd.DataFrame:
    allowed=set(include_boards)
    unknown=allowed-KNOWN_BOARDS
    if unknown:
        raise ValueError(
            f"unknown boards: {sorted(unknown)}"
        )
    if frame.empty:
        return frame.copy()
    if "ts_code" not in frame.columns:
        raise ValueError(
            "candidate frame missing ts_code"
        )

    out=frame.copy()
    out["_board"]=out["ts_code"].map(
        board_of
    )
    return out[
        out["_board"].isin(allowed)
    ].drop(columns=["_board"])


def codes_with_valid_price_limits(
    limit_prices: pd.DataFrame,
) -> set[str]:
    """Return codes with finite, positive and ordered daily price limits."""
    required={
        "ts_code",
        "up_limit",
        "down_limit",
    }
    missing=required-set(limit_prices.columns)
    if missing:
        return set()

    valid=set()
    for _,row in limit_prices.iterrows():
        try:
            up=float(row["up_limit"])
            down=float(row["down_limit"])
        except (TypeError,ValueError):
            continue
        if (
            not math.isfinite(up)
            or not math.isfinite(down)
            or up<=0
            or down<=0
            or up<=down
        ):
            continue
        valid.add(str(row["ts_code"]))
    return valid
