from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
import json

import pandas as pd

from ..execution import simulate_buy_fill, simulate_sell_fill
from ..metrics import summarize_equity
from ..models import Action, FillModel
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

    Exit E0: attempt full liquidation from 09:35 on the first eligible T+1 day.
    If price remains locked at limit-down, retry on subsequent trading days.
    If liquidation happens after the decision checkpoint, no new position is
    opened that day. This is deliberately conservative.
    """

    def __init__(
        self,
        store: LocalParquetStore,
        *,
        strategy: B0Proxy | None = None,
        fill_model: FillModel = FillModel.REALISTIC,
        initial_cash: float = 1_000_000.0,
        fee_rate: float = 0.0003,
        stamp_rate: float = 0.0005,
        checkpoint: time = time(9,35),
        minute_loader: Callable[[str,str],pd.DataFrame] | None = None,
    ):
        self.store=store
        self.strategy=strategy or B0Proxy()
        self.fill_model=fill_model
        self.initial_cash=initial_cash
        self.fee_rate=fee_rate
        self.stamp_rate=stamp_rate
        self.checkpoint=checkpoint
        self.minute_loader=minute_loader

    @staticmethod
    def _key(v) -> str:
        return pd.to_datetime(v).strftime("%Y%m%d")

    def _minute(
        self,
        day_key: str,
        code: str,
        *,
        required: bool=True,
    ) -> pd.DataFrame:
        part=f"{day_key}/{code}"
        frame=self.store.read_optional("minute_1m",part)
        if frame is None and self.minute_loader is not None:
            frame=self.minute_loader(day_key,code)
            if frame is not None and not frame.empty and not self.store.exists("minute_1m",part):
                self.store.write_frame(
                    "minute_1m",
                    part,
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
                f"missing minute data {part}"
            )
        return pd.DataFrame() if frame is None else frame

    def _require(self, dataset: str, key: str) -> pd.DataFrame:
        try:
            return self.store.read_frame(dataset,key)
        except FileNotFoundError as e:
            raise MissingReplayDataError(str(e)) from e

    def run(self, trade_dates: list[str]) -> ReplayResult:
        keys=[self._key(x) for x in trade_dates]
        if len(keys)<3:
            raise ValueError("at least 3 trading days are required")

        portfolio=Portfolio(self.initial_cash)
        signals=[]; fills=[]; trades=[]; equity=[]
        entry_position_snapshot: Position | None=None

        for i,key in enumerate(keys):
            day=pd.to_datetime(key).date()
            decision_time=datetime.combine(day,self.checkpoint)
            daily=self._require("daily",key)
            limits=self._require("limit_prices",key)
            limits_idx=limits.set_index("ts_code",drop=False) if not limits.empty else pd.DataFrame()

            sold_at_checkpoint=False
            # E0 exit first. Same-day sale is rejected by Portfolio itself.
            if portfolio.position is not None and day>portfolio.position.entry_time.date():
                code=portfolio.position.ts_code
                if code not in limits_idx.index:
                    raise MissingReplayDataError(f"no limit price for held {code} on {key}")
                bars=self._minute(key,code)
                down=float(limits_idx.loc[code,"down_limit"])
                fill=simulate_sell_fill(
                    ts_code=code,
                    signal_time=decision_time,
                    minute_bars=bars,
                    limit_down_price=down,
                    model=self.fill_model,
                )
                fills.append(fill)
                if fill.filled:
                    pos=portfolio.position
                    net=portfolio.sell_all(fill.fill_time,fill.fill_price,self.fee_rate,self.stamp_rate)
                    ret=net/pos.cash_used-1.0
                    trades.append({
                        "ts_code":code,
                        "entry_time":pos.entry_time,
                        "entry_price":pos.entry_price,
                        "exit_time":fill.fill_time,
                        "exit_price":fill.fill_price,
                        "shares":pos.shares,
                        "net_return":ret,
                        "exit_rule":"E0_NEXT_DAY_0935",
                    })
                    sold_at_checkpoint=bool(fill.fill_time<=decision_time)
                    entry_position_snapshot=None

            # Build signal only once enough prior history exists and no capital is tied.
            if i>=2 and portfolio.position is None:
                prev=keys[i-1]; prevprev=keys[i-2]
                prev_up=self._require("limit_up",prev)
                prev_down=self._require("limit_down",prev)
                prev_break=self._require("limit_break",prev)
                prev_daily=self._require("daily",prev)
                prevprev_up=self._require("limit_up",prevprev)

                snap=build_completed_day_regime(
                    limit_up_df=prev_up,
                    limit_down_df=prev_down,
                    break_df=prev_break,
                    daily_df=prev_daily,
                    prior_day_limit_up_df=prevprev_up,
                )

                candidate_codes=prev_up["ts_code"].astype(str).tolist() if "ts_code" in prev_up.columns else []

                # If a prior position sold after 09:35, the 09:35 signal is stale and
                # capital was unavailable then; skip re-entry for the day.
                can_enter = not fills or not (
                    fills[-1].side=="SELL"
                    and fills[-1].signal_time.date()==day
                    and fills[-1].filled
                    and fills[-1].fill_time>decision_time
                )

                if candidate_codes and can_enter:
                    current_codes=set(daily["ts_code"].astype(str)) if "ts_code" in daily.columns else set()
                    minute_frames={}
                    for code in candidate_codes:
                        # No daily row generally means suspension/no trading; do not
                        # invent minute data for it.
                        if code not in current_codes:
                            continue
                        minute_frames[code]=self._minute(key,code)
                    cp=build_minute_checkpoint(candidate_codes,minute_frames,limits,decision_time)
                else:
                    cp=pd.DataFrame()

                signal=self.strategy.decide(
                    trade_date=key,
                    decision_time=decision_time,
                    prev_limit_df=prev_up,
                    checkpoint_df=cp,
                    market_regime=snap.regime,
                )
                signal.evidence["regime_snapshot"]=snap.as_dict()
                signals.append(signal)

                if signal.action==Action.BUY_CORE and signal.ts_code and can_enter:
                    code=signal.ts_code
                    if code not in limits_idx.index:
                        raise MissingReplayDataError(f"no limit price for signal {code} on {key}")
                    bars=minute_frames[code]
                    up=float(limits_idx.loc[code,"up_limit"])
                    fill=simulate_buy_fill(
                        ts_code=code,
                        signal_time=decision_time,
                        minute_bars=bars,
                        limit_up_price=up,
                        model=self.fill_model,
                    )
                    fills.append(fill)
                    if fill.filled:
                        portfolio.buy_all(code,fill.fill_time,fill.fill_price,self.fee_rate)
                        entry_position_snapshot=portfolio.position

            mark=None
            if portfolio.position is not None:
                code=portfolio.position.ts_code
                row=daily[daily["ts_code"].astype(str)==code] if "ts_code" in daily.columns else pd.DataFrame()
                if row.empty or "close" not in row.columns:
                    raise MissingReplayDataError(f"missing close for held {code} on {key}")
                mark=float(row.iloc[0]["close"])
            equity.append({
                "date":key,
                "equity":portfolio.equity(mark),
                "cash":portfolio.cash,
                "holding":portfolio.position.ts_code if portfolio.position else None,
                "mark_price":mark,
            })

        metrics=summarize_equity(pd.DataFrame(equity),pd.DataFrame(trades).rename(columns={"net_return":"return"}))
        metrics.update({
            "fill_model":self.fill_model.value,
            "initial_cash":self.initial_cash,
            "closed_trades":len(trades),
            "signals":len(signals),
            "ending_position":portfolio.position.ts_code if portfolio.position else None,
        })
        return ReplayResult(signals,fills,trades,equity,metrics)
