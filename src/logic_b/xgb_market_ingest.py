from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd

from .providers.xuangubao_market import XuangubaoMarketProvider
from .storage import LocalParquetStore


class XuangubaoMarketIngestor:
    """Materialize symbol-day market data from Xuangubao historical minutes.

    The pre-close override is normally sourced from the prior trading day's
    limit-pool close price. This avoids relying on historical kline
    pre_close_px, which is observed to be zero for some archived A-share rows.
    """

    def __init__(
        self,
        provider: XuangubaoMarketProvider,
        store: LocalParquetStore,
    ):
        self.provider=provider
        self.store=store

    @staticmethod
    def _key(day: date | str) -> str:
        return pd.to_datetime(day).strftime("%Y%m%d")

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

        if (
            self.store.exists(
                "minute_1m",
                minute_partition,
            )
            and not force
        ):
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

        if minute_day is None:
            # Re-fetch only metadata when day-level rows are missing.
            need_daily=not self.store.exists(
                "daily",
                day_key,
            )
            need_limits=not self.store.exists(
                "limit_prices",
                day_key,
            )
            if need_daily or need_limits:
                minute_day=self.provider.historical_minute_day(
                    ts_code,
                    trade_date,
                    pre_close_override=pre_close,
                )

        if minute_day is not None:
            daily_row=self.provider.daily_from_minute(
                minute_day
            )
            limit_row=self.provider.limit_prices(
                minute_day
            )
        else:
            # Already cached day rows are returned below.
            daily_row=pd.DataFrame()
            limit_row=pd.DataFrame()

        if not daily_row.empty:
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

        if not limit_row.empty:
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

        # Empty minute bars are persisted as an explicit no-trade observation.
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
            "daily":(
                self.store.read_optional(
                    "daily",
                    day_key,
                )
                or pd.DataFrame()
            ),
            "limit_prices":(
                self.store.read_optional(
                    "limit_prices",
                    day_key,
                )
                or pd.DataFrame()
            ),
            "suspend":(
                self.store.read_optional(
                    "suspend",
                    day_key,
                )
                or pd.DataFrame()
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

        done=[]
        for _,row in prior_limit_up.iterrows():
            code=str(row["ts_code"])
            pre_close=None
            for field in (
                "price",
                "close",
                "prev_day_close",
            ):
                value=row.get(field)
                if value is not None:
                    try:
                        number=float(value)
                    except (TypeError,ValueError):
                        continue
                    if number>0:
                        pre_close=number
                        break

            self.materialize_symbol_day(
                trade_date=trade_date,
                ts_code=code,
                pre_close=pre_close,
                force=force,
            )
            done.append(code)
        return done
