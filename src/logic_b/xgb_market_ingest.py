from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date
import threading
import time as time_module
from typing import Callable

import pandas as pd

from .providers.xuangubao_market import XuangubaoMarketProvider,XuangubaoMinuteDay
from .storage import LocalParquetStore


class XuangubaoMarketIngestor:
    """Materialize candidate symbol-day market data from Xuangubao minutes.

    For day D candidate replay, pre_close should come from the D-1 limit-up
    evidence row when available. This avoids trusting archived kline
    pre_close_px values that are zero/missing for some historical rows.
    """

    def __init__(
        self,
        provider: XuangubaoMarketProvider,
        store: LocalParquetStore,
        *,
        inter_request_sleep: float=0.10,
        max_workers: int=4,
        sleeper: Callable[[float],None]=time_module.sleep,
    ):
        self.provider=provider
        self.store=store
        self.inter_request_sleep=max(
            0.0,
            float(inter_request_sleep),
        )
        self.max_workers=max(
            1,
            int(max_workers),
        )
        self.sleeper=sleeper
        self._write_lock=threading.Lock()

    def _pause(self) -> None:
        if self.inter_request_sleep>0:
            self.sleeper(
                self.inter_request_sleep
            )

    @staticmethod
    def _key(day: date | str) -> str:
        return pd.to_datetime(day).strftime("%Y%m%d")

    @staticmethod
    def _optional_or_empty(
        store: LocalParquetStore,
        dataset: str,
        partition: str,
    ) -> pd.DataFrame:
        frame=store.read_optional(
            dataset,
            partition,
        )
        return (
            pd.DataFrame()
            if frame is None
            else frame
        )

    @staticmethod
    def _day_has_code(
        store: LocalParquetStore,
        dataset: str,
        day_key: str,
        code: str,
    ) -> bool:
        frame=store.read_optional(
            dataset,
            day_key,
        )
        return bool(
            frame is not None
            and not frame.empty
            and "ts_code" in frame.columns
            and str(code) in set(
                frame["ts_code"].astype(str)
            )
        )

    @staticmethod
    def _upsert_day(
        store: LocalParquetStore,
        dataset: str,
        day_key: str,
        rows: pd.DataFrame,
        *,
        key_col: str="ts_code",
        metadata: dict | None=None,
    ) -> pd.DataFrame:
        existing=store.read_optional(
            dataset,
            day_key,
        )
        frames=[
            frame
            for frame in (existing,rows)
            if frame is not None
            and not frame.empty
        ]
        if not frames:
            merged=rows.copy()
        else:
            merged=pd.concat(
                frames,
                ignore_index=True,
            )
            if key_col in merged.columns:
                merged=merged.drop_duplicates(
                    subset=[key_col],
                    keep="last",
                )

        store.write_frame(
            dataset,
            day_key,
            merged,
            metadata=metadata or {},
        )
        return merged

    @staticmethod
    def pre_close_from_prior_row(
        row: pd.Series,
    ) -> float | None:
        """Return D pre-close from a D-1 pool row.

        The preferred value is D-1 final price. Fallback aliases exist for
        source-neutral fixtures and future adapters.
        """
        for field in (
            "price",
            "close",
            "prev_day_close",
        ):
            value=row.get(field)
            if value is None:
                continue
            try:
                number=float(value)
            except (TypeError,ValueError):
                continue
            if number>0:
                return number
        return None

    def materialize_symbol_day(
        self,
        *,
        trade_date: date,
        ts_code: str,
        pre_close: float | None,
        force: bool=False,
    ) -> dict[str,pd.DataFrame]:
        day_key=self._key(trade_date)
        minute_partition=(
            f"{day_key}/{ts_code}"
        )

        cached_minute=self.store.exists(
            "minute_1m",
            minute_partition,
        )
        if cached_minute and not force:
            bars=self.store.read_frame(
                "minute_1m",
                minute_partition,
            )
            minute_day=None
        else:
            minute_day=self.provider.historical_minute_day(
                ts_code,
                trade_date,
                pre_close_override=pre_close,
            )
            bars=minute_day.bars
            self.store.write_frame(
                "minute_1m",
                minute_partition,
                bars,
                metadata={
                    "source":"xuangubao",
                    "trade_date":day_key,
                    "ts_code":ts_code,
                    "pre_close":
                        minute_day.pre_close,
                    "pre_close_source":
                        minute_day.pre_close_source,
                },
            )

        need_daily=not self._day_has_code(
            self.store,
            "daily",
            day_key,
            ts_code,
        )
        need_limits=not self._day_has_code(
            self.store,
            "limit_prices",
            day_key,
            ts_code,
        )

        if (
            minute_day is None
            and (need_daily or need_limits)
        ):
            if (
                pre_close is not None
                and float(pre_close)>0
            ):
                minute_day=XuangubaoMinuteDay(
                    ts_code=ts_code,
                    trade_date=day_key,
                    bars=bars,
                    pre_close=float(pre_close),
                    pre_close_source=
                        "cached_minute_with_override",
                    raw_lines=len(bars),
                )
            else:
                minute_day=self.provider.historical_minute_day(
                    ts_code,
                    trade_date,
                    pre_close_override=pre_close,
                )

        daily_row=pd.DataFrame()
        limit_row=pd.DataFrame()
        if minute_day is not None:
            daily_row=self.provider.daily_from_minute(
                minute_day
            )
            limit_row=self.provider.limit_prices(
                minute_day
            )

        with self._write_lock:
            if (
                not daily_row.empty
                and not self._day_has_code(
                    self.store,
                    "daily",
                    day_key,
                    ts_code,
                )
            ):
                self._upsert_day(
                    self.store,
                    "daily",
                    day_key,
                    daily_row,
                    metadata={
                        "source":
                            "xuangubao_derived_from_1m",
                        "trade_date":day_key,
                    },
                )

            if (
                not limit_row.empty
                and not self._day_has_code(
                    self.store,
                    "limit_prices",
                    day_key,
                    ts_code,
                )
            ):
                self._upsert_day(
                    self.store,
                    "limit_prices",
                    day_key,
                    limit_row,
                    metadata={
                        "source":
                            "xuangubao_derived",
                        "trade_date":day_key,
                    },
                )

            if bars.empty:
                suspend_row=pd.DataFrame([{
                    "trade_date":day_key,
                    "ts_code":ts_code,
                    "suspend_type":"NO_BARS",
                    "source":"xuangubao_inferred",
                }])
                self._upsert_day(
                    self.store,
                    "suspend",
                    day_key,
                    suspend_row,
                    metadata={
                        "source":
                            "xuangubao_inferred",
                        "trade_date":day_key,
                    },
                )

        return {
            "minute_1m":bars,
            "daily":self._optional_or_empty(
                self.store,
                "daily",
                day_key,
            ),
            "limit_prices":self._optional_or_empty(
                self.store,
                "limit_prices",
                day_key,
            ),
            "suspend":self._optional_or_empty(
                self.store,
                "suspend",
                day_key,
            ),
        }

    def materialize_from_prior_pool(
        self,
        *,
        trade_date: date,
        prior_limit_up: pd.DataFrame,
        force: bool=False,
    ) -> list[str]:
        if (
            prior_limit_up is None
            or prior_limit_up.empty
            or "ts_code" not in prior_limit_up.columns
        ):
            return []

        day_key=self._key(trade_date)

        daily=self.store.read_optional(
            "daily",
            day_key,
        )
        limits=self.store.read_optional(
            "limit_prices",
            day_key,
        )
        daily_codes=self._code_set(
            daily
        )
        limit_codes=self._code_set(
            limits
        )

        tasks=[]
        all_codes=[]
        seen=set()
        for _,row in prior_limit_up.iterrows():
            if bool(
                row.get(
                    "is_new_stock",
                    False,
                )
            ):
                continue

            code=str(row["ts_code"])
            if code in seen:
                continue
            seen.add(code)
            all_codes.append(code)

            if (
                not force
                and code in daily_codes
                and code in limit_codes
                and self.store.exists(
                    "minute_1m",
                    f"{day_key}/{code}",
                )
            ):
                continue

            tasks.append((
                code,
                self.pre_close_from_prior_row(
                    row
                ),
            ))

        if not tasks:
            return all_codes

        if self.max_workers<=1:
            for code,pre_close in tasks:
                self.materialize_symbol_day(
                    trade_date=trade_date,
                    ts_code=code,
                    pre_close=pre_close,
                    force=force,
                )
                self._pause()
            return all_codes

        futures={}
        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            for code,pre_close in tasks:
                future=executor.submit(
                    self.materialize_symbol_day,
                    trade_date=trade_date,
                    ts_code=code,
                    pre_close=pre_close,
                    force=force,
                )
                futures[future]=code
                self._pause()

            for future in as_completed(
                futures
            ):
                future.result()

        return all_codes

    def _ensure_empty_market_partitions(
        self,
        day_key: str,
    ) -> None:
        empty_specs={
            "daily":[
                "trade_date","ts_code",
                "open","high","low","close",
                "vol","amount","pct_chg","source",
            ],
            "limit_prices":[
                "trade_date","ts_code",
                "pre_close","up_limit",
                "down_limit","source",
            ],
            "suspend":[
                "trade_date","ts_code",
                "suspend_type","source",
            ],
        }
        for dataset,columns in empty_specs.items():
            if not self.store.exists(
                dataset,
                day_key,
            ):
                self.store.write_frame(
                    dataset,
                    day_key,
                    pd.DataFrame(
                        columns=columns
                    ),
                    metadata={
                        "source":"xuangubao_candidate_slice",
                        "trade_date":day_key,
                        "meaning":
                            "empty canonical partition until symbol-day rows are materialized",
                    },
                )

    @staticmethod
    def _st_rows_from_prior_pool(
        prior_limit_up: pd.DataFrame,
        *,
        trade_date: str,
    ) -> pd.DataFrame:
        columns=[
            "trade_date",
            "ts_code",
            "name",
            "source",
        ]
        if (
            prior_limit_up is None
            or prior_limit_up.empty
            or "ts_code" not in prior_limit_up.columns
        ):
            return pd.DataFrame(columns=columns)

        if "name" not in prior_limit_up.columns:
            return pd.DataFrame(columns=columns)

        names=prior_limit_up["name"].fillna("").astype(str)
        mask=names.str.upper().str.contains("ST",regex=False)
        if not mask.any():
            return pd.DataFrame(columns=columns)

        rows=prior_limit_up.loc[
            mask,
            ["ts_code","name"],
        ].copy()
        rows.insert(0,"trade_date",trade_date)
        rows["source"]="xuangubao_prior_name_inference"
        return rows[columns]

    def _ensure_day_state_partitions(
        self,
        *,
        day_key: str,
        prior_limit_up: pd.DataFrame,
    ) -> None:
        if not self.store.exists(
            "suspend",
            day_key,
        ):
            self.store.write_frame(
                "suspend",
                day_key,
                pd.DataFrame(columns=[
                    "trade_date",
                    "ts_code",
                    "suspend_type",
                    "source",
                ]),
                metadata={
                    "source":"xuangubao_inferred",
                    "trade_date":day_key,
                    "meaning":
                        "empty unless candidate minute bars are absent",
                },
            )

        if not self.store.exists(
            "stock_st",
            day_key,
        ):
            st_rows=self._st_rows_from_prior_pool(
                prior_limit_up,
                trade_date=day_key,
            )
            self.store.write_frame(
                "stock_st",
                day_key,
                st_rows,
                metadata={
                    "source":"xuangubao_prior_name_inference",
                    "trade_date":day_key,
                    "limitation":
                        "does not detect an overnight ST-name change absent from D-1 pool evidence",
                },
            )

    def materialize_range(
        self,
        *,
        trade_dates: list[str],
        force: bool=False,
        progress_callback: Callable[[dict],None] | None=None,
    ) -> dict[str,int]:
        """Materialize D market data for every D-1 limit-up candidate."""
        if len(trade_dates)<2:
            return {
                "trade_days":len(trade_dates),
                "candidate_symbol_days":0,
                "days_with_candidates":0,
            }

        symbol_days=0
        days_with_candidates=0

        for raw_day in trade_dates:
            self._ensure_empty_market_partitions(
                self._key(raw_day)
            )

        if trade_dates:
            self._ensure_day_state_partitions(
                day_key=self._key(
                    trade_dates[0]
                ),
                prior_limit_up=pd.DataFrame(),
            )

        for index in range(1,len(trade_dates)):
            day_key=self._key(
                trade_dates[index]
            )
            prior_key=self._key(
                trade_dates[index-1]
            )
            prior=self.store.read_optional(
                "limit_up",
                prior_key,
            )
            if (
                prior is None
                or prior.empty
            ):
                self._ensure_day_state_partitions(
                    day_key=day_key,
                    prior_limit_up=(
                        pd.DataFrame()
                        if prior is None
                        else prior
                    ),
                )
                continue

            done=self.materialize_from_prior_pool(
                trade_date=
                    pd.to_datetime(
                        day_key
                    ).date(),
                prior_limit_up=prior,
                force=force,
            )
            self._ensure_day_state_partitions(
                day_key=day_key,
                prior_limit_up=prior,
            )
            if done:
                days_with_candidates+=1
                symbol_days+=len(done)

            if progress_callback is not None:
                progress_callback({
                    "trade_date":day_key,
                    "index":index,
                    "trade_days":len(trade_dates),
                    "candidate_symbol_days":symbol_days,
                    "days_with_candidates":days_with_candidates,
                    "day_candidates":len(done),
                })

        return {
            "trade_days":len(trade_dates),
            "candidate_symbol_days":
                symbol_days,
            "days_with_candidates":
                days_with_candidates,
        }
