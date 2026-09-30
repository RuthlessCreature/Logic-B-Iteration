from __future__ import annotations

import json
import time as time_module
from datetime import date
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request,urlopen

import pandas as pd


def normalize_xgb_symbol(symbol: object) -> str:
    value=str(symbol or "").strip().upper()
    if value.endswith(".SS"):
        return value[:-3]+".SH"
    return value


def _theme_names(surge_reason: object) -> list[str]:
    if not isinstance(surge_reason,dict):
        return []
    plates=surge_reason.get("related_plates") or []
    names=[]
    for plate in plates:
        if isinstance(plate,dict):
            name=plate.get("plate_name") or plate.get("name")
        else:
            name=str(plate)
        if name:
            names.append(str(name).strip())
    return [name for name in names if name]


def _tag(row: dict) -> str:
    days=int(row.get("m_days_n_boards_days") or 0)
    boards=int(row.get("m_days_n_boards_boards") or 0)
    if days>0 and boards>0:
        return f"{days}天{boards}板"

    consecutive=int(row.get("limit_up_days") or 0)
    if consecutive<=1:
        return "首板"
    return f"{consecutive}连板"


def normalize_xgb_pool(
    rows: list[dict],
    *,
    trade_date: date,
    pool_name: str,
) -> pd.DataFrame:
    """Normalize Xuangubao pool rows into Logic-B evidence schema."""
    normalized=[]
    for row in rows:
        code=normalize_xgb_symbol(row.get("symbol"))
        if not code:
            continue

        turnover_ratio=float(row.get("turnover_ratio") or 0.0)
        free_cap=float(row.get("non_restricted_capital") or 0.0)
        # XGB exposes turnover ratio and free-float capital but not a dedicated
        # turnover-amount field in this pool payload. Their product is kept as
        # an explicit estimate, not silently presented as vendor turnover.
        turnover_estimated=(
            turnover_ratio*free_cap
            if turnover_ratio>0 and free_cap>0
            else 0.0
        )
        themes=_theme_names(row.get("surge_reason"))
        reason=(
            row.get("surge_reason",{}).get("stock_reason")
            if isinstance(row.get("surge_reason"),dict)
            else None
        )

        normalized.append({
            "trade_date":trade_date.strftime("%Y%m%d"),
            "ts_code":code,
            "name":row.get("stock_chi_name"),
            "tag":_tag(row),
            "limit_times":int(row.get("limit_up_days") or 0),
            "first_limit_up":int(row.get("first_limit_up") or 0),
            "last_limit_up":int(row.get("last_limit_up") or 0),
            "open_num":int(row.get("break_limit_up_times") or 0),
            "turnover_rate":turnover_ratio,
            "turnover_estimated":turnover_estimated,
            "free_float_capital":free_cap,
            "buy_lock_volume_ratio":float(
                row.get("buy_lock_volume_ratio") or 0.0
            ),
            "sell_lock_volume_ratio":float(
                row.get("sell_lock_volume_ratio") or 0.0
            ),
            "prev_close":float(row.get("prev_close_price") or 0.0),
            "price":float(row.get("price") or 0.0),
            "change_percent":float(row.get("change_percent") or 0.0),
            "is_new_stock":bool(row.get("is_new_stock") or False),
            "listed_date":int(row.get("listed_date") or 0),
            "theme":"、".join(themes),
            "reason":reason,
            "pool_name":pool_name,
            "source":"xuangubao",
        })
    return pd.DataFrame(normalized)


