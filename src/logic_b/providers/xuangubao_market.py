from __future__ import annotations

import json
import time as time_module
from dataclasses import dataclass
from datetime import date,datetime,time
from decimal import Decimal,ROUND_HALF_UP
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo

import pandas as pd

from ..universe import board_of


SHANGHAI=ZoneInfo("Asia/Shanghai")


def to_xgb_market_symbol(ts_code: str) -> str:
    code=str(ts_code).strip().upper()
    if code.endswith(".SH"):
        return code[:-3]+".SS"
    return code


@dataclass(frozen=True)
class XuangubaoMinuteDay:
    ts_code: str
    trade_date: str
    bars: pd.DataFrame
    pre_close: float | None
    raw_lines: int


class XuangubaoMarketProvider:
    """Historical stock minute data from Xuangubao/WSCN market backend."""

    BASE="https://api-ddc-wscn.xuangubao.com.cn/market"

    FIELDS=(
        "tick_at",
        "open_px",
        "close_px",
        "high_px",
        "low_px",
        "turnover_volume",
        "turnover_value",
        "avg_px",
        "px_change",
        "px_change_rate",
    )

    def __init__(
        self,
        *,
        timeout: float=20.0,
        max_attempts: int=4,
        retry_base_seconds: float=0.75,
        sleeper: Callable[[float],None]=time_module.sleep,
        opener: Callable | None=None,
        user_agent: str="Mozilla/5.0 Logic-B-Research/0.1",
    ):
        self.timeout=timeout
        self.max_attempts=max_attempts
        self.retry_base_seconds=retry_base_seconds
        self.sleeper=sleeper
        self.opener=opener or urlopen
        self.user_agent=user_agent

    def _json(
        self,
        path: str,
        params: dict[str,object],
    ) -> dict:
        url=f"{self.BASE}{path}?{urlencode(params)}"
        last=None
        for attempt in range(self.max_attempts):
            try:
                req=Request(
                    url,
                    headers={
                        "User-Agent":self.user_agent,
                        "Accept":"application/json",
                    },
                )
                with self.opener(
                    req,
                    timeout=self.timeout,
                ) as response:
                    payload=json.loads(
                        response.read().decode("utf-8")
                    )
                if not isinstance(payload,dict):
                    raise RuntimeError(
                        "Xuangubao market API returned non-object JSON"
                    )
                if payload.get("code") not in (
                    None,0,200,20000
                ):
                    raise RuntimeError(
                        f"Xuangubao market API code={payload.get('code')} "
                        f"message={payload.get('message')}"
                    )
                return payload
            except Exception as exc:
                last=exc
                if attempt+1>=self.max_attempts:
                    raise
                self.sleeper(
                    min(
                        self.retry_base_seconds*(2**attempt),
                        10.0,
                    )
                )
        assert last is not None
        raise last

    @staticmethod
    def _day_timestamp(
        day: date,
    ) -> int:
        # The API timestamp parameter pages historical bars backward from
        # the supplied point. 15:05 safely includes the closing minute.
        dt=datetime.combine(
            day,
            time(15,5),
            tzinfo=SHANGHAI,
        )
        return int(dt.timestamp())

    def historical_minute_day(
        self,
        ts_code: str,
        trade_date: date,
        *,
        tick_count: int=300,
    ) -> XuangubaoMinuteDay:
        xgb_code=to_xgb_market_symbol(
            ts_code
        )
        payload=self._json(
            "/kline",
            {
                "prod_code":xgb_code,
                "timestamp":
                    self._day_timestamp(
                        trade_date
                    ),
                "tick_count":tick_count,
                "period_type":60,
                "fields":",".join(
                    self.FIELDS
                ),
            },
        )

        data=payload.get("data") or {}
        fields=data.get("fields") or []
        candle=(
            data.get("candle",{})
            .get(xgb_code,{})
        )
        lines=candle.get("lines") or []
        pre_close=candle.get(
            "pre_close_px"
        )

        empty_columns=[
            "trade_time",
            "open",
            "high",
            "low",
            "close",
            "vol",
            "amount",
            "avg_price",
        ]

        if not fields or not lines:
            return XuangubaoMinuteDay(
                ts_code=ts_code,
                trade_date=
                    trade_date.strftime(
                        "%Y%m%d"
                    ),
                bars=pd.DataFrame(
                    columns=empty_columns
                ),
                pre_close=(
                    float(pre_close)
                    if pre_close is not None
                    else None
                ),
                raw_lines=len(lines),
            )

        frame=pd.DataFrame(
            lines,
            columns=fields,
        )
        required={
            "tick_at",
            "open_px",
            "close_px",
            "high_px",
            "low_px",
        }
        missing=required-set(
            frame.columns
        )
        if missing:
            raise RuntimeError(
                f"Xuangubao kline missing fields: {sorted(missing)}"
            )

        local_time=(
            pd.to_datetime(
                frame["tick_at"],
                unit="s",
                utc=True,
            )
            .dt.tz_convert(
                "Asia/Shanghai"
            )
        )
        frame["trade_time"]=(
            local_time.dt.tz_localize(
                None
            )
        )
        frame=frame[
            frame["trade_time"].dt.date
            ==trade_date
        ].copy()

        normalized=pd.DataFrame({
            "trade_time":
                frame["trade_time"],
            "open":
                pd.to_numeric(
                    frame["open_px"],
                    errors="coerce",
                ),
            "high":
                pd.to_numeric(
                    frame["high_px"],
                    errors="coerce",
                ),
            "low":
                pd.to_numeric(
                    frame["low_px"],
                    errors="coerce",
                ),
            "close":
                pd.to_numeric(
                    frame["close_px"],
                    errors="coerce",
                ),
            "vol":
                pd.to_numeric(
                    frame.get(
                        "turnover_volume",
                        0,
                    ),
                    errors="coerce",
                ).fillna(0),
            "amount":
                pd.to_numeric(
                    frame.get(
                        "turnover_value",
                        0,
                    ),
                    errors="coerce",
                ).fillna(0),
            "avg_price":
                pd.to_numeric(
                    frame.get(
                        "avg_px",
                        float("nan"),
                    ),
                    errors="coerce",
                ),
        }).sort_values(
            "trade_time"
        ).reset_index(drop=True)

        return XuangubaoMinuteDay(
            ts_code=ts_code,
            trade_date=
                trade_date.strftime(
                    "%Y%m%d"
                ),
            bars=normalized,
            pre_close=(
                float(pre_close)
                if pre_close is not None
                else None
            ),
            raw_lines=len(lines),
        )

    @staticmethod
    def daily_from_minute(
        minute_day: XuangubaoMinuteDay,
    ) -> pd.DataFrame:
        bars=minute_day.bars
        if bars.empty:
            return pd.DataFrame(columns=[
                "trade_date",
                "ts_code",
                "open",
                "high",
                "low",
                "close",
                "vol",
                "amount",
                "pct_chg",
                "source",
            ])

        pre=minute_day.pre_close
        close=float(
            bars.iloc[-1]["close"]
        )
        pct=(
            (close/pre-1.0)*100.0
            if pre not in (None,0)
            else float("nan")
        )
        return pd.DataFrame([{
            "trade_date":
                minute_day.trade_date,
            "ts_code":
                minute_day.ts_code,
            "open":
                float(bars.iloc[0]["open"]),
            "high":
                float(bars["high"].max()),
            "low":
                float(bars["low"].min()),
            "close":
                close,
            "vol":
                float(bars["vol"].sum()),
            "amount":
                float(
                    bars["amount"].sum()
                ),
            "pct_chg":pct,
            "source":"xuangubao",
        }])

    @staticmethod
    def _round_price(
        value: float,
    ) -> float:
        return float(
            Decimal(str(value))
            .quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        )

    @classmethod
    def limit_prices(
        cls,
        minute_day: XuangubaoMinuteDay,
    ) -> pd.DataFrame:
        pre=minute_day.pre_close
        if pre in (None,0):
            return pd.DataFrame(columns=[
                "trade_date",
                "ts_code",
                "pre_close",
                "up_limit",
                "down_limit",
                "source",
            ])

        board=board_of(
            minute_day.ts_code
        )
        ratio={
            "main":0.10,
            "chinext":0.20,
            "star":0.20,
        }.get(board)
        if ratio is None:
            return pd.DataFrame(columns=[
                "trade_date",
                "ts_code",
                "pre_close",
                "up_limit",
                "down_limit",
                "source",
            ])

        return pd.DataFrame([{
            "trade_date":
                minute_day.trade_date,
            "ts_code":
                minute_day.ts_code,
            "pre_close":float(pre),
            "up_limit":
                cls._round_price(
                    pre*(1+ratio)
                ),
            "down_limit":
                cls._round_price(
                    pre*(1-ratio)
                ),
            "source":
                "xuangubao_derived",
        }])
