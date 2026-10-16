from __future__ import annotations

import re
import pandas as pd

from .features import parse_board_height, percentile_rank


_THEME_SPLIT=re.compile(r"[、,，;/|]+") 


def split_themes(value: object) -> list[str]:
    if value is None or (isinstance(value,float) and pd.isna(value)):
        return []
    return [x.strip() for x in _THEME_SPLIT.split(str(value)) if x.strip()]


def build_prev_day_theme_evidence(kpl_limit_df: pd.DataFrame) -> pd.DataFrame:
    """Convert D-1 KPL limit-up themes into per-stock point-in-time evidence.

    KPL D-1 ranking is vendor-published before D open. We intentionally avoid
    THS current-membership data here because that dataset is latest-only and
    would leak future constituent changes into historical replay.
    """
    cols=[
        "ts_code","theme_name","theme_limit_up_count","theme_max_height",
        "theme_total_amount","theme_strength","has_theme_evidence",
    ]
    if kpl_limit_df is None or kpl_limit_df.empty or "ts_code" not in kpl_limit_df.columns:
        return pd.DataFrame(columns=cols)

    rows=[]
    for _,r in kpl_limit_df.iterrows():
        code=str(r["ts_code"])
        themes=split_themes(r.get("theme"))
        height=parse_board_height(r.get("status",r.get("tag","首板")))
        amount=float(pd.to_numeric(pd.Series([r.get("amount",0.0)]),errors="coerce").fillna(0).iloc[0])
        for theme in themes:
            rows.append({
                "ts_code":code,
                "theme_name":theme,
                "height":height,
                "amount":amount,
            })
    if not rows:
        return pd.DataFrame(columns=cols)

    long=pd.DataFrame(rows).drop_duplicates(["ts_code","theme_name"])
    agg=long.groupby("theme_name",as_index=False).agg(
        theme_limit_up_count=("ts_code","nunique"),
        theme_max_height=("height","max"),
        theme_total_amount=("amount","sum"),
    )
    agg["r_theme_breadth"]=percentile_rank(agg["theme_limit_up_count"])
    agg["r_theme_height"]=percentile_rank(agg["theme_max_height"])
    agg["r_theme_amount"]=percentile_rank(agg["theme_total_amount"])
    agg["theme_strength"]=(
        0.50*agg["r_theme_breadth"]
        +0.30*agg["r_theme_height"]
        +0.20*agg["r_theme_amount"]
    )

    joined=long[["ts_code","theme_name"]].merge(agg,on="theme_name",how="left")
    joined=joined.sort_values(
        ["ts_code","theme_strength","theme_limit_up_count","theme_total_amount"],
        ascending=[True,False,False,False],
    )
    best=joined.groupby("ts_code",as_index=False).first()
    best["has_theme_evidence"]=best["theme_limit_up_count"]>=2
    return best[cols]
