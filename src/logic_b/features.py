from __future__ import annotations

import numpy as np
import pandas as pd

from .models import MarketRegime


def _series(df: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce").fillna(default)
    return pd.Series(default, index=df.index, dtype=float)


def percentile_rank(s: pd.Series, ascending: bool = True) -> pd.Series:
    if len(s) <= 1:
        return pd.Series(1.0, index=s.index)
    return s.rank(pct=True, method="average", ascending=ascending)


def build_prev_day_candidate_features(limit_df: pd.DataFrame) -> pd.DataFrame:
    if limit_df.empty:
        return limit_df.copy()

    x = limit_df.copy()
    height = _series(x, "连板数", 1.0)
    if "limit_times" in x.columns:
        height = _series(x, "limit_times", 1.0)

    amount = _series(x, "成交额", 0.0)
    if "amount" in x.columns:
        amount = _series(x, "amount", 0.0)

    turnover = _series(x, "换手率", 0.0)
    if "turnover_ratio" in x.columns:
        turnover = _series(x, "turnover_ratio", 0.0)

    open_times = _series(x, "开板次数", 0.0)
    if "open_num" in x.columns:
        open_times = _series(x, "open_num", 0.0)

    seal_amount = _series(x, "封单金额", 0.0)
    if "limit_order" in x.columns:
        seal_amount = _series(x, "limit_order", 0.0)
    if "lu_limit_order" in x.columns:
        seal_amount = _series(x, "lu_limit_order", 0.0)

    x["f_height"] = height
    x["f_amount"] = amount
    x["f_turnover"] = turnover
    x["f_open_times"] = open_times
    x["f_seal_amount"] = seal_amount

    x["r_height"] = percentile_rank(height)
    x["r_amount"] = percentile_rank(np.log1p(amount.clip(lower=0)))
    x["r_turnover"] = percentile_rank(turnover)
    x["r_seal"] = percentile_rank(np.log1p(seal_amount.clip(lower=0)))
    x["r_open_quality"] = percentile_rank(open_times, ascending=False)

    x["prev_core_score"] = (
        0.36 * x["r_height"]
        + 0.24 * x["r_amount"]
        + 0.16 * x["r_turnover"]
        + 0.14 * x["r_seal"]
        + 0.10 * x["r_open_quality"]
    )
    return x


def classify_market_regime(
    *,
    limit_up_count: int,
    limit_down_count: int,
    break_rate: float,
    max_height: int,
    prev_limit_median_return: float,
) -> MarketRegime:
    stress = 0
    strength = 0

    stress += int(limit_down_count >= 20)
    stress += int(break_rate >= 0.35)
    stress += int(prev_limit_median_return <= -0.02)
    stress += int(max_height <= 3)

    strength += int(limit_up_count >= 60)
    strength += int(break_rate <= 0.20)
    strength += int(prev_limit_median_return >= 0.015)
    strength += int(max_height >= 6)

    if stress >= 3:
        return MarketRegime.ICE
    if stress >= 2:
        return MarketRegime.RETREAT
    if strength >= 3:
        return MarketRegime.ATTACK
    if strength >= 2:
        return MarketRegime.TRIAL
    return MarketRegime.NEUTRAL