class XuangubaoEvidenceProvider:
    """Public historical Xuangubao evidence client.

    This client intentionally covers market-emotion and limit-pool evidence.
    It does not pretend to provide historical per-stock 1-minute OHLC.
    """

    BASE="https://flash-api.xuangubao.com.cn/api"

    POOL_MAP={
        "涨停池":"limit_up",
        "跌停池":"limit_down",
        "炸板池":"limit_up_broken",
        "limit_up":"limit_up",
        "limit_down":"limit_down",
        "limit_up_broken":"limit_up_broken",
    }

    DEFAULT_INDICATORS=(
        "rise_count",
        "fall_count",
        "limit_up_count",
        "limit_down_count",
        "limit_up_broken_count",
        "limit_up_broken_ratio",
        "yesterday_limit_up_avg_pcp",
        "market_temperature",
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
        query=urlencode(params)
        url=f"{self.BASE}{path}?{query}"
        last=None
        for attempt in range(self.max_attempts):
            try:
                request=Request(
                    url,
                    headers={
                        "User-Agent":self.user_agent,
                        "Accept":"application/json",
                    },
                )
                with self.opener(
                    request,
                    timeout=self.timeout,
                ) as response:
                    payload=json.loads(
                        response.read().decode("utf-8")
                    )
                if not isinstance(payload,dict):
                    raise RuntimeError(
                        "Xuangubao returned non-object JSON"
                    )
                if payload.get("code") not in (None,0,200,20000):
                    raise RuntimeError(
                        f"Xuangubao API code={payload.get('code')} "
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
    def _date(day: date) -> str:
        return day.strftime("%Y-%m-%d")

    def pool_raw(
        self,
        trade_date: date,
        pool_name: str,
    ) -> list[dict]:
        pool=self.POOL_MAP.get(pool_name)
        if pool is None:
            raise ValueError(
                f"unsupported Xuangubao pool: {pool_name}"
            )
        payload=self._json(
            "/pool/detail",
            {
                "pool_name":pool,
                "date":self._date(trade_date),
            },
        )
        data=payload.get("data") or []
        if not isinstance(data,list):
            raise RuntimeError(
                "Xuangubao pool data is not a list"
            )
        return data

    def limit_list(
        self,
        trade_date: date,
        limit_type: str="涨停池",
    ) -> pd.DataFrame:
        pool=self.POOL_MAP.get(limit_type)
        if pool is None:
            raise ValueError(
                f"unsupported Xuangubao pool: {limit_type}"
            )
        return normalize_xgb_pool(
            self.pool_raw(trade_date,limit_type),
            trade_date=trade_date,
            pool_name=pool,
        )

    def theme_limit_list(
        self,
        trade_date: date,
    ) -> pd.DataFrame:
        pool=self.limit_list(
            trade_date,
            "涨停池",
        )
        if pool.empty:
            return pd.DataFrame(columns=[
                "trade_date",
                "ts_code",
                "theme",
                "status",
                "amount",
                "reason",
                "source",
            ])
        return pd.DataFrame({
            "trade_date":pool["trade_date"],
            "ts_code":pool["ts_code"],
            "theme":pool["theme"],
            "status":pool["tag"],
            "amount":pool["turnover_estimated"],
            "reason":pool["reason"],
            "source":"xuangubao",
        })

    def market_indicator_line(
        self,
        trade_date: date,
        fields: tuple[str,...] | list[str] | None=None,
    ) -> pd.DataFrame:
        fields=tuple(fields or self.DEFAULT_INDICATORS)
        payload=self._json(
            "/market_indicator/line",
            {
                "fields":",".join(fields),
                "date":self._date(trade_date),
            },
        )
        data=payload.get("data") or []
        if not isinstance(data,list):
            raise RuntimeError(
                "Xuangubao indicator data is not a list"
            )
        frame=pd.DataFrame(data)
        if not frame.empty and "timestamp" in frame.columns:
            frame["event_time"]=pd.to_datetime(
                frame["timestamp"],
                unit="s",
                utc=True,
            ).dt.tz_convert("Asia/Shanghai")
            same_day=(
                frame["event_time"]
                .dt.date
                ==trade_date
            )
            frame=frame.loc[
                same_day
            ].copy()

        if not frame.empty:
            frame["trade_date"]=trade_date.strftime("%Y%m%d")
            frame["source"]="xuangubao"
        return frame

    def market_close_snapshot(
        self,
        trade_date: date,
    ) -> dict:
        line=self.market_indicator_line(trade_date)
        if line.empty:
            return {}
        row=line.sort_values(
            "timestamp"
            if "timestamp" in line.columns
            else "trade_date"
        ).iloc[-1]
        return {
            key:row[key]
            for key in row.index
            if key not in {"event_time"}
        }

    def preflight(
        self,
        trade_date: date,
    ) -> dict:
        up=self.limit_list(trade_date,"涨停池")
        broken=self.limit_list(trade_date,"炸板池")
        down=self.limit_list(trade_date,"跌停池")
        indicators=self.market_indicator_line(trade_date)
        close=(
            indicators.iloc[-1].to_dict()
            if not indicators.empty
            else {}
        )
        return {
            "ok":(
                not indicators.empty
                and len(up)+len(broken)+len(down)>0
            ),
            "trade_date":trade_date.strftime("%Y%m%d"),
            "limit_up_count":len(up),
            "limit_up_broken_count":len(broken),
            "limit_down_count":len(down),
            "indicator_rows":len(indicators),
            "close_indicator":{
                key:close.get(key)
                for key in self.DEFAULT_INDICATORS
            },
            "limit_up_columns":list(up.columns),
        }
