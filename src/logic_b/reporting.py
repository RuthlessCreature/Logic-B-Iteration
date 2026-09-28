from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _jsonable(v: Any) -> Any:
    if is_dataclass(v):
        return {k:_jsonable(x) for k,x in asdict(v).items()}
    if isinstance(v, dict):
        return {str(k):_jsonable(x) for k,x in v.items()}
    if isinstance(v, (list,tuple)):
        return [_jsonable(x) for x in v]
    if hasattr(v,"value"):
        return v.value
    if isinstance(v,(datetime,pd.Timestamp)):
        return v.isoformat()
    return v


def _rows(items: list[Any]) -> list[dict]:
    rows=[]
    for item in items:
        row=_jsonable(item)
        if isinstance(row,dict) and isinstance(row.get("evidence"),dict):
            row["evidence_json"]=json.dumps(row.pop("evidence"),ensure_ascii=False,sort_keys=True)
        rows.append(row)
    return rows


def write_run_artifacts(
    *,
    run_dir: str | Path,
    signals: list[Any],
    fills: list[Any],
    trades: list[dict],
    daily_equity: list[dict],
    metrics: dict,
    config: dict,
    metadata: dict | None = None,
) -> Path:
    root=Path(run_dir)
    root.mkdir(parents=True,exist_ok=True)

    sig_rows=_rows(signals)
    fill_rows=_rows(fills)
    pd.DataFrame(sig_rows).to_parquet(root/"signals.parquet",index=False)
    pd.DataFrame(fill_rows).to_parquet(root/"fills.parquet",index=False)
    pd.DataFrame(trades).to_parquet(root/"trades.parquet",index=False)
    pd.DataFrame(daily_equity).to_parquet(root/"daily_equity.parquet",index=False)

    (root/"metrics.json").write_text(json.dumps(_jsonable(metrics),ensure_ascii=False,indent=2),encoding="utf-8")
    (root/"config.json").write_text(json.dumps(_jsonable(config),ensure_ascii=False,indent=2),encoding="utf-8")
    manifest={
        "created_at":datetime.now(timezone.utc).isoformat(),
        "metadata":metadata or {},
        "rows":{
            "signals":len(sig_rows),
            "fills":len(fill_rows),
            "trades":len(trades),
            "daily_equity":len(daily_equity),
        },
    }
    (root/"run_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return root
