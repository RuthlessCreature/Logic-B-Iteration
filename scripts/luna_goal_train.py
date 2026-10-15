"""Build the 2025-only Goal comparison and freeze a candidate before 2026 access.

Inputs are private, locally cached normalized datasets. Public outputs contain
aggregate experiment and cache statistics only; vendor rows and detailed
symbol-level ledgers stay under ignored runs/.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import subprocess

from logic_b.goal import digest, _stats, _curve, _svg, _write_csv, _write_storage_reports
from logic_b.replay import replay
from logic_b.storage import physical_cache_inventory, export_normalized_parquet


VERSIONS = [
    {"id": "V0_SIMPLE_STREAK", "hypothesis": "原始昨日涨停候选排序作为负面基线。",
     "mechanism": "候选延续排序代理；不代表完整 Logic A。", "params": None,
     "decision": "BASELINE"},
    {"id": "V1_MARKET_STATE_GATE", "hypothesis": "昨日选股宝 market_temperature < 40 时不新开仓，减少低风险偏好代理状态下的暴露。",
     "mechanism": "仅把供应商温度当作市场风险偏好代理；不声称识别真实心理。",
     "params": {"min_streak": 1, "max_breaks": 100, "min_market_temperature": 40},
     "decision": "TRAIN_EXPLORATORY"},
    {"id": "V2_BREAK_FEEDBACK_VETO", "hypothesis": "在 V1 之外，昨日候选炸板次数 > 1 时拒绝该候选，检验个股负反馈代理是否减少尾部损失。",
     "mechanism": "炸板次数代理接力失败/负反馈；没有订单流或投资者账户数据。",
     "params": {"min_streak": 1, "max_breaks": 1, "min_market_temperature": 40},
     "decision": "TRAIN_EXPLORATORY"},
]


def _load_2025(path: Path):
    raw = path.read_bytes()
    dataset = json.loads(raw.decode("utf-8"))
    if not str(dataset.get("classification", "")).startswith("HISTORICAL_DATA"):
        raise ValueError("training comparison requires a real historical-source dataset, not a synthetic fixture")
    if dataset.get("coverage_complete") is not True:
        raise ValueError("training comparison requires complete target-path daily/minute coverage")
    days = dataset.get("days")
    if not isinstance(days, list) or not days:
        raise ValueError(f"{path} has no dataset.days")
    dates = [row.get("date") for row in days]
    if dates != sorted(set(dates)):
        raise ValueError("2025 dataset dates must be strictly sorted and unique")
    if any(not isinstance(day, str) or not day.startswith("2025-") for day in dates):
        raise ValueError("train-only runner accepts 2025 dates only; validation was not opened")
    return dataset, hashlib.sha256(raw).hexdigest()


def _run_row(version: dict, dataset: dict, base_config: dict, index: int):
    config = json.loads(json.dumps(base_config))
    if version["params"] is not None:
        config["baseline"] = version["params"]
    result = replay({"days": dataset["days"],
                     "coverage_complete": dataset.get("coverage_complete") is True}, config)
    stats = _stats(result)
    fills = result["fills"]
    stats["fees_total"] = round(sum(sum((fill.get("fees") or {}).values()) for fill in fills), 6)
    stats["fee_commission"] = round(sum((fill.get("fees") or {}).get("commission", 0) for fill in fills), 6)
    stats["fee_transfer"] = round(sum((fill.get("fees") or {}).get("transfer", 0) for fill in fills), 6)
    stats["fee_stamp"] = round(sum((fill.get("fees") or {}).get("stamp", 0) for fill in fills), 6)
    stats["turnover_cny"] = round(sum(fill.get("gross", 0) for fill in fills), 6)
    stats["cash_days"] = sum(row.get("symbol") is None for row in result["daily_equity"])
    stats["locked_or_unfilled_limit_up"] = sum(x.get("reason") == "NO_FILL_LIMIT_UP" for x in result["orders"])
    stats["locked_or_unfilled_limit_down"] = sum(x.get("reason") == "NO_FILL_LIMIT_DOWN" for x in result["orders"])
    stats["corporate_action_flags"] = len(result.get("account_unresolved_corporate_actions", []))
    stats["classification"] = result["classification"]
    event_rows = sum(len(day.get(key) or []) for day in dataset["days"]
                     for key in ("limit_up", "limit_down", "limit_broken"))
    daily_symbols = {symbol for day in dataset["days"] for symbol in (day.get("daily") or {})}
    daily_symbol_days = sum(len(day.get("daily") or {}) for day in dataset["days"])
    minute_symbol_days = sum(len(day.get("bars_5m") or {}) for day in dataset["days"])
    minute_bars = sum(len(bars) for day in dataset["days"]
                      for bars in (day.get("bars_5m") or {}).values())
    pipeline_audit_path = Path(dataset.get("_source_path", ""))
    try:
        aggregate = json.loads((pipeline_audit_path.parent / "aggregate.json").read_text(encoding="utf-8"))
        coverage = aggregate.get("coverage", {})
    except (OSError, json.JSONDecodeError):
        coverage = {}
    coverage_summary = {"event_days": len(dataset["days"]), "xuangubao_event_rows": event_rows,
        "unique_daily_symbols": len(daily_symbols), "daily_symbol_days": daily_symbol_days,
        "minute_symbol_days": minute_symbol_days, "minute_bars": minute_bars,
        "coverage_complete_for_version_path_only": dataset.get("coverage_complete") is True,
        "missing_daily_target_days": coverage.get("missing_daily_target_days"),
        "missing_minute_target_days": coverage.get("missing_minute_target_days"),
        "suspended_target_days": coverage.get("suspended_target_days"),
        "unknown_trade_status_target_days": coverage.get("unknown_trade_status_target_days"),
        "event_failures": len(coverage.get("event_failures", [])),
        "daily_failures": len(coverage.get("daily_failures", [])),
        "baostock_retries": coverage.get("baostock_retries"),
        "baostock_api_failures": coverage.get("baostock_api_failures"),
        "baostock_queries": coverage.get("baostock_queries"),
        "calendar_cache": coverage.get("calendar_cache"),
        "events_cache": coverage.get("events_cache"),
        "minute_cache": coverage.get("minute_cache"), "daily_cache": coverage.get("daily_cache"),
        "classification": "CANDIDATE_POOL_PROXY_NOT_FULL_MARKET_PRICE_COVERAGE"}
    # Predeclared training score: after-cost return + 0.5 * signed MDD.
    score = None if stats["return_pct"] is None or stats["max_drawdown_pct"] is None else round(
        stats["return_pct"] + 0.5 * stats["max_drawdown_pct"], 6)
    return {"iteration": index, "version": version["id"],
            "parent_strategy_sha": None if index == 0 else versions_sha(index - 1),
            "candidate_strategy_sha": versions_sha(index),
            "hypothesis": version["hypothesis"], "participant_psychology_mechanism": version["mechanism"],
            "parameters": version["params"] or base_config["baseline"],
            "expected_direction": "降低弱市暴露/失败接力暴露；收益和风险都可能恶化。" if index else "固定参照。",
            "falsification_criteria": "训练风险调整分数不改善，或执行/来源门禁不满足则拒绝晋级。",
            "train": stats, "train_score": score, "source_coverage": coverage_summary,
     "decision": "KEEP_AS_REFERENCE" if index == 0 else "REJECT" if score is not None and score <= 0 else "INCONCLUSIVE",
            "decision_reason": "所有版本只作探索性价格条模拟；官方价限、09:35 PIT、公司行动及全市场候选覆盖门禁未通过，不能成为交易候选。",
            "next_train_experiment": "保留 V0 对照；只有补齐可得性/价格限制证据后才考虑额外版本。",
            "equity": _curve(result), "daily_private": result["daily_equity"],
            "orders_private": result["orders"],
            "fills_private": result["fills"]}


def versions_sha(index: int) -> str:
    version = VERSIONS[index]
    return digest({"version": version, "strategy_source_sha256": hashlib.sha256(
        Path("src/logic_b/strategy.py").read_bytes()).hexdigest()})


def _market_state(days):
    rows = []
    previous_up: set[str] = set()
    previous_down: set[str] = set()
    for i, day in enumerate(days):
        market = day.get("market") or {}
        temp = market.get("market_temperature")
        up_codes = {str(x.get("symbol")) for x in (day.get("limit_up") or []) if x.get("symbol")}
        down_codes = {str(x.get("symbol")) for x in (day.get("limit_down") or []) if x.get("symbol")}
        ups, downs = len(up_codes), len(down_codes)
        continuation_count = len(previous_up & up_codes)
        continuation_rate = continuation_count / len(previous_up) if previous_up else None
        strong_to_down_count = len(previous_up & down_codes)
        down_to_up_repair_count = len(previous_down & up_codes)
        negative_feedback_rate = strong_to_down_count / len(previous_up) if previous_up else None
        repair_rate = down_to_up_repair_count / len(previous_down) if previous_down else None
        try:
            temp = float(temp) if temp is not None else None
        except (TypeError, ValueError):
            temp = None
        if temp is None:
            state = "UNKNOWN"
        elif temp <= 20 and downs >= ups:
            state = "ICE"
        elif temp < 35 or downs > ups:
            state = "RETREAT"
        elif temp >= 65 and ups > downs and (continuation_rate is None or continuation_rate >= .20):
            state = "ATTACK"
        elif temp >= 45 and ups >= downs:
            state = "TRIAL"
        else:
            state = "NEUTRAL"
        next_date = days[i + 1]["date"] if i + 1 < len(days) else None
        rows.append({"date": day["date"], "state_proxy": state,
                     "market_temperature": temp, "limit_up_count": ups,
                     "limit_down_count": downs, "limit_broken_count": len(day.get("limit_broken") or []),
                     "lagged_up_continuation_count": continuation_count,
                     "lagged_up_continuation_rate": continuation_rate,
                     "strong_to_down_feedback_count": strong_to_down_count,
                     "strong_to_down_feedback_rate": negative_feedback_rate,
                     "down_to_up_repair_count": down_to_up_repair_count,
                     "down_to_up_repair_rate": repair_rate,
                     "source_asof": day["date"], "signal_eligible_on": next_date,
                     "publication_time_certified": False,
                     "classification": "CANDIDATE_POOL_PROXY"})
        previous_up, previous_down = up_codes, down_codes
    return rows


def _state_svg(rows):
    colors = {"ATTACK": "#159947", "TRIAL": "#8bc34a", "NEUTRAL": "#94a3b8",
              "RETREAT": "#f59e0b", "ICE": "#dc2626", "UNKNOWN": "#111827"}
    width, height = 1100, 130
    bars = []
    n = max(len(rows), 1)
    bw = width / n
    for i, row in enumerate(rows):
        title = html.escape(f"{row['date']} {row['state_proxy']} temp={row['market_temperature']}")
        bars.append(f'<rect x="{i*bw:.2f}" y="35" width="{max(bw,1):.2f}" height="42" fill="{colors[row["state_proxy"]]}"><title>{title}</title></rect>')
    legend = " · ".join(f'<tspan fill="{c}">{s}</tspan>' for s, c in colors.items())
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">'
            '<text x="12" y="22" font-family="sans-serif" font-size="16">2025 Observable market-state proxy (daily XGB inputs; publication time unverified)</text>'
            + "".join(bars) + f'<text x="12" y="103" font-family="sans-serif" font-size="13">{legend}</text></svg>')


def build_training(v0_path: Path, v1_path: Path, v2_path: Path, config_path: Path,
                   cache_root: Path, out_dir: Path, public_dir: Path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("train_start") != "2025-01-01" or config.get("train_end") != "2025-12-31":
        raise ValueError("unexpected active training boundary")
    paths = [v0_path, v1_path, v2_path]
    loaded = [_load_2025(path) for path in paths]
    datasets = [item[0] for item in loaded]
    hashes = [item[1] for item in loaded]
    for dataset, path in zip(datasets, paths):
        dataset["_source_path"] = str(path.resolve())
    if any([d["date"] for d in x["days"]] != [d["date"] for d in datasets[0]["days"]] for x in datasets[1:]):
        raise ValueError("strategy variants must share the same 2025 session calendar")
    cached_sessions = set()
    for calendar_path in sorted((cache_root / "calendar").glob("*.json")):
        cached_calendar = json.loads(calendar_path.read_text(encoding="utf-8"))
        cached_sessions.update(day for day in cached_calendar.get("days", []) if day.startswith("2025-"))
    if not cached_sessions or cached_sessions != set(d["date"] for d in datasets[0]["days"]):
        raise ValueError("training dataset must match the complete cached 2025 trading calendar")
    out_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    iterations = []
    curves = []
    for i, (version, dataset, data_sha) in enumerate(zip(VERSIONS, datasets, hashes)):
        row = _run_row(version, dataset, config, i)
        row["data_snapshot_sha256"] = data_sha
        row["date_window"] = [dataset["days"][0]["date"], dataset["days"][-1]["date"]]
        row["session_count"] = len(dataset["days"])
        iterations.append(row)
        curves.append((version["id"], row["equity"]))
        # Private details are preserved locally for audit, never uploaded.
        (out_dir / f"{version['id']}_private_ledger.json").write_text(json.dumps(
            {k: row[k] for k in ("orders_private", "fills_private", "daily_private")}, ensure_ascii=False,
            indent=2, allow_nan=False) + "\n", encoding="utf-8")

    strategy_src_sha = hashlib.sha256(Path("src/logic_b/strategy.py").read_bytes()).hexdigest()
    config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    code_sha = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    # Hard execution/source gates fail closed. This is the pre-validation freeze.
    frozen = {"status": "NO_CANDIDATE", "selected_strategy": None,
              "selected_for_validation": None, "selection_rule": "training_score = net_return_pct + 0.5 * max_drawdown_pct; promotion also requires fully verified PIT, official price limits, corporate-action accounting, and complete candidate coverage",
              "train_window": ["2025-01-01", "2025-12-31"],
              "training_sessions": len(datasets[0]["days"]),
              "versions_evaluated": [r["version"] for r in iterations],
              "training_data_sha256_by_version": {v["id"]: h for v, h in zip(VERSIONS, hashes)},
              "config_sha256": config_sha, "strategy_source_sha256": strategy_src_sha,
              "code_head_before_freeze": code_sha,
              "freeze_created_utc": datetime.now(timezone.utc).isoformat(),
              "gates": {"full_market_candidate_universe": False, "official_per_security_price_limits": False,
                        "historical_0935_pit_certified": False, "corporate_actions_fully_reconciled": False,
                        "broker_fill_evidence": False},
              "reason": "2025 rows support exploratory bar-price simulations only. No strategy qualifies for promotion to 2026 validation economics.",
              "version_digest": digest({"rows": [{k: r[k] for k in ("version", "candidate_strategy_sha", "train_score", "decision")}
                                                   for r in iterations], "config_sha256": config_sha})}
    frozen["selection_sha256"] = digest(frozen)
    (public_dir / "frozen_selection.json").write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Public iteration data is aggregate-only; row-level source prices stay private.
    public_iterations = [{k: r[k] for k in ("iteration", "version", "parent_strategy_sha", "candidate_strategy_sha",
        "hypothesis", "participant_psychology_mechanism", "parameters", "expected_direction",
        "falsification_criteria", "train", "train_score", "decision", "decision_reason", "next_train_experiment",
        "source_coverage", "data_snapshot_sha256", "date_window", "session_count")} for r in iterations]
    (public_dir / "iteration_history.json").write_text(json.dumps(public_iterations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cols = ["iteration", "version", "candidate_strategy_sha", "data_snapshot_sha256", "train_return_pct",
            "train_max_drawdown_pct", "train_score", "completed_trades", "fees_total", "cash_days",
            "limit_up_no_fills", "limit_down_no_fills", "xuangubao_event_rows", "daily_symbol_days",
            "minute_symbol_days", "minute_bars", "missing_minute_target_days", "baostock_retries", "decision"]
    _write_csv(public_dir / "iteration_history.csv", [{"iteration": r["iteration"], "version": r["version"],
        "candidate_strategy_sha": r["candidate_strategy_sha"], "data_snapshot_sha256": r["data_snapshot_sha256"],
        "train_return_pct": r["train"]["return_pct"], "train_max_drawdown_pct": r["train"]["max_drawdown_pct"],
        "train_score": r["train_score"], "completed_trades": r["train"]["completed_trades"],
        "fees_total": r["train"]["fees_total"], "cash_days": r["train"]["cash_days"],
        "limit_up_no_fills": r["train"]["locked_or_unfilled_limit_up"],
        "limit_down_no_fills": r["train"]["locked_or_unfilled_limit_down"],
        "xuangubao_event_rows": r["source_coverage"]["xuangubao_event_rows"],
        "daily_symbol_days": r["source_coverage"]["daily_symbol_days"],
        "minute_symbol_days": r["source_coverage"]["minute_symbol_days"],
        "minute_bars": r["source_coverage"]["minute_bars"],
        "missing_minute_target_days": r["source_coverage"]["missing_minute_target_days"],
        "baostock_retries": r["source_coverage"]["baostock_retries"],
        "decision": r["decision"]} for r in iterations], cols)
    _write_csv(public_dir / "training_equity.csv", [{"version": name, **point}
        for name, points in curves for point in points], ["version", "date", "equity", "reconciled"])
    (public_dir / "training_equity.svg").write_text(_svg(curves, "2025 training · V0, MarketGate V1, Negative-feedback V2"), encoding="utf-8")

    states = _market_state(datasets[0]["days"])
    _write_csv(public_dir / "market_state_2025.csv", states,
               ["date", "state_proxy", "market_temperature", "limit_up_count", "limit_down_count",
                "limit_broken_count", "lagged_up_continuation_count", "lagged_up_continuation_rate",
                "strong_to_down_feedback_count", "strong_to_down_feedback_rate", "down_to_up_repair_count",
                "down_to_up_repair_rate", "source_asof", "signal_eligible_on",
                "publication_time_certified", "classification"])
    (public_dir / "market_state_2025.svg").write_text(_state_svg(states), encoding="utf-8")
    state_lookup = {row["date"]: row for row in states}
    activity_rows = []
    state_groups = {}
    for version, dataset, iteration in zip(VERSIONS, datasets, iterations):
        order_by_day = {}
        for order in iteration["orders_private"]:
            order_by_day.setdefault(order.get("day"), []).append(order)
        fill_fees = {}
        for fill in iteration["fills_private"]:
            fill_fees[fill.get("day")] = fill_fees.get(fill.get("day"), 0.0) + sum((fill.get("fees") or {}).values())
        points = {row["date"]: row for row in iteration["equity"]}
        daily_private = {row["day"]: row for row in iteration["daily_private"]}
        previous_equity = 10000.0
        for i, day in enumerate(dataset["days"]):
            source_state = state_lookup.get(dataset["days"][i - 1]["date"]) if i else None
            market_state = source_state["state_proxy"] if source_state else "UNKNOWN"
            orders = order_by_day.get(day["date"], [])
            point = points[day["date"]]
            account_point = daily_private[day["date"]]
            daily_return = ((point["equity"] / previous_equity - 1) * 100) if previous_equity else None
            row = {"version": version["id"], "trade_date": day["date"],
                   "market_state_asof": market_state,
                   "signal_source_date": source_state["date"] if source_state else None,
                   "publication_time_certified": False,
                   "action_reason": ";".join(sorted({str(x.get("reason")) for x in orders})) or
                                   ("HOLD" if account_point.get("symbol") is not None else "CASH"),
                   "buy_attempts": sum(x.get("side") == "BUY" for x in orders),
                   "sell_attempts": sum(x.get("side") == "SELL" for x in orders),
                   "cash_at_close": account_point["cash"],
                   "position_open_at_close": account_point.get("symbol") is not None,
                   "equity": point["equity"], "daily_mark_return_pct": round(daily_return, 6),
                   "fees_cny": round(fill_fees.get(day["date"], 0.0), 6),
                   "economically_reconciled": point["reconciled"]}
            activity_rows.append(row)
            group = state_groups.setdefault((version["id"], market_state),
                {"version": version["id"], "market_state_asof": market_state, "sessions": 0,
                 "buy_attempts": 0, "sell_attempts": 0, "market_gate_rejections": 0,
                 "fees_cny": 0.0, "cash_days": 0, "equity_marks": []})
            group["sessions"] += 1
            group["buy_attempts"] += row["buy_attempts"]
            group["sell_attempts"] += row["sell_attempts"]
            group["market_gate_rejections"] += sum(x.get("reason") == "MARKET_GATE" for x in orders)
            group["fees_cny"] += row["fees_cny"]
            group["cash_days"] += int(not row["position_open_at_close"])
            group["equity_marks"].append(daily_return)
            previous_equity = point["equity"]
    _write_csv(public_dir / "market_state_activity.csv", activity_rows,
               ["version", "trade_date", "market_state_asof", "signal_source_date",
                "publication_time_certified", "action_reason", "buy_attempts", "sell_attempts",
                "cash_at_close", "position_open_at_close", "equity", "daily_mark_return_pct",
                "fees_cny", "economically_reconciled"])
    state_summary = []
    for group in state_groups.values():
        marks = [x for x in group.pop("equity_marks") if x is not None]
        group["mean_daily_mark_return_pct"] = round(sum(marks) / len(marks), 6) if marks else None
        group["classification"] = "EXPLORATORY_MARK_TO_MARK; NOT_EXECUTABLE_RETURN"
        state_summary.append(group)
    _write_csv(public_dir / "market_state_summary.csv", state_summary,
               ["version", "market_state_asof", "sessions", "buy_attempts", "sell_attempts",
                "market_gate_rejections", "fees_cny", "cash_days", "mean_daily_mark_return_pct", "classification"])

    parquet = export_normalized_parquet(cache_root)
    inventory = physical_cache_inventory(cache_root)
    inventory["parquet_export"] = parquet
    inventory["data_date_window"] = ["2025-01-01", "2025-12-31"]
    inventory["r2_status"] = "NOT_CONNECTED"
    inventory["r2_actual_bytes"] = None
    monthly_rows = [row for row in inventory.get("by_source_type_month", []) if row["year"] == "2025"]
    month_json = sum(row["physical_bytes"] for row in monthly_rows
                     if row["format"] == "json" and row["partition_status"] == "MONTH_PARTITIONED")
    month_parquet = sum(row["physical_bytes"] for row in monthly_rows if row["format"] == "parquet")
    legacy_bytes = sum(row["physical_bytes"] for row in monthly_rows
                       if row["partition_status"] == "LEGACY_UNPARTITIONED")
    inventory["storage_summary"] = {"monthly_json_bytes": month_json,
        "normalized_parquet_bytes": month_parquet,
        "parquet_to_monthly_json_ratio": round(month_parquet / month_json, 6) if month_json else None,
        "parquet_size_reduction_pct": round((1 - month_parquet / month_json) * 100, 2) if month_json else None,
        "legacy_unpartitioned_physical_bytes": legacy_bytes,
        "legacy_note": "100 legacy annual BaoStock daily files overlap month-partitioned rows; included in physical disk total, excluded from monthly coverage row totals."}
    (public_dir / "storage_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_storage_reports(public_dir, inventory)

    manifest = {"classification": "AGGREGATE_ONLY_REAL_SOURCE_PARTIAL_BAR_SIMULATION",
                "code_head_before_freeze": code_sha, "strategy_source_sha256": strategy_src_sha,
                "data_snapshot_sha256_by_version": {v["id"]: h for v, h in zip(VERSIONS, hashes)},
                "config_sha256": config_sha, "train_window": ["2025-01-01", "2025-12-31"],
                "validation_window": ["2026-01-01", "2026-06-30"],
                "validation_accessed": False, "frozen_selection_sha256": frozen["selection_sha256"],
                "providers": {"event": "Xuangubao", "daily_and_5m": "BaoStock"},
                "model_provider": "Codex offline research; no external LLM API",
                "fees": {"commission_rate": 0.00025, "minimum_commission_cny": 5,
                         "stamp_and_transfer": "from repository date-based fee model"},
                "fill_assumption": "completed 09:45 five-minute bar close; simulated, not queue execution",
                "r2_status": "NOT_CONNECTED", "generated_utc": datetime.now(timezone.utc).isoformat()}
    (public_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {"classification": "REAL_VENDOR_DATA_CANDIDATE_POOL_PROXY_NOT_EXECUTABLE_RETURN",
              "status": "NOT_FULLY_VALIDATED", "training": {"window": ["2025-01-01", "2025-12-31"],
                    "sessions": len(datasets[0]["days"]), "iterations": public_iterations},
              "data_evidence": {"calendar_sessions": len(cached_sessions),
                    "xuangubao_event_days": len(datasets[0]["days"]),
                    "xuangubao_event_rows": iterations[0]["source_coverage"]["xuangubao_event_rows"],
                    "daily_symbol_days": iterations[0]["source_coverage"]["daily_symbol_days"],
                    "daily_symbol_count": iterations[0]["source_coverage"]["unique_daily_symbols"],
                    "minute_symbol_days": iterations[0]["source_coverage"]["minute_symbol_days"],
                    "minute_bars": iterations[0]["source_coverage"]["minute_bars"],
                    "monthly_json_bytes": month_json, "normalized_parquet_bytes": month_parquet,
                    "legacy_unpartitioned_bytes": legacy_bytes,
                    "local_total_physical_bytes": inventory["total_bytes"],
                    "cache_failure_counts": {"event": sum(r["source_coverage"]["event_failures"] for r in iterations),
                        "daily": sum(r["source_coverage"]["daily_failures"] for r in iterations),
                        "minute_target": sum(r["source_coverage"]["missing_minute_target_days"] or 0 for r in iterations),
                        "baostock_api": sum(r["source_coverage"]["baostock_api_failures"] or 0 for r in iterations)},
                    "baostock_retries": sum(r["source_coverage"]["baostock_retries"] or 0 for r in iterations),
                    "incremental_cache_activity_by_version": {r["version"]: {
                        "calendar": r["source_coverage"]["calendar_cache"],
                        "events": r["source_coverage"]["events_cache"],
                        "daily": r["source_coverage"]["daily_cache"],
                        "minute": r["source_coverage"]["minute_cache"],
                        "baostock_queries": r["source_coverage"]["baostock_queries"],
                        "baostock_retries": r["source_coverage"]["baostock_retries"],
                        "baostock_failures": r["source_coverage"]["baostock_api_failures"]}
                        for r in iterations},
                    "initial_base_collection_download_counters": "NOT_RECORDED; initial full-range cache predated byte-counter instrumentation.",
                    "r2_status": "NOT_CONNECTED", "r2_actual_bytes": None,
                    "scope": "CANDIDATE_POOL_PROXY_NOT_FULL_MARKET_PRICE_COVERAGE"},
              "validation": {"window": ["2026-01-01", "2026-06-30"], "accessed": False,
                    "status": "NOT_OPENED_BEFORE_TRAINING_FREEZE"},
              "frozen_selection": frozen, "storage": {"physical_bytes": inventory["total_bytes"],
                    "r2_status": "NOT_CONNECTED", "r2_actual_bytes": None},
              "follow": "NO_FOLLOW", "known_limits": [
                  "Data universe is prior-day V0-selected candidate symbols plus vendor-wide event pool summaries, not complete market price universe.",
                  "Xuangubao EOD publication time and 09:35 availability are not certified.",
                  "Price limits are inferred from code/ST rules, not official per-security historical values.",
                  "Corporate actions and real queue fills are not fully verified; 09:45 completed-bar close is a model assumption.",
                  "MarketState labels are observable vendor-data proxies, not investor-psychology measurements."],
              "outputs": ["iteration_history.csv", "iteration_history.json", "training_equity.csv", "training_equity.svg",
                          "market_state_2025.csv", "market_state_2025.svg", "market_state_activity.csv",
                          "market_state_summary.csv", "storage_inventory.json",
                          "coverage_by_month.csv", "storage_growth.svg", "frozen_selection.json", "run_manifest.json"]}
    (public_dir / "goal_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    body = ["<!doctype html><meta charset='utf-8'><title>Logic-B 2025 Goal</title>",
        "<h1>Logic-B · 2025 TRAIN</h1>",
        "<p><b>NOT_FULLY_VALIDATED · NO_FOLLOW.</b> Real vendor input, partial candidate-price universe; 2026H1 not accessed before freeze.</p>",
        f"<p>Training sessions: {len(datasets[0]['days'])}; calendar/event days: {len(cached_sessions)}/{len(datasets[0]['days'])}; private snapshot SHA256: {hashes[0]}.</p>",
        f"<p>Measured local disk: {inventory['total_bytes']:,} bytes ({inventory['total_mib']} MiB), month JSON {month_json:,} bytes, normalized Parquet {month_parquet:,} bytes (ratio {inventory['storage_summary']['parquet_to_monthly_json_ratio']}), legacy duplicate annual cache {legacy_bytes:,} bytes. R2: NOT_CONNECTED / null.</p>",
        "<h2>2025 training iterations</h2><table border='1'><tr><th>Version</th><th>Return %</th><th>MDD %</th><th>Trades</th><th>Fees CNY</th><th>Cash days</th><th>Decision</th></tr>"]
    for row in iterations:
        s = row["train"]
        body.append(f"<tr><td>{html.escape(row['version'])}</td><td>{s['return_pct']}</td><td>{s['max_drawdown_pct']}</td><td>{s['completed_trades']}</td><td>{s['fees_total']}</td><td>{s['cash_days']}</td><td>{row['decision']}</td></tr>")
    body += ["</table><h2>Training equity</h2><img src='training_equity.svg' width='100%'>",
             "<h2>Observable market-state proxy</h2><img src='market_state_2025.svg' width='100%'>",
             "<p>市场心理仅以供应商涨跌停/炸板、延续、强转弱/修复行为做代理；特征在源日期收盘后形成，只可能用于下一交易日，供应商实际发布时间未认证。板块主线/容量核心没有完整历史标签，标记 UNKNOWN。</p>",
             "<h2>Measured local storage growth</h2><img src='storage_growth.svg' width='100%'>",
             "<p><a href='coverage_by_month.csv'>Monthly source/format coverage CSV</a> · <a href='storage_inventory.json'>Measured inventory and partition hashes</a></p>",
             "<h2>Validation</h2><p>Selection frozen as NO_CANDIDATE before 2026H1 retrieval. Validation may be reported INSUFFICIENT if source/execution gates fail.</p>",
             "<h2>Provenance</h2><ul><li>Xuangubao event pools and BaoStock unadjusted daily/5-minute bars.</li><li>Completed 09:45 5m bar-close simulation, never actual queue fills.</li><li>Full-market price coverage, official bands, PIT, corporate actions and broker execution not certified.</li></ul>",
             "</body></html>"]
    (public_dir / "dashboard.html").write_text("\n".join(body), encoding="utf-8")
    return {"report": report, "iterations": iterations, "frozen_selection": frozen,
            "inventory": inventory}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v0", type=Path, required=True)
    parser.add_argument("--v1", type=Path, required=True)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/goal_2025_2026.json"))
    parser.add_argument("--cache", type=Path, default=Path("data/raw"))
    parser.add_argument("--private-out", type=Path, default=Path("runs/goal_2025_2026"))
    parser.add_argument("--public-out", type=Path, default=Path("research/goal_2025_2026"))
    args = parser.parse_args()
    result = build_training(args.v0, args.v1, args.v2, args.config, args.cache,
                            args.private_out, args.public_out)
    print(json.dumps({"status": result["report"]["status"],
                      "sessions": result["report"]["training"]["sessions"],
                      "versions": [{"id": r["version"], "return_pct": r["train"]["return_pct"],
                                   "mdd_pct": r["train"]["max_drawdown_pct"], "decision": r["decision"]}
                                  for r in result["iterations"]],
                      "frozen_selection": result["frozen_selection"]["status"],
                      "training_sha256": result["frozen_selection"]["training_data_sha256_by_version"],
                      "physical_bytes": result["inventory"]["total_bytes"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
