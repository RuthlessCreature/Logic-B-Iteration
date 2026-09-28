from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,time
from typing import Callable

import pandas as pd

from ..execution import simulate_buy_fill,simulate_sell_fill
from ..metrics import summarize_equity
from ..models import Action,FillModel
from ..portfolio import Portfolio
from ..storage import LocalParquetStore
from ..strategy.b0 import B0Proxy
from .checkpoint import build_minute_checkpoint
from .regime import build_completed_day_regime


class MissingReplayDataError(RuntimeError):
    pass


@dataclass
class ReplayResult:
    signals: list
    fills: list
    trades: list[dict]
    daily_equity: list[dict]
    metrics: dict


class B0ReplayRunner:
    """Event-style B0-P baseline replay.

    Rules:
    - D-1 limit-up pool defines candidates.
    - D-1 KPL theme labels provide point-in-time theme evidence.
    - Current-day ST list may remove candidates before the 09:35 decision.
    - A signal built from the completed checkpoint bar can only fill later.
    - E0 attempts full liquidation after the next eligible 09:35 checkpoint.
    - Locked limit-down positions remain held and are retried on later sessions.
    """

    def __init__(
        self,
        store: LocalParquetStore,
        *,
        strategy: B0Proxy | None=None,
        fill_model: FillModel=FillModel.REALISTIC,
        initial_cash: float=1_000_000.0,
        fee_rate: float=0.0003,
        stamp_rate: float=0.0005,
        checkpoint: time=time(9,35),
        minute_loader: Callable[
            [str,str],
            pd.DataFrame,
        ] | None=None,
        exclude_st: bool=True,
    ):
        self.store=store
        self.strategy=strategy or B0Proxy()
        self.fill_model=fill_model
        self.initial_cash=initial_cash
        self.fee_rate=fee_rate
        self.stamp_rate=stamp_rate
        self.checkpoint=checkpoint
        self.minute_loader=minute_loader
        self.exclude_st=exclude_st

    @staticmethod
    def _key(value) -> str:
        return pd.to_datetime(value).strftime("%Y%m%d")

    def _require(
        self,
        dataset: str,
        key: str,
    ) -> pd.DataFrame:
        try:
            return self.store.read_frame(
                dataset,
                key,
            )
        except FileNotFoundError as exc:
            raise MissingReplayDataError(
                str(exc)
            ) from exc

    def _minute(
        self,
        day_key: str,
        code: str,
        *,
        required: bool=True,
    ) -> pd.DataFrame:
        partition=f"{day_key}/{code}"
        frame=self.store.read_optional(
            "minute_1m",
            partition,
        )

        if (
            frame is None
            and self.minute_loader is not None
        ):
            frame=self.minute_loader(
                day_key,
                code,
            )
            if (
                frame is not None
                and not frame.empty
                and not self.store.exists(
                    "minute_1m",
                    partition,
                )
            ):
                self.store.write_frame(
                    "minute_1m",
                    partition,
                    frame,
                    metadata={
                        "source":"on_demand_loader",
                        "trade_date":day_key,
                        "ts_code":code,
                        "freq":"1min",
                    },
                )

        if frame is None and required:
            raise MissingReplayDataError(
                f"missing minute data {partition}"
            )

        return (
            pd.DataFrame()
            if frame is None
            else frame
        )

    @staticmethod
    def _filter_st(
        prev_up: pd.DataFrame,
        current_st: pd.DataFrame,
    ) -> pd.DataFrame:
        if prev_up.empty:
            return prev_up.copy()
        if (
            current_st is None
            or current_st.empty
            or "ts_code" not in current_st.columns
        ):
            return prev_up.copy()

        st_codes=set(
            current_st["ts_code"].astype(str)
        )
        return prev_up[
            ~prev_up["ts_code"].astype(str).isin(
                st_codes
            )
        ].copy()

    def run(
        self,
        trade_dates: list[str],
    ) -> ReplayResult:
        keys=[
            self._key(value)
            for value in trade_dates
        ]
        if len(keys)<3:
            raise ValueError(
                "at least 3 trading days are required"
            )

        portfolio=Portfolio(self.initial_cash)
        signals=[]
        fills=[]
        trades=[]
        equity=[]

        for index,key in enumerate(keys):
            day=pd.to_datetime(key).date()
            decision_time=datetime.combine(
                day,
                self.checkpoint,
            )

            daily=self._require("daily",key)
            limits=self._require(
                "limit_prices",
                key,
            )
            limits_idx=(
                limits.set_index(
                    "ts_code",
                    drop=False,
                )
                if not limits.empty
                else pd.DataFrame()
            )

            # E0 exit before considering any new entry.
            if (
                portfolio.position is not None
                and day>
                portfolio.position.entry_time.date()
            ):
                code=portfolio.position.ts_code
                if code not in limits_idx.index:
                    raise MissingReplayDataError(
                        f"no limit price for held "
                        f"{code} on {key}"
                    )

                bars=self._minute(key,code)
                down=float(
                    limits_idx.loc[
                        code,
                        "down_limit",
                    ]
                )
                fill=simulate_sell_fill(
                    ts_code=code,
                    signal_time=decision_time,
                    minute_bars=bars,
                    limit_down_price=down,
                    model=self.fill_model,
                )
                fills.append(fill)

                if fill.filled:
                    position=portfolio.position
                    net=portfolio.sell_all(
                        fill.fill_time,
                        fill.fill_price,
                        self.fee_rate,
                        self.stamp_rate,
                    )
                    trades.append({
                        "ts_code":code,
                        "entry_time":
                            position.entry_time,
                        "entry_price":
                            position.entry_price,
                        "exit_time":
                            fill.fill_time,
                        "exit_price":
                            fill.fill_price,
                        "shares":
                            position.shares,
                        "net_return":
                            net/position.cash_used-1.0,
                        "exit_rule":
                            "E0_NEXT_DAY_0935",
                    })

            if (
                index>=2
                and portfolio.position is None
            ):
                prev=keys[index-1]
                prevprev=keys[index-2]

                prev_up=self._require(
                    "limit_up",
                    prev,
                )
                prev_down=self._require(
                    "limit_down",
                    prev,
                )
                prev_break=self._require(
                    "limit_break",
                    prev,
                )
                prev_daily=self._require(
                    "daily",
                    prev,
                )
                prevprev_up=self._require(
                    "limit_up",
                    prevprev,
                )
                prev_theme=self.store.read_optional(
                    "kpl_limit_up",
                    prev,
                )

                if self.exclude_st:
                    current_st=self._require(
                        "stock_st",
                        key,
                    )
                    candidates=self._filter_st(
                        prev_up,
                        current_st,
                    )
                else:
                    candidates=prev_up.copy()

                regime=build_completed_day_regime(
                    limit_up_df=prev_up,
                    limit_down_df=prev_down,
                    break_df=prev_break,
                    daily_df=prev_daily,
                    prior_day_limit_up_df=
                        prevprev_up,
                )

                candidate_codes=(
                    candidates["ts_code"]
                    .astype(str)
                    .tolist()
                    if "ts_code" in candidates.columns
                    else []
                )

                # If a prior position was sold after the checkpoint,
                # the 09:35 entry decision is stale and cannot be replayed
                # using capital that was unavailable then.
                can_enter=not fills or not (
                    fills[-1].side=="SELL"
                    and
                    fills[-1].signal_time.date()
                    ==day
                    and fills[-1].filled
                    and fills[-1].fill_time
                    >decision_time
                )

                minute_frames={}
                if candidate_codes and can_enter:
                    current_codes=(
                        set(
                            daily["ts_code"]
                            .astype(str)
                        )
                        if "ts_code" in daily.columns
                        else set()
                    )
                    for code in candidate_codes:
                        if code not in current_codes:
                            continue
                        minute_frames[code]=(
                            self._minute(
                                key,
                                code,
                            )
                        )

                    checkpoint=build_minute_checkpoint(
                        candidate_codes,
                        minute_frames,
                        limits,
                        decision_time,
                    )
                else:
                    checkpoint=pd.DataFrame()

                signal=self.strategy.decide(
                    trade_date=key,
                    decision_time=decision_time,
                    prev_limit_df=candidates,
                    checkpoint_df=checkpoint,
                    market_regime=regime.regime,
                    prev_theme_df=prev_theme,
                )
                signal.evidence[
                    "regime_snapshot"
                ]=regime.as_dict()
                signal.evidence[
                    "st_exclusion_enabled"
                ]=self.exclude_st
                signal.evidence[
                    "candidate_count_after_st_filter"
                ]=len(candidate_codes)
                signals.append(signal)

                if (
                    signal.action==Action.BUY_CORE
                    and signal.ts_code
                    and can_enter
                ):
                    code=signal.ts_code
                    if code not in limits_idx.index:
                        raise MissingReplayDataError(
                            f"no limit price for signal "
                            f"{code} on {key}"
                        )

                    bars=minute_frames[code]
                    up=float(
                        limits_idx.loc[
                            code,
                            "up_limit",
                        ]
                    )
                    fill=simulate_buy_fill(
                        ts_code=code,
                        signal_time=decision_time,
                        minute_bars=bars,
                        limit_up_price=up,
                        model=self.fill_model,
                    )
                    fills.append(fill)

                    if fill.filled:
                        portfolio.buy_all(
                            code,
                            fill.fill_time,
                            fill.fill_price,
                            self.fee_rate,
                        )

            mark=None
            if portfolio.position is not None:
                code=portfolio.position.ts_code
                row=(
                    daily[
                        daily["ts_code"]
                        .astype(str)
                        ==code
                    ]
                    if "ts_code" in daily.columns
                    else pd.DataFrame()
                )
                if (
                    row.empty
                    or "close" not in row.columns
                ):
                    raise MissingReplayDataError(
                        f"missing close for held "
                        f"{code} on {key}"
                    )
                mark=float(
                    row.iloc[0]["close"]
                )

            equity.append({
                "date":key,
                "equity":
                    portfolio.equity(mark),
                "cash":
                    portfolio.cash,
                "holding":
                    (
                        portfolio.position.ts_code
                        if portfolio.position
                        else None
                    ),
                "mark_price":mark,
            })

        metrics=summarize_equity(
            pd.DataFrame(equity),
            pd.DataFrame(trades).rename(
                columns={
                    "net_return":"return"
                }
            ),
        )
        metrics.update({
            "fill_model":
                self.fill_model.value,
            "initial_cash":
                self.initial_cash,
            "closed_trades":
                len(trades),
            "signals":
                len(signals),
            "ending_position":
                (
                    portfolio.position.ts_code
                    if portfolio.position
                    else None
                ),
            "exclude_st":
                self.exclude_st,
        })

        return ReplayResult(
            signals=signals,
            fills=fills,
            trades=trades,
            daily_equity=equity,
            metrics=metrics,
        )
