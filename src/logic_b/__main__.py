"""Offline CLI for deterministic replay; live trading is deliberately unsupported."""
import argparse
import csv
import json
from pathlib import Path

from .replay import replay

def main():
    p = argparse.ArgumentParser(description="Logic-B historical cash-equity research")
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--config", type=Path, default=Path("config/research.json"))
    p.add_argument("--out", type=Path, default=Path("runs/replay"))
    args = p.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    result = replay(dataset, cfg)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, key in (("orders.csv", "orders"), ("fills.csv", "fills"), ("daily_equity.csv", "daily_equity"),
                      ("closed_trades.csv", "closed_trades"), ("yearly.csv", "yearly")):
        rows = result[key]
        if not rows:
            continue
        keys = sorted({k for row in rows for k in row})
        with (args.out / name).open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({k: result[k] for k in ("classification", "status", "initial_cash", "final_equity",
                                              "return_pct", "max_drawdown_pct")}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
