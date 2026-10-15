from __future__ import annotations

import pandas as pd


REQUIRED_HUMAN={
    "trade_date","decision_time","action","selected_code","core_type"
}
REQUIRED_PROXY={
    "trade_date","decision_time","action","ts_code","core_type"
}


def _norm_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.strftime("%Y%m%d")


def _norm_time(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.strftime("%H:%M")


def _norm_code(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip()


def compare_human_proxy(
    human: pd.DataFrame,
    proxy: pd.DataFrame,
) -> tuple[dict[str,float],pd.DataFrame]:
    """Compare B0-H labels against B0-P outputs without looking at P&L."""
    missing_h=REQUIRED_HUMAN-set(human.columns)
    missing_p=REQUIRED_PROXY-set(proxy.columns)
    if missing_h:
        raise ValueError(f"human labels missing columns: {sorted(missing_h)}")
    if missing_p:
        raise ValueError(f"proxy signals missing columns: {sorted(missing_p)}")

    h=human.copy()
    p=proxy.copy()

    h["join_date"]=_norm_date(h["trade_date"])
    p["join_date"]=_norm_date(p["trade_date"])
    h["join_time"]=_norm_time(h["decision_time"])
    p["join_time"]=_norm_time(p["decision_time"])

    h=h.rename(columns={
        "action":"human_action",
        "selected_code":"human_code",
        "core_type":"human_core_type",
    })
    p=p.rename(columns={
        "action":"proxy_action",
        "ts_code":"proxy_code",
        "core_type":"proxy_core_type",
    })

    merged=h.merge(
        p,
        on=["join_date","join_time"],
        how="inner",
        suffixes=("_human","_proxy"),
    )
    if merged.empty:
        return {
            "matched_labels":0.0,
            "human_labels":float(len(h)),
            "coverage":0.0,
            "action_agreement":float("nan"),
            "selection_agreement":float("nan"),
            "core_type_agreement":float("nan"),
        },merged

    merged["human_code"]=_norm_code(merged["human_code"])
    merged["proxy_code"]=_norm_code(merged["proxy_code"])
    merged["action_match"]=merged["human_action"]==merged["proxy_action"]
    merged["code_match"]=merged["human_code"]==merged["proxy_code"]
    merged["core_type_match"]=merged["human_core_type"]==merged["proxy_core_type"]

    human_buy=merged["human_action"]=="BUY_CORE"
    both_buy=human_buy & (merged["proxy_action"]=="BUY_CORE")

    metrics={
        "matched_labels":float(len(merged)),
        "human_labels":float(len(h)),
        "coverage":float(len(merged)/len(h)) if len(h) else 0.0,
        "action_agreement":float(merged["action_match"].mean()),
        "selection_agreement":(
            float(merged.loc[human_buy,"code_match"].mean())
            if human_buy.any() else float("nan")
        ),
        "buy_to_buy_selection_agreement":(
            float(merged.loc[both_buy,"code_match"].mean())
            if both_buy.any() else float("nan")
        ),
        "core_type_agreement":(
            float(merged.loc[human_buy,"core_type_match"].mean())
            if human_buy.any() else float("nan")
        ),
    }

    audit_cols=[
        "join_date","join_time",
        "human_action","proxy_action","action_match",
        "human_code","proxy_code","code_match",
        "human_core_type","proxy_core_type","core_type_match",
    ]
    return metrics,merged[audit_cols].copy()
