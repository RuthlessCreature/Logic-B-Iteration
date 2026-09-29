import json
from pathlib import Path

import pytest
import yaml

from logic_b.research_request import append_github_env,load_research_request


CFG={
    "research":{
        "development_end":"2026-06-30",
    }
}


def write_request(tmp_path,payload):
    p=tmp_path/"request.json"
    p.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return p


def base_request():
    return {
        "request_id":"pilot",
        "window":{
            "start":"2025-01-02",
            "end":"2025-01-27",
        },
        "preflight_date":"2025-01-27",
        "fill":"all",
        "blind_holdout":False,
    }


def test_valid_request_is_normalized(tmp_path):
    p=write_request(
        tmp_path,
        base_request(),
    )
    spec=load_research_request(
        p,
        config=CFG,
    )
    assert spec.request_id=="pilot"
    assert spec.start=="2025-01-02"
    assert spec.end=="2025-01-27"
    assert spec.preflight_date=="2025-01-27"
    assert spec.fill=="all"


def test_holdout_request_is_rejected(tmp_path):
    payload=base_request()
    payload["window"]["end"]="2026-07-01"
    p=write_request(
        tmp_path,
        payload,
    )
    with pytest.raises(
        ValueError,
        match="development_end",
    ):
        load_research_request(
            p,
            config=CFG,
        )


def test_preflight_must_be_inside_window(tmp_path):
    payload=base_request()
    payload["preflight_date"]="2025-02-05"
    p=write_request(
        tmp_path,
        payload,
    )
    with pytest.raises(
        ValueError,
        match="preflight_date",
    ):
        load_research_request(
            p,
            config=CFG,
        )


def test_fill_is_frozen_enum(tmp_path):
    payload=base_request()
    payload["fill"]="best"
    p=write_request(
        tmp_path,
        payload,
    )
    with pytest.raises(
        ValueError,
        match="unsupported fill",
    ):
        load_research_request(
            p,
            config=CFG,
        )


def test_blind_holdout_flag_is_never_allowed(tmp_path):
    payload=base_request()
    payload["blind_holdout"]=True
    p=write_request(
        tmp_path,
        payload,
    )
    with pytest.raises(
        ValueError,
        match="blind holdout",
    ):
        load_research_request(
            p,
            config=CFG,
        )


def test_github_env_writer_emits_required_fields(tmp_path):
    p=write_request(
        tmp_path,
        base_request(),
    )
    spec=load_research_request(
        p,
        config=CFG,
    )
    env=tmp_path/"env"
    append_github_env(
        spec,
        env,
    )
    text=env.read_text(
        encoding="utf-8",
    )
    assert "REQUEST_ID=pilot" in text
    assert "RUN_START=2025-01-02" in text
    assert "RUN_END=2025-01-27" in text
    assert "PREFLIGHT_DATE=2025-01-27" in text
    assert "FILL_MODEL=all" in text
