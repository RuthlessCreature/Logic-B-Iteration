from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import pytest
from logic_b.v05_research import FEATURES
from logic_b.v05_aggregate import sanitize_training_events,merge_monthly_features

def sample(trading_day="2025-01-06"):
    row={"trade_date":trading_day,"outcome_date":"2025-01-07","label":1,
         "code":"002820","entry_reference_price":12.3}
    for n,col in enumerate(FEATURES):row[col]=float(1+n)
    return pd.DataFrame([row])

def test_no_raw_vendor_candles_or_symbols_in_model_export():
    f=sanitize_training_events(sample())
    assert "code" not in f.columns
    assert "entry_reference_price" not in f.columns
    assert set(f.columns)=={"trade_date","outcome_date","label",*FEATURES}

def test_future_labels_and_blind_holdout_fail_closed():
    x=sample()
    x["outcome_date"]=x["trade_date"]
    with pytest.raises(ValueError,match="LABEL_MUST_FOLLOW_SIGNAL_DATE"):
        sanitize_training_events(x)
    x=sample()
    x["trade_date"]="2026-07-01";x["outcome_date"]="2026-07-02"
    with pytest.raises(ValueError,match="BLIND_HOLDOUT_LOCKED"):
        sanitize_training_events(x)

def test_monthly_shards_are_aggregated_with_duplicate_events_removed(tmp_path):
    for shard in ["jan","feb"]:
        base=tmp_path/shard
        (base/"public").mkdir(parents=True)
        sample().drop(columns=["code","entry_reference_price"]).to_csv(base/"public"/"features.csv",index=False)
        (base/"quality.json").write_text(json.dumps({"candidate_stock_days":10,"missing_or_bad":0}))
    out,report=merge_monthly_features(tmp_path,expected_segments=2)
    assert len(out)==1
    assert report["shards"]==2
    assert report["rows_after_dedup"]==1
    assert report["candidate_stock_days"]==20

def test_missing_or_bad_shard_data_is_not_silently_dropped(tmp_path):
    with pytest.raises(ValueError,match="MISSING_SEGMENTS"):
        merge_monthly_features(tmp_path,expected_segments=3)
    p=tmp_path/"jan"/"public"
    p.mkdir(parents=True)
    sample().drop(columns=["code","entry_reference_price"]).to_csv(p/"features.csv",index=False)
    (p.parent/"quality.json").write_text(json.dumps({"candidate_stock_days":10,"missing_or_bad":2}))
    with pytest.raises(ValueError,match="SHARD_SOURCE_ERRORS"):
        merge_monthly_features(tmp_path,expected_segments=1)
