from __future__ import annotations

from dataclasses import asdict,dataclass

import pandas as pd

from .ingest import HistoricalIngestor
from .storage import LocalParquetStore
from .universe import codes_with_valid_price_limits,filter_boards


@dataclass(frozen=True)
class ReadinessReport:
    trade_days: int
    daily_partitions_expected: int
    daily_partitions_missing: int
    manifest_failures: int
    minute_partitions_expected: int
    minute_partitions_missing: int
    missing_daily: list[str]
    bad_manifests: list[str]
    missing_minutes: list[str]

    @property
    def ready(self) -> bool:
        return (
            self.daily_partitions_missing==0
            and self.manifest_failures==0
            and self.minute_partitions_missing==0
        )

    def as_dict(self) -> dict:
        out=asdict(self)
        out["ready"]=self.ready
        return out


def _codes(frame: pd.DataFrame | None) -> set[str]:
    if (
        frame is None
        or frame.empty
        or "ts_code" not in frame.columns
    ):
        return set()
    return set(frame["ts_code"].astype(str))


def assess_data_readiness(
    *,
    store: LocalParquetStore,
    trade_dates: list[str],
    include_boards: tuple[str,...] | None,
    exclude_st: bool,
    exclude_no_limit_ipo_days: bool,
) -> ReadinessReport:
    """Check whether cached data can run B0 without mid-replay surprises."""

    dates=sorted(
        pd.to_datetime(trade_dates)
        .strftime("%Y%m%d")
        .tolist()
    )

    required=list(
        HistoricalIngestor.DAILY_DATASETS
    )
    missing_daily=[]
    bad_manifests=[]

    for day in dates:
        for dataset in required:
            token=f"{dataset}:{day}"
            if not store.exists(dataset,day):
                missing_daily.append(token)
            elif not store.verify(dataset,day):
                bad_manifests.append(token)

    missing_minutes=[]
    expected_minutes=0

    for i in range(1,len(dates)):
        day=dates[i]
        prev=dates[i-1]

        # If the daily dependencies are absent we cannot derive a reliable
        # expected candidate set; the missing daily list already blocks ready.
        required_for_candidates=[
            ("limit_up",prev),
            ("daily",day),
            ("limit_prices",day),
            ("suspend",day),
        ]
        if exclude_st:
            required_for_candidates.append(
                ("stock_st",day)
            )
        if any(
            not store.exists(dataset,key)
            for dataset,key in required_for_candidates
        ):
            continue

        candidates=store.read_frame(
            "limit_up",
            prev,
        )

        if include_boards is not None:
            candidates=filter_boards(
                candidates,
                include_boards,
            )

        excluded=_codes(
            store.read_frame(
                "suspend",
                day,
            )
        )
        if exclude_st:
            excluded|=_codes(
                store.read_frame(
                    "stock_st",
                    day,
                )
            )

        if excluded and not candidates.empty:
            candidates=candidates[
                ~candidates["ts_code"]
                .astype(str)
                .isin(excluded)
            ].copy()

        limits=store.read_frame(
            "limit_prices",
            day,
        )
        if exclude_no_limit_ipo_days:
            valid=codes_with_valid_price_limits(
                limits
            )
            if not candidates.empty:
                candidates=candidates[
                    candidates["ts_code"]
                    .astype(str)
                    .isin(valid)
                ].copy()

        daily_codes=_codes(
            store.read_frame(
                "daily",
                day,
            )
        )
        codes=(
            candidates["ts_code"]
            .astype(str)
            .tolist()
            if not candidates.empty
            and "ts_code" in candidates.columns
            else []
        )

        for code in sorted(set(codes)):
            if code not in daily_codes:
                continue
            expected_minutes+=1
            partition=f"{day}/{code}"
            if not store.exists(
                "minute_1m",
                partition,
            ):
                missing_minutes.append(
                    partition
                )
            elif not store.verify(
                "minute_1m",
                partition,
            ):
                bad_manifests.append(
                    f"minute_1m:{partition}"
                )

    return ReadinessReport(
        trade_days=len(dates),
        daily_partitions_expected=
            len(dates)*len(required),
        daily_partitions_missing=
            len(missing_daily),
        manifest_failures=
            len(bad_manifests),
        minute_partitions_expected=
            expected_minutes,
        minute_partitions_missing=
            len(missing_minutes),
        missing_daily=missing_daily,
        bad_manifests=bad_manifests,
        missing_minutes=missing_minutes,
    )
