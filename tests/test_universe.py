import pandas as pd
import pytest

from logic_b.universe import (
    board_of,
    codes_with_valid_price_limits,
    filter_boards,
)


@pytest.mark.parametrize(
    ("code","board"),
    [
        ("600000.SH","main"),
        ("605000.SH","main"),
        ("000001.SZ","main"),
        ("002001.SZ","main"),
        ("688001.SH","star"),
        ("300001.SZ","chinext"),
        ("301001.SZ","chinext"),
        ("920001.BJ","other"),
    ],
)
def test_board_classification(code,board):
    assert board_of(code)==board


def test_filter_boards_excludes_bse_and_unselected_boards():
    frame=pd.DataFrame({
        "ts_code":[
            "600000.SH",
            "300001.SZ",
            "688001.SH",
            "920001.BJ",
        ]
    })
    out=filter_boards(
        frame,
        ["main","star"],
    )
    assert set(out["ts_code"])=={
        "600000.SH",
        "688001.SH",
    }


def test_valid_price_limits_exclude_missing_or_unordered_rows():
    frame=pd.DataFrame({
        "ts_code":["A","B","C","D"],
        "up_limit":[11.0,None,9.0,0.0],
        "down_limit":[9.0,8.0,10.0,0.0],
    })
    assert codes_with_valid_price_limits(frame)=={"A"}
