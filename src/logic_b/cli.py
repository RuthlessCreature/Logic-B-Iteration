from __future__ import annotations
import argparse, json
from pathlib import Path
import yaml
from .features import classify_market_regime


def main() -> int:
    parser=argparse.ArgumentParser(prog="logic-b")
    sub=parser.add_subparsers(dest="cmd",required=True)
    sub.add_parser("smoke")
    p=sub.add_parser("validate-config"); p.add_argument("path")
    args=parser.parse_args()
    if args.cmd=="smoke":
        r=classify_market_regime(limit_up_count=72,limit_down_count=4,break_rate=.16,max_height=7,prev_limit_median_return=.021)
        print(json.dumps({"status":"ok","example_regime":r.value},ensure_ascii=False)); return 0
    cfg=yaml.safe_load(Path(args.path).read_text(encoding="utf-8"))
    required=["version","universe","portfolio","execution","research"]
    missing=[k for k in required if k not in cfg]
    if missing: raise SystemExit(f"missing config keys: {missing}")
    print(json.dumps({"status":"ok","version":cfg["version"]},ensure_ascii=False)); return 0


if __name__=="__main__":
    raise SystemExit(main())
