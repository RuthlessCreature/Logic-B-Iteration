from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("h02_final_stock_features", SCRIPTS / "h02_final_stock_features.py")
assert SPEC and SPEC.loader
FEATURES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FEATURES)


def weekday_sessions(start: str, stop: str) -> list[str]:
    result = []
    day = date.fromisoformat(start)
    end = date.fromisoformat(stop)
    while day <= end:
        if day.weekday() < 5:
            result.append(day.strftime("%Y%m%d"))
        day += timedelta(days=1)
    return result


def synthetic_inputs():
    days = weekday_sessions("2024-09-20", "2026-01-16")
    up = {}
    down = {}
    for i, day in enumerate(days):
        up[day] = {"SYN-A", "SYN-B"} if i % 4 in (0, 1) else {"SYN-A"}
        down[day] = {"SYN-B"} if i % 11 == 0 else set()
    hashes = {"calendar": {d: "a" * 64 for d in days}, "limit_up": {d: "b" * 64 for d in days}, "limit_down": {d: "c" * 64 for d in days}}
    data = {"calendar_days": days, "limit_up": up, "limit_down": down, "partition_hashes": hashes,
            "manifest_hashes_verified": len(days) * 3, "manifest_hashes_expected": len(days) * 3,
            "archive_hashes": {f"h01-raw-{p}.zip": "d" * 64 for p in ("2024h1", "2024h2", "2025h1", "2025h2", "2026dev")}}
    aux_hashes = {ds: {d: "e" * 64 for d in days} for ds in FEATURES.AUX_DATASETS}
    aux = {
        "limit_break": {d: ({"SYN-B"} if i % 13 == 0 else set()) for i, d in enumerate(days)},
        "market_indicator": {d: {"limit_up_count": len(up[d]), "limit_down_count": len(down[d]),
                                  "limit_up_broken_count": 1, "rise_count": 100, "fall_count": 50,
                                  "market_temperature": 50.0, "yesterday_limit_up_avg_pcp": .02,
                                  "limit_up_broken_ratio": .1,
                                  "last_observed_at_shanghai": f"{d[:4]}-{d[4:6]}-{d[6:]}T15:00:00+08:00"}
                               for d in days},
        "themes": {d: {"SYN-A": {"theme-1"}, "SYN-B": {"theme-2"}} for d in days},
        "aux_hashes": aux_hashes, "archive_sha256": {f"h01-raw-{p}.zip": "d" * 64 for p in ("2024h1", "2024h2", "2025h1", "2025h2", "2026dev")},
        "archive_manifest_verified": len(days) * 3, "archive_manifest_count": len(days) * 3,
    }
    return data, aux


def test_feature_matrix_is_lagged_and_targets_are_separate():
    data, aux = synthetic_inputs()
    summary, rows = FEATURES.analyze_features(data, aux)
    assert rows
    assert summary["feature_time_contract"]["all_feature_last_session_is_strictly_before_outcome"] is True
    assert summary["feature_time_contract"]["historical_publication_time_certified"] is False
    row = next(r for r in rows if r["outcome_date"] == "20250701" and r["ts_code"] == "SYN-A")
    changed = deepcopy(data)
    changed["limit_up"]["20250701"] = set()
    changed["limit_down"]["20250701"] = {"SYN-A"}
    _, new_rows = FEATURES.analyze_features(changed, aux)
    new = next(r for r in new_rows if r["outcome_date"] == "20250701" and r["ts_code"] == "SYN-A")
    feature_names = [name for name in row if name not in {"continuation_D", "down_next_D", "down_three_D_to_D2"}]
    assert {k: row[k] for k in feature_names} == {k: new[k] for k in feature_names}
    assert row["continuation_D"] != new["continuation_D"]


def test_three_day_labels_are_purged_at_every_phase_boundary():
    data, aux = synthetic_inputs()
    _, rows = FEATURES.analyze_features(data, aux)
    by_day = {r["outcome_date"]: r["down_three_D_to_D2"] for r in rows if r["ts_code"] == "SYN-A"}
    for day in ("20250627", "20250630", "20251230", "20251231", "20260115", "20260116"):
        assert by_day[day] is None


def test_predeclared_empty_groups_remain_visible():
    data, aux = synthetic_inputs()
    summary, _ = FEATURES.analyze_features(data, aux)
    groups = summary["outcomes"]["validation_2025H2"]["Y1_D_vendor_limit_up_pool"]["groups"]["streak_x_down5"]["groups"]
    assert [r["level"] for r in groups] == ["1|0", "1|1+", "2|0", "2|1+", "3+|0", "3+|1+"]
    assert all({"candidate_days", "coverage", "rate", "day_block_bootstrap_95pct_ci"} <= set(r) for r in groups)


def test_protected_or_incomplete_calendar_fails_closed():
    data, aux = synthetic_inputs()
    protected = "20260701"
    data["calendar_days"].append(protected)
    data["calendar_days"].sort()
    data["limit_up"][protected] = {"SYN-A"}
    data["limit_down"][protected] = set()
    with pytest.raises(FEATURES.EmpiricalDataError, match="protected"):
        FEATURES.analyze_features(data, aux)

    data, aux = synthetic_inputs()
    del data["limit_down"]["20250701"]
    with pytest.raises(FEATURES.EmpiricalDataError, match="coverage"):
        FEATURES.analyze_features(data, aux)
