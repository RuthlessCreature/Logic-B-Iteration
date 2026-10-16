from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _safe_json(value) -> dict:
    if isinstance(value,dict):
        return value
    if value is None or (
        isinstance(value,float)
        and np.isnan(value)
    ):
        return {}
    try:
        data=json.loads(str(value))
    except (TypeError,ValueError,json.JSONDecodeError):
        return {}
    return data if isinstance(data,dict) else {}


def _group_trade_metrics(
    frame: pd.DataFrame,
    by: str,
) -> list[dict]:
    if frame.empty or by not in frame.columns:
        return []

    rows=[]
    for key,group in frame.groupby(
        by,
        dropna=False,
    ):
        ret=pd.to_numeric(
            group["net_return"],
            errors="coerce",
        ).dropna()
        if ret.empty:
            continue
        losses=ret[ret<0]
        wins=ret[ret>0]
        rows.append({
            by:(
                None
                if pd.isna(key)
                else str(key)
            ),
            "trades":int(len(ret)),
            "win_rate":float(
                (ret>0).mean()
            ),
            "expectancy":float(
                ret.mean()
            ),
            "median_return":float(
                ret.median()
            ),
            "worst_trade":float(
                ret.min()
            ),
            "best_trade":float(
                ret.max()
            ),
            "profit_factor":(
                float(
                    wins.sum()
                    /abs(losses.sum())
                )
                if losses.sum()<0
                else float("inf")
            ),
        })
    return rows


def analyze_run(
    *,
    signals: pd.DataFrame,
    fills: pd.DataFrame,
    trades: pd.DataFrame,
) -> tuple[dict,pd.DataFrame]:
    """Post-run attribution only.

    This function describes where trades/signals failed. It does not suggest or
    tune strategy thresholds.
    """
    sig=signals.copy()
    fill=fills.copy()
    tr=trades.copy()

    if not sig.empty:
        sig["trade_date_key"]=pd.to_datetime(
            sig["trade_date"].astype(str),
            errors="coerce",
        ).dt.strftime("%Y%m%d")
        if "evidence_json" in sig.columns:
            evidence=sig["evidence_json"].map(
                _safe_json
            )
        elif "evidence" in sig.columns:
            evidence=sig["evidence"].map(
                _safe_json
            )
        else:
            evidence=pd.Series(
                [{} for _ in range(len(sig))],
                index=sig.index,
            )
        sig["gate_reason"]=[
            row.get("gate")
            for row in evidence
        ]
    else:
        sig["trade_date_key"]=pd.Series(
            dtype=str
        )
        sig["gate_reason"]=pd.Series(
            dtype=object
        )

    if not tr.empty:
        tr["entry_date_key"]=pd.to_datetime(
            tr["entry_time"],
            errors="coerce",
        ).dt.strftime("%Y%m%d")
        tr["net_return"]=pd.to_numeric(
            tr["net_return"],
            errors="coerce",
        )
        signal_cols=[
            col
            for col in [
                "trade_date_key",
                "ts_code",
                "market_regime",
                "core_type",
                "candidate_score",
                "confirmation_score",
                "tradability_score",
                "risk_score",
            ]
            if col in sig.columns
        ]
        if {
            "trade_date_key",
            "ts_code",
        }.issubset(signal_cols):
            lookup=sig[
                signal_cols
            ].dropna(
                subset=["ts_code"]
            ).drop_duplicates(
                ["trade_date_key","ts_code"],
                keep="last",
            )
            tr=tr.merge(
                lookup,
                left_on=[
                    "entry_date_key",
                    "ts_code",
                ],
                right_on=[
                    "trade_date_key",
                    "ts_code",
                ],
                how="left",
            )

    if not fill.empty:
        fill["filled_bool"]=fill[
            "filled"
        ].astype(bool)
        unfilled=fill[
            ~fill["filled_bool"]
        ].copy()
    else:
        unfilled=fill.copy()

    def counts(
        frame: pd.DataFrame,
        column: str,
    ) -> list[dict]:
        if frame.empty or column not in frame.columns:
            return []
        out=(
            frame[column]
            .fillna("UNKNOWN")
            .astype(str)
            .value_counts(dropna=False)
        )
        return [
            {
                column:str(key),
                "count":int(value),
            }
            for key,value in out.items()
        ]

    cash=(
        sig[
            sig.get(
                "action",
                pd.Series(
                    index=sig.index,
                    dtype=object,
                ),
            ).astype(str)=="CASH"
        ]
        if not sig.empty
        else sig.copy()
    )

    closed=tr.dropna(
        subset=["net_return"]
    ) if not tr.empty else tr.copy()
    losing=closed[
        closed["net_return"]<0
    ].copy() if not closed.empty else closed.copy()
    tail=closed[
        closed["net_return"]<=-0.05
    ].copy() if not closed.empty else closed.copy()

    diagnostics={
        "signals":int(len(sig)),
        "cash_signals":int(len(cash)),
        "fills":int(len(fill)),
        "unfilled_fills":int(len(unfilled)),
        "closed_trades":int(len(closed)),
        "losing_trades":int(len(losing)),
        "tail_losses_le_minus_5pct":int(len(tail)),
        "unfilled_by_side":counts(
            unfilled,
            "side",
        ),
        "unfilled_by_reason":counts(
            unfilled,
            "reason",
        ),
        "cash_by_gate":counts(
            cash,
            "gate_reason",
        ),
        "trade_metrics_by_market_regime":
            _group_trade_metrics(
                closed,
                "market_regime",
            ),
        "trade_metrics_by_core_type":
            _group_trade_metrics(
                closed,
                "core_type",
            ),
    }

    if not closed.empty:
        diagnostics.update({
            "worst_trade":float(
                closed["net_return"].min()
            ),
            "best_trade":float(
                closed["net_return"].max()
            ),
            "loss_rate":float(
                (closed["net_return"]<0).mean()
            ),
            "tail_loss_rate":float(
                (closed["net_return"]<=-0.05).mean()
            ),
        })

    audit_cols=[
        col
        for col in [
            "ts_code",
            "entry_time",
            "entry_price",
            "exit_time",
            "exit_price",
            "net_return",
            "market_regime",
            "core_type",
            "candidate_score",
            "confirmation_score",
            "tradability_score",
            "risk_score",
            "exit_rule",
        ]
        if col in closed.columns
    ]
    attribution=(
        closed[audit_cols]
        .sort_values(
            "net_return",
            ascending=True,
        )
        .reset_index(drop=True)
        if audit_cols
        else pd.DataFrame()
    )
    return diagnostics,attribution


def analyze_run_dir(
    run_dir: str | Path,
) -> tuple[dict,pd.DataFrame]:
    root=Path(run_dir)
    return analyze_run(
        signals=_read_parquet(
            root/"signals.parquet"
        ),
        fills=_read_parquet(
            root/"fills.parquet"
        ),
        trades=_read_parquet(
            root/"trades.parquet"
        ),
    )
