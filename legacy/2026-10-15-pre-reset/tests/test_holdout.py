from datetime import date
import pytest

from logic_b.cli import assert_holdout_access


CFG={
    "research":{
        "blind_holdout_start":"2026-07-01",
        "blind_holdout_end":"2026-09-28",
    }
}


def test_holdout_locked_by_default():
    with pytest.raises(SystemExit,match="blind holdout is locked"):
        assert_holdout_access(
            CFG,
            date(2026,6,1),
            date(2026,7,15),
            unlock=False,
        )


def test_development_window_allowed():
    assert not assert_holdout_access(
        CFG,
        date(2024,9,30),
        date(2026,6,30),
        unlock=False,
    )


def test_holdout_requires_explicit_unlock():
    assert assert_holdout_access(
        CFG,
        date(2026,7,1),
        date(2026,9,28),
        unlock=True,
    )
