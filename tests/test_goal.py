"""Active Luna 2025/2026 dataset, visible curves and physical storage evidence."""
import copy
import json
from pathlib import Path
import pytest

from logic_b.goal import execute_goal, split_days, physical_storage_inventory
from logic_b.research import study_boundaries, training_summary, compare_candidate
from logic_b.replay import replay

CFG=json.loads(Path("config/goal_2025_2026.json").read_text(encoding="utf-8"))
SAMPLE=json.loads(Path("examples/goal_toy_2025_2026.json").read_text(encoding="utf-8"))
PROP=json.loads(Path("examples/proposal_example.json").read_text(encoding="utf-8"))

def test_active_goal_split_and_legacy_unchanged():
    assert study_boundaries(CFG)==("2025-01-01","2025-12-31","2026-01-01","2026-06-30")
    assert training_summary(SAMPLE,CFG)["training_end"]=="2025-12-31"
    assert training_summary(SAMPLE,CFG)["sessions"]==7
    legacy=json.loads(Path("config/research.json").read_text())
    assert legacy["start"]=="2020-01-01"
    assert len(split_days(SAMPLE,CFG)[1])==6

def test_active_goal_rejects_other_period_and_protected():
    ds=copy.deepcopy(SAMPLE)
    ds["days"][0]["date"]="2024-12-31"
    with pytest.raises(ValueError,match="active Goal"):
        split_days(ds,CFG)
    ds=copy.deepcopy(SAMPLE)
    ds["days"][-1]["date"]="2026-07-01"
    with pytest.raises(ValueError,match="active Goal"):
        split_days(ds,CFG)
    with pytest.raises(ValueError,match="outside-range"):
        replay({"days":[{"date":"2020-01-02"}]},CFG)

def test_2026_is_never_used_to_pick_training_winner(tmp_path):
    x=execute_goal(SAMPLE,CFG,[PROP],tmp_path/"first",tmp_path/"data")
    ds=copy.deepcopy(SAMPLE)
    for row in ds["days"]:
        if row["date"]>="2026-01-01":
            row["daily"]["600001.SH"]["close"]=8.5  # deliberately invalid simulated economics in 2026
    y=execute_goal(ds,CFG,[PROP],tmp_path/"second",tmp_path/"data")
    assert x["frozen_selection"]["selected_from_training_only"]==y["frozen_selection"]["selected_from_training_only"]
    assert x["train_iterations"]==y["train_iterations"]
    assert x["frozen_selection"]["version_digest"]==y["frozen_selection"]["version_digest"]

def test_chart_and_iteration_outputs_are_real_files_and_labeled_synthetic(tmp_path):
    data=tmp_path/"data"/"raw"/"events"
    data.mkdir(parents=True)
    (data/"2025-01-02.json").write_bytes(b"x"*31)
    (data/"2026-01-02.json").write_bytes(b"x"*47)
    result=execute_goal(SAMPLE,CFG,[PROP],tmp_path/"out",tmp_path/"data")
    assert result["classification"]=="SYNTHETIC_FIXTURE_NOT_TRADING_PROOF"
    assert result["status"]=="NOT_FULLY_VALIDATED"
    assert result["follow"]=="NO_FOLLOW"
    assert len(result["train_iterations"])==2
    for name in ("dashboard.html","training_equity.svg","validation_equity.svg",
                 "iteration_history.json","iteration_history.csv","goal_report.json",
                 "storage_inventory.json","training_equity.csv","validation_equity.csv",
                 "frozen_selection.json"):
        assert (tmp_path/"out"/name).is_file()
    storage=result["storage"]
    assert storage["total_bytes"]==78
    assert storage["total_files"]==2
    assert {r["year"] for r in storage["by_provider_year"]}=={"2025","2026"}
    assert storage["r2_actual_bytes"] is None
    assert "合成演示数据" in (tmp_path/"out"/"dashboard.html").read_text()
    assert "2025" in (tmp_path/"out"/"training_equity.svg").read_text()

def test_validation_boundaries_and_first_day_prior_seed():
    tr,va=split_days(SAMPLE,CFG)
    result=replay({"days":va,"prior_completed_day":tr[-1]},CFG)
    assert result["daily_equity"][0]["day"]=="2026-01-02"
    assert result["initial_cash"]==10000
    with pytest.raises(ValueError,match="invalid prior completed"):
        replay({"days":va,"prior_completed_day":va[-1]},CFG)

def test_study_compare_candidate_active_split():
    result=compare_candidate(SAMPLE,CFG,PROP)
    assert result["time_split"]=={
        "train_start":"2025-01-01","train_end":"2025-12-31",
        "validation_start":"2026-01-01","validation_end":"2026-06-30"
    }
    assert result["verdict"]=="NO_FOLLOW"
