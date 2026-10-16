"""Only local shadow decision review. No HTTP requests or broker orders."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from .runtime import RuntimeSnapshot, decide_runtime, load_runtime_config

def main():
    p = argparse.ArgumentParser(description="Logic-B frozen-runtime SHADOW decision simulation")
    p.add_argument("--snapshot", type=Path, default=Path("examples/runtime_shadow_snapshot.json"))
    p.add_argument("--runtime-config", type=Path, default=Path("config/runtime.json"))
    p.add_argument("--strategy", type=Path, default=Path("config/research.json"))
    p.add_argument("--out", type=Path, default=Path("runs/runtime-shadow/decision.json"))
    args = p.parse_args()
    snapshot = RuntimeSnapshot(**json.loads(args.snapshot.read_text(encoding="utf-8")))
    runtime_cfg = load_runtime_config(args.runtime_config)
    research_strategy = json.loads(args.strategy.read_text(encoding="utf-8"))
    result = decide_runtime(snapshot, config=runtime_cfg, research_strategy=research_strategy)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:result[k] for k in (
         "stage","trade_date","action","review_status","reason",
         "advisory_status","model_calls_executed","orders_transmitted")}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
