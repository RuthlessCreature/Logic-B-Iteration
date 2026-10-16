"""Predeclared 2025-only Logic-A-style early-confirmation experiments.

Reads one private, expanded 2025 candidate-path snapshot. Writes aggregate
statistics and equity curves only; no symbol-level prices/orders are exported.
This remains bar-close research, not PIT-certified or broker-fill evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from logic_b.replay import replay
from logic_b.strategy import select_core
from luna_goal_train import _load_2025


VARIANTS = [
    {"id": "R2_LEADER_ONLY", "params": {"leader_only": True},
     "hypothesis": "选择昨日排序第一核心，若不合格则空仓，不以后排递补。"},
    {"id": "R2_CONFIRM_0PCT", "params": {"leader_only": True, "entry_confirmation_pct": 0.0},
     "hypothesis": "昨日核心须在09:35 bar收盘不低于前收，作为早盘承接代理。"},
    {"id": "R2_CONFIRM_1PCT", "params": {"leader_only": True, "entry_confirmation_pct": 1.0},
     "hypothesis": "昨日核心须在09:35 bar收盘较前收至少上涨1%，过滤弱承接。"},
    {"id": "R2_CONFIRM_2PCT", "params": {"leader_only": True, "entry_confirmation_pct": 2.0},
     "hypothesis": "昨日核心须在09:35 bar收盘较前收至少上涨2%，作为更强承接门槛。"},
    {"id": "R2_CONFIRM_1PCT_MARKET_VETO", "params": {
        "leader_only": True, "entry_confirmation_pct": 1.0,
        "min_market_temperature": 40, "max_breaks": 1},
     "hypothesis": "1%早盘确认叠加前一日情绪温度>=40及核心炸板次数<=1。"},
]


def _summary(result: dict, params: dict, hypothesis: str, data_sha: str) -> dict:
    fills = result["fills"]
    reasons = {}
    for order in result["orders"]:
        reason = order.get("reason", "UNKNOWN")
        reasons[reason] = reasons.get(reason, 0) + 1
    score = None
    if result["return_pct"] is not None and result["max_drawdown_pct"] is not None:
        score = round(result["return_pct"] + 0.5 * result["max_drawdown_pct"], 6)
    return {
        "hypothesis": hypothesis,
        "parameters": params,
        "snapshot_sha256": data_sha,
        "classification": result["classification"],
        "coverage_status": result["status"],
        "initial_cash_cny": result["initial_cash"],
        "final_equity_cny": result["final_equity"],
        "bar_model_return_pct": result["return_pct"],
        "bar_model_max_drawdown_pct": result["max_drawdown_pct"],
        "exploratory_train_score_return_plus_half_mdd": score,
        "verified_executable_return_pct": None,
        "verified_executable_max_drawdown_pct": None,
        "sessions": len(result["daily_equity"]),
        "closed_trades": len(result["closed_trades"]),
        "buy_fills": sum(x["side"] == "BUY" for x in fills),
        "sell_fills": sum(x["side"] == "SELL" for x in fills),
        "fees_cny": round(sum(sum((x.get("fees") or {}).values()) for x in fills), 6),
        "cash_days": sum(x.get("symbol") is None for x in result["daily_equity"]),
        "limit_up_no_fills": reasons.get("NO_FILL_LIMIT_UP", 0),
        "limit_down_no_fills": reasons.get("NO_FILL_LIMIT_DOWN", 0),
        "order_reasons": reasons,
        "unreconciled_corporate_action_count": len(result.get("account_unresolved_corporate_actions", [])),
        "account_mark_reconciled": result.get("economically_reconciled", False),
        "execution_classification": "BAR_CLOSE_SIMULATION_NOT_REAL_FILL",
        "pit_0935_certified": False,
        "promotion": "NO_FOLLOW_DATA_GATES_UNRESOLVED",
    }


def _equity_svg(curves: list[dict]) -> str:
    colors = ["#2563eb", "#059669", "#ea580c", "#9333ea", "#dc2626"]
    versions = list(dict.fromkeys(row["version"] for row in curves))
    grouped = {version: [row["equity_cny"] for row in curves if row["version"] == version]
               for version in versions}
    values = [value for rows in grouped.values() for value in rows]
    low, high = min(values), max(values)
    if high <= low:
        high = low + 1
    width, height, left, right, top, bottom = 1100, 440, 75, 25, 40, 90
    plot_w, plot_h = width - left - right, height - top - bottom
    paths = []
    for index, version in enumerate(versions):
        points = grouped[version]
        coords = []
        for i, value in enumerate(points):
            x = left + plot_w * i / max(len(points) - 1, 1)
            y = top + plot_h * (high - value) / (high - low)
            coords.append(f"{x:.1f},{y:.1f}")
        color = colors[index % len(colors)]
        paths.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(coords)}"/>')
        paths.append(f'<text x="{left + (index % 3) * 330}" y="{height - 52 + (index // 3) * 20}" '
                     f'font-family="sans-serif" font-size="13" fill="{color}">{version}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">'
            '<text x="75" y="24" font-family="sans-serif" font-size="17">2025 train · ¥10,000 independent account per version</text>'
            f'<text x="5" y="{top + 5}" font-family="sans-serif" font-size="12">¥{high:,.0f}</text>'
            f'<text x="5" y="{top + plot_h}" font-family="sans-serif" font-size="12">¥{low:,.0f}</text>'
            f'<line x1="{left}" y1="{top + plot_h * (high - 10000) / (high - low):.1f}" '
            f'x2="{width - right}" y2="{top + plot_h * (high - 10000) / (high - low):.1f}" '
            'stroke="#64748b" stroke-dasharray="5 4"/>' + "".join(paths) + "</svg>")


def run(dataset_path: Path, config_path: Path, out_dir: Path) -> dict:
    dataset, data_sha = _load_2025(dataset_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("train_start") != "2025-01-01" or config.get("train_end") != "2025-12-31":
        raise ValueError("round2 requires the fixed 2025 training window")
    dataset["_source_path"] = str(dataset_path.resolve())
    if len(dataset["days"]) != 243 or dataset["days"][0]["date"] != "2025-01-02" \
            or dataset["days"][-1]["date"] != "2025-12-31":
        raise ValueError("unexpected 2025 trading-session sample; expected 243 sessions")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, curves = [], []
    materialized_bar_sets = [bars for day in dataset["days"]
                             for bars in (day.get("bars_5m") or {}).values()]
    materialized_with_0935 = sum(any(bar.get("time") == "09:35" for bar in bars)
                                 for bars in materialized_bar_sets)
    strategy_source_sha = hashlib.sha256(Path("src/logic_b/strategy.py").read_bytes()).hexdigest()
    replay_source_sha = hashlib.sha256(Path("src/logic_b/replay.py").read_bytes()).hexdigest()
    for variant in VARIANTS:
        cfg = json.loads(json.dumps(config))
        cfg["baseline"] = {**config["baseline"], **variant["params"]}
        result = replay(dataset, cfg)
        row = {"version": variant["id"], **_summary(result, variant["params"], variant["hypothesis"], data_sha)}
        target_paths = 0
        target_0935 = 0
        for index in range(1, len(dataset["days"])):
            symbol, _ = select_core(dataset["days"][index - 1], cfg["baseline"])
            if symbol:
                target_paths += 1
                bars = (dataset["days"][index].get("bars_5m") or {}).get(symbol, [])
                target_0935 += int(any(bar.get("time") == "09:35" for bar in bars))
        row["selected_target_paths"] = target_paths
        row["selected_target_paths_with_0935_bar"] = target_0935
        row["selected_target_paths_missing_0935_bar"] = target_paths - target_0935
        row["candidate_strategy_sha256"] = hashlib.sha256(json.dumps({
            "strategy_source": strategy_source_sha, "replay_source": replay_source_sha,
            "params": variant["params"], "hypothesis": variant["hypothesis"]},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        rows.append(row)
        for point in result["daily_equity"]:
            curves.append({"version": variant["id"], "date": point["day"],
                           "equity_cny": point["equity"],
                           "economically_reconciled": point["economically_reconciled"]})
    public_rows = rows
    (out_dir / "round2_summary.json").write_text(json.dumps({
        "classification": "2025_CANDIDATE_POOL_BAR_SIMULATION_NOT_TRADING_PROOF",
        "date_window": ["2025-01-01", "2025-12-31"], "sessions": 243,
        "snapshot_sha256": data_sha, "strategy_source_sha256": strategy_source_sha,
        "replay_source_sha256": replay_source_sha,
        "materialized_5m_symbol_days": len(materialized_bar_sets),
        "materialized_5m_symbol_days_with_0935_bar": materialized_with_0935,
        "bar_0935_present_for_all_materialized_symbol_days": materialized_with_0935 == len(materialized_bar_sets),
        "bar_timestamp_interval_semantics_verified": False,
        "full_market_universe": False, "official_price_limits": False,
        "corporate_actions_fully_reconciled": False, "actual_order_fills": False,
        "target_return_pct": 200.0,
        "target_achieved": False,
        "target_achievement_gate": "Only verified_executable_return_pct can count; official-limit, PIT, universe, corporate-action and actual-fill gates remain false.",
        "decision": "NO_FOLLOW", "versions": public_rows,
    }, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    columns = list(public_rows[0])
    with (out_dir / "round2_summary.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{**row, "order_reasons": json.dumps(row["order_reasons"],
            sort_keys=True, ensure_ascii=False)} for row in public_rows])
    with (out_dir / "round2_equity.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(curves[0]))
        writer.writeheader()
        writer.writerows(curves)
    svg = _equity_svg(curves)
    (out_dir / "round2_equity.svg").write_text(svg, encoding="utf-8")
    table = "".join("<tr>" + "".join(f"<td>{row[key]}</td>" for key in
        ("version", "bar_model_return_pct", "bar_model_max_drawdown_pct", "closed_trades", "fees_cny")) + "</tr>"
        for row in public_rows)
    (out_dir / "round2_dashboard.html").write_text(
        "<!doctype html><html lang=zh><meta charset=utf-8><title>2025 Logic-A round 2</title>"
        "<h1>2025训练：Logic-A早盘承接实验</h1>"
        "<p>候选池价格代理；非全市场覆盖、非PIT认证、非实际成交。目标200%未实现；NO_FOLLOW。</p>"
        + svg + "<table border=1><thead><tr><th>版本</th><th>bar模拟费后收益%</th><th>bar模拟最大回撤%</th>"
        "<th>平仓交易</th><th>费用¥</th></tr></thead><tbody>" + table + "</tbody></table>"
        "<p>详情见 round2_summary.json、round2_summary.csv、round2_equity.csv。</p></html>",
        encoding="utf-8")
    return {"snapshot_sha256": data_sha, "versions": public_rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/goal_2025_2026.json"))
    parser.add_argument("--out", type=Path, default=Path("research/goal_2025_2026/round2"))
    args = parser.parse_args()
    result = run(args.dataset, args.config, args.out)
    print(json.dumps({"snapshot_sha256": result["snapshot_sha256"],
                      "versions": [{"version": r["version"], "bar_model_return_pct": r["bar_model_return_pct"],
                                    "bar_model_max_drawdown_pct": r["bar_model_max_drawdown_pct"],
                                    "closed_trades": r["closed_trades"]} for r in result["versions"]]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
