"""Open the 2026H1 development-validation window after a verified training freeze.

The frozen NO_CANDIDATE decision is immutable. In that case this runner reports
only the historical V0 reference curve and marks economic validation insufficient.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from logic_b.goal import _svg, _write_csv
from logic_b.pipeline import _check_dates
from logic_b.storage import export_normalized_parquet, physical_cache_inventory


START, END = "2026-01-01", "2026-06-30"


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _write_storage_svg(rows):
    width, height = 760, 220
    by_month = {}
    for row in rows:
        if row["format"] != "json":
            continue
        month = row["month"]
        aggregate = by_month.setdefault(month, {"month": month, "bytes": 0})
        aggregate["bytes"] += int(row["physical_bytes"])
    months = [by_month[m] for m in sorted(by_month)]
    running, points = 0, []
    for i, row in enumerate(months):
        running += row["bytes"]
        x = 60 + i * (width - 100) / max(len(months) - 1, 1)
        points.append((x, running))
    top = max((p[1] for p in points), default=1)
    coords = " ".join(f"{x:.1f},{height-35-y/top*(height-75):.1f}" for x, y in points)
    labels = "".join(f'<text x="{60+i*(width-100)/max(len(months)-1,1):.1f}" y="{height-12}" font-size="11">{r["month"]}</text>'
                     for i, r in enumerate(months))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        '<text x="12" y="20" font-size="16">2026H1 cumulative measured JSON cache bytes</text>'
        f'<polyline fill="none" stroke="#2563eb" stroke-width="3" points="{coords}"/>'
        f'<text x="12" y="45" font-size="12">Final: {running:,} bytes · local cache only</text>{labels}</svg>')


def _state_svg(states):
    colors = {"ATTACK": "#159947", "TRIAL": "#8bc34a", "NEUTRAL": "#94a3b8",
              "RETREAT": "#f59e0b", "ICE": "#dc2626", "UNKNOWN": "#111827"}
    width, height = 1100, 130
    bw = width / max(len(states), 1)
    bars = []
    for i, row in enumerate(states):
        title = f"{row['date']} {row['state_proxy']} temp={row['market_temperature']}"
        bars.append(f'<rect x="{i*bw:.2f}" y="35" width="{max(bw,1):.2f}" height="42" '
                    f'fill="{colors[row["state_proxy"]]}"><title>{title}</title></rect>')
    legend = " · ".join(colors)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        '<text x="12" y="22" font-family="sans-serif" font-size="16">2026H1 observable market-state proxy · publication time unverified</text>'
        + "".join(bars) + f'<text x="12" y="103" font-family="sans-serif" font-size="13">{legend}</text></svg>')


def build_validation(frozen_path: Path, dataset_path: Path, aggregate_path: Path,
                     ledger_path: Path, cache_root: Path, public_dir: Path,
                     source_head: str | None = None):
    public_dir.mkdir(parents=True, exist_ok=True)
    frozen_bytes = frozen_path.read_bytes()
    frozen = json.loads(frozen_bytes.decode("utf-8"))
    if frozen.get("status") != "NO_CANDIDATE" or frozen.get("selected_strategy") is not None:
        raise ValueError("validation runner expects the immutable NO_CANDIDATE training freeze")
    if frozen.get("train_window") != ["2025-01-01", "2025-12-31"]:
        raise ValueError("unexpected frozen training boundary")
    dataset_bytes = dataset_path.read_bytes()
    dataset = json.loads(dataset_bytes.decode("utf-8"))
    if dataset.get("coverage_complete") is not True:
        raise ValueError("V0 reference dataset is missing target-path data")
    dates = [row.get("date") for row in dataset.get("days", [])]
    if not dates or dates != sorted(set(dates)):
        raise ValueError("validation dates must be non-empty, sorted, unique")
    if any(not isinstance(day, str) or not START <= day <= END for day in dates):
        raise ValueError("validation runner accepts 2026H1 dates only")
    _check_dates(dates[0], dates[-1])
    calendar = set()
    for path in sorted((cache_root / "calendar").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        calendar.update(d for d in value.get("days", []) if START <= d <= END)
    if calendar != set(dates):
        raise ValueError("validation dataset must match the cached complete 2026H1 trading calendar")

    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    stable_days = [{k: day.get(k) for k in ("date", "limit_up", "limit_down", "limit_broken",
                    "market", "daily", "bars_5m")} for day in dataset["days"]]
    input_sha = _digest(stable_days)
    if aggregate.get("input_sha256") != input_sha:
        raise ValueError("pipeline aggregate does not match the private 2026H1 dataset")
    if len(ledger.get("daily_equity", [])) != len(dates):
        raise ValueError("V0 ledger does not contain one equity mark per validation session")

    cache = export_normalized_parquet(cache_root)
    inventory = physical_cache_inventory(cache_root)
    inventory["parquet_export"] = cache
    rows = [r for r in inventory.get("by_source_type_month", [])
            if r["year"] == "2026" and r["month"] <= "2026-06"]
    _write_csv(public_dir / "storage_2026H1_by_month.csv", rows,
        ["provider", "dataset", "year", "month", "format", "files", "physical_bytes",
         "mib", "rows", "trading_days", "partition_status", "partition_manifest_sha256",
         "r2_actual_bytes"])
    growth, running = [], 0
    for month in (f"2026-{i:02d}" for i in range(1, 7)):
        source_rows = [r for r in rows if r["month"] == month and r["format"] == "json"]
        increment = sum(int(r["physical_bytes"]) for r in source_rows)
        running += increment
        growth.append({"month": month, "json_bytes_added": increment,
                       "json_bytes_cumulative": running,
                       "json_files": sum(r["files"] for r in source_rows),
                       "source_rows": sum(r["rows"] or 0 for r in source_rows)})
    _write_csv(public_dir / "storage_growth_2026H1.csv", growth,
        ["month", "json_bytes_added", "json_bytes_cumulative", "json_files", "source_rows"])
    (public_dir / "storage_growth_2026H1.svg").write_text(_write_storage_svg(rows), encoding="utf-8")

    daily = ledger["daily_equity"]
    curve = [{"version": "V0_REFERENCE_ONLY_NO_FROZEN_CANDIDATE", "date": p["day"],
              "equity": p["equity"], "economically_reconciled": p["economically_reconciled"]}
             for p in daily]
    _write_csv(public_dir / "validation_v0_equity.csv", curve,
        ["version", "date", "equity", "economically_reconciled"])
    (public_dir / "validation_v0_equity.svg").write_text(
        _svg([("V0_REFERENCE_ONLY_NO_FROZEN_CANDIDATE", [{"date": p["date"],
             "equity": p["equity"], "reconciled": p["economically_reconciled"]} for p in curve])],
             "2026H1 development validation · V0 reference only · no frozen strategy"), encoding="utf-8")

    # Use only lagged inputs for action context; source publication time remains unverified.
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    from luna_goal_train import _market_state
    states = _market_state(dataset["days"])
    _write_csv(public_dir / "market_state_2026H1.csv", states,
        ["date", "state_proxy", "market_temperature", "limit_up_count", "limit_down_count",
         "limit_broken_count", "lagged_up_continuation_count", "lagged_up_continuation_rate",
         "strong_to_down_feedback_count", "strong_to_down_feedback_rate", "down_to_up_repair_count",
         "down_to_up_repair_rate", "source_asof", "signal_eligible_on",
         "publication_time_certified", "classification"])
    (public_dir / "market_state_2026H1.svg").write_text(_state_svg(states), encoding="utf-8")
    activity = []
    orders_by_day = {}
    for order in ledger.get("orders", []):
        orders_by_day.setdefault(order["day"], []).append(order)
    for i, point in enumerate(daily):
        source = states[i-1] if i else None
        day_orders = orders_by_day.get(point["day"], [])
        activity.append({"trade_date": point["day"], "market_state_asof": source["state_proxy"] if source else "UNKNOWN",
            "signal_source_date": source["date"] if source else None, "publication_time_certified": False,
            "order_reasons": ";".join(sorted({o["reason"] for o in day_orders})) or
                             ("HOLD" if point["symbol"] else "CASH"),
            "position_open_at_close": point["symbol"] is not None, "equity": point["equity"],
            "economically_reconciled": point["economically_reconciled"]})
    _write_csv(public_dir / "market_state_activity_2026H1.csv", activity,
        ["trade_date", "market_state_asof", "signal_source_date", "publication_time_certified",
         "order_reasons", "position_open_at_close", "equity", "economically_reconciled"])

    fees = {k: round(sum((f.get("fees") or {}).get(k, 0.0) for f in ledger.get("fills", [])), 6)
            for k in ("commission", "stamp", "transfer")}
    fees["total"] = round(sum(fees.values()), 6)
    coverage = aggregate["coverage"]
    report = {"classification": "DEVELOPMENT_VALIDATION_V0_REFERENCE_ONLY_NO_FROZEN_CANDIDATE",
        "status": "INSUFFICIENT", "conclusion": "No strategy was selected in 2025; this is V0 reference exploration, not validation of a frozen candidate.",
        "frozen_selection": {"status": frozen["status"], "selection_sha256": frozen["selection_sha256"],
                             "frozen_file_sha256": hashlib.sha256(frozen_bytes).hexdigest(),
                             "selected_strategy": None},
        "validation_window": [START, END], "observed_calendar": [dates[0], dates[-1]],
        "sessions": len(dates), "trading_calendar_complete": len(dates) == len(calendar),
        "validation_input_sha256": input_sha, "dataset_file_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "account": {"initial_cash_cny": ledger["initial_cash"], "final_equity_cny": ledger["final_equity"],
            "return_pct": ledger["return_pct"], "max_drawdown_pct": ledger["max_drawdown_pct"],
            "closed_trades": len(ledger["closed_trades"]), "buy_fills": sum(f["side"] == "BUY" for f in ledger["fills"]),
            "sell_fills": sum(f["side"] == "SELL" for f in ledger["fills"]), "fees_cny": fees,
            "cash_days": sum(not p["symbol"] for p in daily), "held_at_end": bool(daily[-1]["symbol"]),
            "no_fill_limit_up": coverage["planning_outcome_reasons"].get("NO_FILL_LIMIT_UP", 0),
            "no_fill_limit_down": coverage["planning_outcome_reasons"].get("NO_FILL_LIMIT_DOWN", 0),
            "suspended_days": coverage["suspended_target_days"],
            "corporate_action_flags": len(ledger.get("account_unresolved_corporate_actions", [])),
            "unreliable_marks": sum(p["mark_stale"] or p["corporate_action_unreconciled"] for p in daily)},
        "data_evidence": {"xuangubao_event_days": coverage["event_days"],
            "event_failures": len(coverage["event_failures"]), "daily_failures": len(coverage["daily_failures"]),
            "candidate_symbols": coverage["source_codes"], "target_5m_requests": coverage["minute_requested"],
            "target_5m_complete": coverage["minute_with_bars"], "missing_target_5m": coverage["missing_minute_target_days"],
            "suspended_without_minute_request": coverage["suspended_target_days"],
            "baostock_queries": coverage["baostock_queries"], "baostock_retries": coverage["baostock_retries"],
            "baostock_api_failures": coverage["baostock_api_failures"], "cache_activity": {
                "calendar": coverage["calendar_cache"], "events": coverage["events_cache"],
                "daily": coverage["daily_cache"], "minute": coverage["minute_cache"]},
            "source_scope": "Xuangubao event pool + V0 candidate-path BaoStock data; not full-market prices."},
        "storage": {"validation_2026H1_json_bytes": running,
            "validation_2026H1_json_files": sum(r["files"] for r in rows if r["format"] == "json"),
            "local_cache_total_bytes_all_years": inventory["total_bytes"],
            "local_cache_total_files_all_years": inventory["total_files"],
            "normalized_parquet_bytes_2026H1": sum(r["physical_bytes"] for r in rows if r["format"] == "parquet"),
            "r2_status": "NOT_CONNECTED", "r2_actual_bytes": None,
            "initial_interrupted_collection_byte_counters": "UNAVAILABLE; physical source-type/month sizes are measured; only the completed rerun has instrumented new/reused byte counters."},
        "market_state": {"classification": "LAGGED_VENDOR_POOL_PROXY_PUBLICATION_TIME_UNVERIFIED",
            "rows": len(states), "sector_and_true_core_labels": "UNKNOWN"},
        "code_head_before_validation": source_head or subprocess.run(["git", "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip(),
        "follow": "NO_FOLLOW", "limitations": [
            "2026H1 has prior exposure across earlier research and is a development validation period, not blind test.",
            "No strategy was frozen; V0 is reported only as reference and cannot be a selected validation winner.",
            "V0 outputs use simulated 09:45 completed-bar closes, not order queue fills.",
            "Historical official per-security price limits, 09:35 publication-time PIT, and all corporate actions are not verified.",
            "BaoStock prices are V0-path candidates, not a full market universe; R2 is not connected.",
            "The initial interrupted collection did not preserve byte counters; actual local physical bytes are fully measured."],
        "generated_utc": datetime.now(timezone.utc).isoformat()}
    public_dir.mkdir(parents=True, exist_ok=True)
    report["outputs"] = ["validation_report.json", "validation_v0_equity.csv", "validation_v0_equity.svg",
        "market_state_2026H1.csv", "market_state_2026H1.svg", "market_state_activity_2026H1.csv",
        "storage_2026H1_by_month.csv", "storage_growth_2026H1.csv", "storage_growth_2026H1.svg"]
    (public_dir / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dashboard = (public_dir / "dashboard.html").read_text(encoding="utf-8")
    section_marker = "<h2>2026H1 开发验证：冻结状态与 V0 参考</h2>"
    dashboard = dashboard.split(section_marker, 1)[0]
    if "</body>" in dashboard:
        dashboard = dashboard.rsplit("</body>", 1)[0]
    elif "</html>" in dashboard:
        dashboard = dashboard.rsplit("</html>", 1)[0]
    (public_dir / "dashboard.html").write_text(
        dashboard + "\n" + section_marker + "\n"
        f"<p><b>INSUFFICIENT · NO_FOLLOW。</b> 2025冻结结果为 NO_CANDIDATE，因此下图仅是 V0 参考，不是冻结策略验证。"
        f"独立账户 ¥10,000 → ¥{ledger['final_equity']:.2f}（{ledger['return_pct']:.4f}%），"
        f"最大回撤 {ledger['max_drawdown_pct']:.4f}%，{len(ledger['closed_trades'])} 笔平仓，"
        f"费用 ¥{fees['total']:.2f}；涨停未成交 {report['account']['no_fill_limit_up']}，"
        f"跌停未成交 {report['account']['no_fill_limit_down']}，停牌 {report['account']['suspended_days']}。"
        f"2026H1 本地JSON实测 {running:,} bytes；R2 NOT_CONNECTED。</p>\n"
        "<p>验证曲线：<a href='validation_v0_equity.svg'>SVG</a> · "
        "<a href='validation_v0_equity.csv'>CSV</a> · <a href='validation_report.json'>JSON</a></p>\n"
        "<h3>市场状态与 V0 动作</h3><p><a href='market_state_2026H1.svg'>状态 SVG</a> · "
        "<a href='market_state_activity_2026H1.csv'>逐日动作 CSV</a></p>\n" +
        (public_dir / "market_state_2026H1.svg").read_text(encoding="utf-8") +
        "<h3>2026H1 实测缓存累计增长</h3><p><a href='storage_2026H1_by_month.csv'>月度字节/行数</a> · "
        "<a href='storage_growth_2026H1.csv'>累计容量CSV</a></p>\n"+
        (public_dir / "storage_growth_2026H1.svg").read_text(encoding="utf-8") + "\n</body></html>",
        encoding="utf-8")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(public_dir.iterdir())
              if p.is_file() and p.name not in ("validation_manifest.json",)}
    manifest = {"freeze_sha256": report["frozen_selection"]["frozen_file_sha256"],
        "validation_input_sha256": input_sha, "code_head_before_validation": report["code_head_before_validation"],
        "window": [START, END], "validation_accessed_after_freeze_ci": True,
        "artifacts_sha256": hashes, "generated_utc": datetime.now(timezone.utc).isoformat()}
    (public_dir / "validation_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen", type=Path, default=Path("research/goal_2025_2026/frozen_selection.json"))
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("research/goal_2025_2026"))
    parser.add_argument("--source-head", default=None)
    args = parser.parse_args()
    print(json.dumps(build_validation(args.frozen, args.dataset, args.aggregate, args.ledger,
        args.cache, args.out, args.source_head), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
