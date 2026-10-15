from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from ..features import classify_market_regime, parse_board_height
from ..models import MarketRegime


@dataclass(frozen=True)
class RegimeSnapshot:
    regime: MarketRegime
    limit_up_count: int
    limit_down_count: int
    break_count: int
    break_rate: float
    max_height: int
    prev_limit_median_return: float

    def as_dict(self) -> dict:
        return {
            "regime":self.regime.value,
            "limit_up_count":self.limit_up_count,
            "limit_down_count":self.limit_down_count,
            "break_count":self.break_count,
            "break_rate":self.break_rate,
            "max_height":self.max_height,
            "prev_limit_median_return":self.prev_limit_median_return,
        }


def build_completed_day_regime(
    *,
    limit_up_df: pd.DataFrame,
    limit_down_df: pd.DataFrame,
    break_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    prior_day_limit_up_df: pd.DataFrame | None,
) -> RegimeSnapshot:
    """Build a regime after day D closes, to be used no earlier than D+1.

    prev_limit_median_return means: on D, median daily return of stocks that
    belonged to D-1's limit-up pool. This prevents using D+1 outcomes.
    """
    up_n=len(limit_up_df)
    down_n=len(limit_down_df)
    break_n=len(break_df)
    denom=up_n+break_n
    break_rate=float(break_n/denom) if denom else 0.0

    if not limit_up_df.empty and "tag" in limit_up_df.columns:
        max_height=max(limit_up_df["tag"].map(parse_board_height).tolist() or [1])
    else:
        max_height=1

    median_ret=0.0
    if prior_day_limit_up_df is not None and not prior_day_limit_up_df.empty and not daily_df.empty:
        codes=set(prior_day_limit_up_df["ts_code"].astype(str))
        d=daily_df[daily_df["ts_code"].astype(str).isin(codes)]
        if not d.empty and "pct_chg" in d.columns:
            # Tushare daily pct_chg is percentage points.
            median_ret=float(pd.to_numeric(d["pct_chg"],errors="coerce").dropna().median()/100.0)

    regime=classify_market_regime(
        limit_up_count=up_n,
        limit_down_count=down_n,
        break_rate=break_rate,
        max_height=int(max_height),
        prev_limit_median_return=median_ret,
    )
    return RegimeSnapshot(regime,up_n,down_n,break_n,break_rate,int(max_height),median_ret)
