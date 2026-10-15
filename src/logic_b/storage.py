"""Measured local source-cache inventory and optional normalized Parquet export.

All inventories use on-disk byte lengths. The module never reports an estimated
R2 size as actual storage and never copies source rows to public artifacts.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _month_from_day(day: str):
    return day[:7] if isinstance(day, str) and len(day) >= 7 and day[4:5] == "-" else "UNPARTITIONED"


def physical_cache_inventory(root: Path):
    """Inventory local provider-cache files by type and source month."""
    root = Path(root)
    if not root.exists():
        return {"exists": False, "local_root": str(root), "total_files": 0,
                "total_bytes": 0, "by_provider_year": [], "by_source_type_month": [],
                "r2_status": "NOT_CONNECTED", "r2_actual_bytes": None}

    totals: dict[tuple[str, str, str, str], dict] = defaultdict(
        lambda: {"files": 0, "bytes": 0, "rows": 0, "trading_days": set(), "sha256s": set()})
    total_files = total_bytes = 0
    files_by_year: dict[tuple[str, str], dict] = defaultdict(lambda: {"files": 0, "bytes": 0})
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.endswith(".tmp"):
            continue
        rel = path.relative_to(root)
        parts = rel.parts
        size = path.stat().st_size
        file_sha256 = sha256(path.read_bytes()).hexdigest()
        total_files += 1
        total_bytes += size
        if not parts:
            continue
        if parts[0] == "parquet":
            dataset = parts[1] if len(parts) > 1 else "unknown"
            month = path.stem if len(path.stem) == 7 else "UNPARTITIONED"
            provider = {"events": "xuangubao", "daily": "baostock", "minute": "baostock",
                        "calendar": "baostock"}.get(dataset, "derived")
            row = totals[provider, dataset, month, "parquet"]
            row["files"] += 1
            row["bytes"] += size
            row["sha256s"].add(file_sha256)
            if row["rows"] is not None:
                try:
                    import pyarrow.parquet as pq
                    row["rows"] += pq.read_metadata(path).num_rows
                    if "trade_date" in (pq.read_schema(path).names or []):
                        values = pq.read_table(path, columns=["trade_date"])["trade_date"].to_pylist()
                        row["trading_days"].update(str(value)[:10] for value in values if value is not None)
                except ImportError:
                    # Unknown is not zero: local Python may inventory Parquet
                    # without the optional reader installed.
                    row["rows"] = None
            continue

        dataset = parts[1] if parts[0] == "raw" and len(parts) > 1 else parts[0]
        provider = {"events": "xuangubao", "daily": "baostock", "minute": "baostock",
                    "calendar": "baostock", "failures.jsonl": "mixed"}.get(dataset, "local")
        month = "UNPARTITIONED"
        rows = 0
        trading_days: set[str] = set()
        value = _read_json(path) if path.suffix.lower() == ".json" else None
        if dataset == "events" and value is not None:
            day = value.get("date")
            month = _month_from_day(day)
            for key in ("limit_up", "limit_down", "limit_broken"):
                rows += len(value.get(key) or [])
            if day:
                trading_days.add(day)
        elif dataset == "events":
            month = _month_from_day(path.stem)
        elif dataset == "daily" and value is not None:
            records = value.get("records") if isinstance(value.get("records"), dict) else {}
            rows = len(records)
            if len(parts) >= 3 and len(parts[1]) == 7 and parts[1][4] == "-":
                month = parts[1]
                trading_days.update(records)
            else:
                for day in records:
                    trading_days.add(day)
        elif dataset == "minute" and value is not None:
            day = value.get("day") or path.stem
            month = _month_from_day(day)
            rows = len(value.get("bars") or [])
            if day:
                trading_days.add(day)
        elif dataset == "minute":
            month = _month_from_day(path.stem)
        elif dataset == "calendar" and value is not None:
            month = path.stem if len(path.stem) == 7 else "UNPARTITIONED"
            days = value.get("days") or []
            rows = len(days)
            trading_days.update(days)
        elif path.name == "failures.jsonl":
            rows = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        row = totals[provider, dataset, month, "json"]
        row["files"] += 1
        row["bytes"] += size
        row["rows"] += rows
        row["trading_days"].update(trading_days)
        row["sha256s"].add(file_sha256)
        year = month[:4] if len(month) == 7 and month[:4].isdigit() else "UNPARTITIONED"
        year_row = files_by_year[provider, year]
        year_row["files"] += 1
        year_row["bytes"] += size

    detail = []
    for (provider, dataset, month, file_format), value in sorted(totals.items()):
        detail.append({"provider": provider, "dataset": dataset, "year": month[:4] if month[:4].isdigit()
                       else "UNPARTITIONED", "month": month, "format": file_format,
                       "files": value["files"], "physical_bytes": value["bytes"],
                       "mib": round(value["bytes"] / 1048576, 6), "rows": value["rows"],
                       "trading_days": len(value["trading_days"]),
                       "partition_status": "LEGACY_UNPARTITIONED" if month == "UNPARTITIONED" else "MONTH_PARTITIONED",
                       "partition_manifest_sha256": sha256("\n".join(sorted(value["sha256s"])).encode("ascii")).hexdigest(),
                       "r2_actual_bytes": None})
    return {"exists": True, "local_root": str(root), "total_files": total_files,
            "total_bytes": total_bytes, "total_mib": round(total_bytes / 1048576, 6),
            "by_provider_year": [{"provider": p, "year": y, **row}
                                  for (p, y), row in sorted(files_by_year.items())],
            "by_source_type_month": detail,
            "r2_status": "NOT_CONNECTED", "r2_actual_bytes": None,
            "storage_note": "Measured local file sizes; R2 is separate and not connected"}


def _month_parquet_rows(root: Path):
    root = Path(root)
    result = {"events": defaultdict(list), "daily": defaultdict(list),
              "minute": defaultdict(list), "calendar": defaultdict(list)}
    for path in sorted((root / "events").glob("*.json")) if (root / "events").exists() else []:
        value = _read_json(path)
        if value is None:
            continue
        day = value.get("date", "")
        month = _month_from_day(day)
        source_hash = sha256(path.read_bytes()).hexdigest()
        for pool, key in (("limit_up", "limit_up"), ("limit_down", "limit_down"),
                          ("broken", "limit_broken")):
            for item in value.get(key) or []:
                result["events"][month].append({"trade_date": day, "pool": pool,
                    "symbol": item.get("symbol"), "limit_up_days": item.get("limit_up_days"),
                    "break_limit_up_times": item.get("break_limit_up_times"),
                    "name": item.get("name"), "source_sha256": source_hash})
        market = value.get("market") or {}
        result["events"][month].append({"trade_date": day, "pool": "market",
            "market_temperature": market.get("market_temperature"), "source_sha256": source_hash})

    daily_root = root / "daily"
    monthly_files = sorted(daily_root.glob("*/*.json")) if daily_root.exists() else []
    monthly_by_code: dict[str, set[str]] = defaultdict(set)
    for path in monthly_files:
        if len(path.parent.name) == 7 and path.parent.name[4] == "-":
            monthly_by_code[path.stem].add(path.parent.name)
    legacy_files = sorted(daily_root.glob("*.json")) if daily_root.exists() else []
    for path in monthly_files + legacy_files:
        value = _read_json(path)
        if value is None:
            continue
        source_hash = sha256(path.read_bytes()).hexdigest()
        for day, item in (value.get("records") or {}).items():
            month = _month_from_day(day)
            if path.parent != daily_root and path.parent.name == month:
                # Monthly partition is authoritative for its covered month.
                pass
            elif path.parent == daily_root and month in monthly_by_code