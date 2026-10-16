import json
from pathlib import Path
from logic_b.runtime_cli import main

def test_shadow_cli_without_codex_or_provider_calls(monkeypatch,tmp_path,capsys):
    output=tmp_path/"decision.json"
    monkeypatch.setattr("sys.argv", ["logic_b.runtime_cli","--out",str(output)])
    main()
    r=json.loads(output.read_text())
    assert r["review_status"]=="NO_FOLLOW"
    assert r["reason"]=="STRATEGY_NOT_PROMOTED"
    assert r["orders_transmitted"]==0
    assert r["model_calls_executed"]==0
    assert r["advisory_status"]=={"jev":"DISABLED","deepseek":"DISABLED"}
    assert "NO_FOLLOW" in capsys.readouterr().out
