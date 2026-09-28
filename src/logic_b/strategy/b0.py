from __future__ import annotations

from datetime import datetime
import numpy as np
import pandas as pd

from ..features import build_prev_day_candidate_features
from ..models import Action, CoreType, MarketRegime, Signal


class B0Proxy:
    version = "B0-P.0"

    def __init__(self, blocked_regimes=(MarketRegime.RETREAT, MarketRegime.ICE), min_confirmation=0.58, min_tradability=0.45):
        self.blocked_regimes = blocked_regimes
        self.min_confirmation = min_confirmation
        self.min_tradability = min_tradability

    @staticmethod
    def _core_type(row: pd.Series, max_height: float) -> CoreType:
        height = float(row["f_height"])
        if height == max_height and height >= 3:
            return CoreType.TOTAL_MARKET_LEADER
        if row["r_amount"] >= 0.85 and row["prev_core_score"] >= 0.70:
            return CoreType.SECTOR_CAPACITY_CORE
        if row["r_turnover"] >= 0.75 and row["prev_core_score"] >= 0.65:
            return CoreType.TURNOVER_FRONT
        if height <= 2 and row["prev_core_score"] >= 0.72:
            return CoreType.CATCHUP_CORE
        return CoreType.NONE

    @staticmethod
    def _checkpoint_scores(row: pd.Series) -> tuple[float, float]:
        pct = float(row.get("pct_from_prev_close", 0.0))
        rel = float(row.get("relative_to_peer_median", 0.0))
        amount_rank = float(row.get("checkpoint_amount_rank", 0.5))
        at_limit = bool(row.get("at_limit", False))
        one_price = bool(row.get("one_price_limit", False))
        opened_after_limit = bool(row.get("opened_after_limit", False))
        confirmation = (
            0.35 * np.clip((pct + 0.03) / 0.13, 0.0, 1.0)
            + 0.25 * np.clip((rel + 0.03) / 0.08, 0.0, 1.0)
            + 0.25 * np.clip(amount_rank, 0.0, 1.0)
            + 0.15 * float(at_limit)
        )
        tradability = 0.85 - 0.70 * float(one_price) - 0.25 * float(at_limit and not opened_after_limit) + 0.10 * float(opened_after_limit)
        return float(np.clip(confirmation, 0, 1)), float(np.clip(tradability, 0, 1))

    def decide(self, *, trade_date: str, decision_time: datetime, prev_limit_df: pd.DataFrame, checkpoint_df: pd.DataFrame, market_regime: MarketRegime) -> Signal:
        def cash(reason: str, risk: float = 0.5) -> Signal:
            return Signal(trade_date, decision_time, None, self.version, market_regime, CoreType.NONE, 0, 0, 0, risk, Action.CASH, {"gate": reason})

        if market_regime in self.blocked_regimes:
            return cash("market_regime_blocked", 1.0)

        prev = build_prev_day_candidate_features(prev_limit_df)
        if prev.empty or checkpoint_df.empty:
            return cash("no_candidates")

        merged = prev.merge(checkpoint_df, on="ts_code", how="inner", suffixes=("", "_t"))
        if merged.empty:
            return cash("no_checkpoint_candidates")

        max_height = float(prev["f_height"].max())
        merged["core_type"] = merged.apply(lambda r: self._core_type(r, max_height), axis=1)
        merged = merged[merged["core_type"] != CoreType.NONE].copy()
        if merged.empty:
            return cash("no_core", 0.4)

        scores = merged.apply(self._checkpoint_scores, axis=1)
        merged["confirmation_score"] = [s[0] for s in scores]
        merged["tradability_score"] = [s[1] for s in scores]
        merged["decision_score"] = 0.52 * merged["prev_core_score"] + 0.33 * merged["confirmation_score"] + 0.15 * merged["tradability_score"]
        winner = merged.sort_values(["decision_score", "prev_core_score"], ascending=False).iloc[0]
        confirmation = float(winner["confirmation_score"])
        tradability = float(winner["tradability_score"])
        action = Action.BUY_CORE if confirmation >= self.min_confirmation and tradability >= self.min_tradability else Action.CASH
        if action == Action.CASH:
            return Signal(trade_date, decision_time, None, self.version, market_regime, CoreType.NONE, float(winner["prev_core_score"]), confirmation, tradability, 1.0 - (0.55 * confirmation + 0.45 * tradability), action, {"winner_before_gate": str(winner["ts_code"])})
        return Signal(trade_date, decision_time, str(winner["ts_code"]), self.version, market_regime, winner["core_type"], float(winner["prev_core_score"]), confirmation, tradability, 1.0 - (0.55 * confirmation + 0.45 * tradability), action, {"decision_score": float(winner["decision_score"]), "max_height_prev_day": max_height})
