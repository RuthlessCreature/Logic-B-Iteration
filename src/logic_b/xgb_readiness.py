from __future__ import annotations

from dataclasses import asdict,dataclass

import pandas as pd

from .storage import LocalParquetStore
from .universe import (
    codes_with_valid_price_limits,
    filter_boards,
)


EVIDENCE_DATASETS=(
    "limit_up",
    "limit_down",
    "limit_break",
    "theme_limit_up",
    "market_indicator",
)

MARKET_DAY_DATASETS=(
    "daily",
    "limit_prices",
    "suspend",
    "stock_st",
)


@dataclass(frozen=True)
class XgbReadinessReport:
    trade_days: int
    evidence_partitions_missing: int
    market_partitions_missing: int
    manifest_failures: int
    candidate_symbol_days_expected: int
    candidate_daily_missing: int
    candidate_limit_missing: int
    minute_partitions_missing: int
    missing_evidence: list[str]
    missing_market: list[str]
    bad_manifests: list[str]
    missing_candidate_daily: list[str]
    missing_candidate_limits: list[str]
    missing_minutes: list[str]

    @property
    def ready(self) -> bool:
        return (
            self.evidence_partitions_missing==0
            and self.market_partitions_missing==0
            and self.manifest_failures==0
            and self.candidate_daily_missing==0
            and self.candidate_limit_missing==0
            and self.minute_partitions_missing==0
        )

    def as_dict(self) -> dict:
        out=asdict(self)
        out["ready"]=self.ready
        return out


def _codes(
    frame: pd.DataFrame | None,
) -> set[str]:
    if (
        frame is None
        or frame.empty
        or "ts_code" not in frame.columns
    ):
        return set()
    return set(
        frame["ts_code"].astype(str)
    )


def assess_xgb_candidate_readiness(
    *,
    store: LocalParquetStore,
    trade_dates: list[str],
    include_boards: tuple[str,...] | None,
    exclude_st: bool,
    exclude_no_limit_ipo_days: bool,
) -> XgbReadinessReport:
    """Validate the XGB candidate-slice data lake for B0 replay.

    Unlike the Tushare readiness gate, this function does not expect full
    market daily/limit coverage. It only requires complete symbol-day data for
    stocks that can actually enter the D-day candidate set.
    """
    dates=sorted(
        pd.to_datetime(
            trade_dates
        ).strftime("%Y%m%d").tolist()
    )

    missing_evidence=[]
    missing_market=[]
    bad_manifests=[]

    for day in dates:
        for dataset in EVIDENCE_DATASETS:
            token=f"{dataset}:{day}"
            if not store.exists(
                dataset,
                day,
            ):
                missing_evidence.append(
                    token
                )
            elif not store.verify(
                dataset,
                day,
            ):
                bad_manifests.append(
                    token
                )

        for dataset in MARKET_DAY_DATASETS:
            token=f"{dataset}:{day}"
            if not store.exists(
                dataset,
                day,
            ):
                missing_market.append(
                    token
                )
            elif not store.verify(
                dataset,
                day,
            ):
                bad_manifests.append(
                    token
                )

    expected=0
    missing_daily=[]
    missing_limits=[]
    missing_minutes=[]

    for index in range(1,len(dates)):
        day=dates[index]
        prev=dates[index-1]

        prior=store.read_optional(
            "limit_up",
            prev,
        )
        if (
            prior is None
            or prior.empty
            or "ts_code" not in prior.columns
        ):
            continue

        candidates=prior.copy()
        if include_boards is not None:
            candidates=filter_boards(
                candidates,
                include_boards,
            )

        suspend=store.read_optional(
            "suspend",
            day,
        )
        st=store.read_optional(
            "stock_st",
            day,
        )
        excluded=_codes(
            suspend
        )
        if exclude_st:
            excluded|=_codes(st)

        if excluded and not candidates.empty:
            candidates=candidates[
                ~candidates["ts_code"]
                .astype(str)
                .isin(excluded)
            ].copy()

        if (
            exclude_no_limit_ipo_days
            and not candidates.empty
            and "is_new_stock" in candidates.columns
        ):
            flags=(
                candidates["is_new_stock"]
                .fillna(False)
                .astype(bool)
            )
            candidates=candidates[
                ~flags
            ].copy()

        daily=store.read_optional(
            "daily",
            day,
        )
        limits=store.read_optional(
            "limit_prices",
            day,
        )
        daily_codes=_codes(daily)
        limit_codes=_codes(limits)

        if exclude_no_limit_ipo_days:
            valid_limit_codes=(
                codes_with_valid_price_limits(
                    limits
                )
                if limits is not None
                else set()
            )
        else:
            valid_limit_codes=limit_codes

        codes=sorted(
            set(
                candidates["ts_code"]
                .astype(str)
                .tolist()
            )
        )
        expected+=len(codes)

        for code in codes:
            token=f"{day}/{code}"

            if code not in daily_codes:
                missing_daily.append(
                    token
                )

            if code not in limit_codes:
                missing_limits.append(
                    token
                )
            elif (
                exclude_no_limit_ipo_days
                and code not in valid_limit_codes
            ):
                # The row exists but intentionally has no valid limits.
                # It is excluded from B0 rather than treated as missing data.
                continue

            if not store.exists(
                "minute_1m",
                token,
            ):
                missing_minutes.append(
                    token
                )
            elif not store.verify(
                "minute_1m",
                token,
            ):
                bad_manifests.append(
                    f"minute_1m:{token}"
                )

    return XgbReadinessReport(
        trade_days=len(dates),
        evidence_partitions_missing=
            len(missing_evidence),
        market_partitions_missing=
            len(missing_market),
        manifest_failures=
            len(bad_manifests),
        candidate_symbol_days_expected=
            expected,
        candidate_daily_missing=
            len(missing_daily),
        candidate_limit_missing=
            len(missing_limits),
        minute_partitions_missing=
            len(missing_minutes),
        missing_evidence=
            missing_evidence,
        missing_market=
            missing_market,
        bad_manifests=
            bad_manifests,
        missing_candidate_daily=
            missing_daily,
        missing_candidate_limits=
            missing_limits,
        missing_minutes=
            missing_minutes,
    )
