from __future__ import annotations

from dataclasses import dataclass,asdict

import pandas as pd


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    message: str
    count: int=1

    def as_dict(self) -> dict:
        return asdict(self)


def _codes(frame: pd.DataFrame) -> set[str]:
    if frame is None or frame.empty or "ts_code" not in frame.columns:
        return set()
    return set(frame["ts_code"].astype(str))


def audit_daily_bundle(
    *,
    daily: pd.DataFrame,
    limit_prices: pd.DataFrame,
    limit_up: pd.DataFrame,
    limit_down: pd.DataFrame,
    limit_break: pd.DataFrame | None=None,
) -> list[AuditIssue]:
    issues: list[AuditIssue]=[]

    required_daily={"ts_code","open","high","low","close"}
    required_limit={"ts_code","pre_close","up_limit","down_limit"}
    md=required_daily-set(daily.columns)
    ml=required_limit-set(limit_prices.columns)
    if md:
        issues.append(AuditIssue(
            "ERROR","DAILY_COLUMNS",
            f"daily missing columns: {sorted(md)}",len(md),
        ))
    if ml:
        issues.append(AuditIssue(
            "ERROR","LIMIT_COLUMNS",
            f"limit_prices missing columns: {sorted(ml)}",len(ml),
        ))
    if md or ml:
        return issues

    if daily["ts_code"].astype(str).duplicated().any():
        n=int(daily["ts_code"].astype(str).duplicated(keep=False).sum())
        issues.append(AuditIssue(
            "ERROR","DAILY_DUPLICATE_CODE",
            "duplicate ts_code rows in daily",n,
        ))

    if limit_prices["ts_code"].astype(str).duplicated().any():
        n=int(limit_prices["ts_code"].astype(str).duplicated(keep=False).sum())
        issues.append(AuditIssue(
            "ERROR","LIMIT_DUPLICATE_CODE",
            "duplicate ts_code rows in limit_prices",n,
        ))

    d=daily.copy()
    for col in ["open","high","low","close"]:
        d[col]=pd.to_numeric(d[col],errors="coerce")

    invalid=(
        (d["low"]>d["high"])
        |(d["open"]<d["low"])
        |(d["open"]>d["high"])
        |(d["close"]<d["low"])
        |(d["close"]>d["high"])
    )
    if invalid.any():
        issues.append(AuditIssue(
            "ERROR","INVALID_OHLC",
            "daily OHLC violates low <= open/close <= high",
            int(invalid.sum()),
        ))

    lim=limit_prices.copy()
    for col in ["pre_close","up_limit","down_limit"]:
        lim[col]=pd.to_numeric(lim[col],errors="coerce")

    market=d.merge(
        lim[["ts_code","up_limit","down_limit"]],
        on="ts_code",how="left",
    )
    missing_limits=market["up_limit"].isna()|market["down_limit"].isna()
    if missing_limits.any():
        issues.append(AuditIssue(
            "ERROR","MISSING_LIMIT_PRICE",
            "tradable daily row has no price-limit row",
            int(missing_limits.sum()),
        ))

    tol=0.002
    above=(market["close"]>market["up_limit"]+tol)&~missing_limits
    below=(market["close"]<market["down_limit"]-tol)&~missing_limits
    if above.any() or below.any():
        issues.append(AuditIssue(
            "ERROR","CLOSE_OUTSIDE_LIMIT",
            "daily close lies outside official price limits",
            int(above.sum()+below.sum()),
        ))

    check=market.set_index(market["ts_code"].astype(str))
    for pool,name,target in [
        (limit_up,"LIMIT_UP_CLOSE_MISMATCH","up_limit"),
        (limit_down,"LIMIT_DOWN_CLOSE_MISMATCH","down_limit"),
    ]:
        codes=_codes(pool)
        available=[c for c in codes if c in check.index]
        missing=codes-set(available)
        if missing:
            issues.append(AuditIssue(
                "ERROR",f"{name}_NO_DAILY",
                f"{len(missing)} pool codes missing from daily/limits",
                len(missing),
            ))
        if available:
            sub=check.loc[available]
            mismatch=(sub["close"]-sub[target]).abs()>tol
            if mismatch.any():
                issues.append(AuditIssue(
                    "ERROR",name,
                    f"{name}: pool classification disagrees with official close/limit",
                    int(mismatch.sum()),
                ))

    up=_codes(limit_up)
    down=_codes(limit_down)
    overlap=up&down
    if overlap:
        issues.append(AuditIssue(
            "ERROR","UP_DOWN_POOL_OVERLAP",
            "same code appears in limit-up and limit-down pools",
            len(overlap),
        ))

    if limit_break is not None and not limit_break.empty:
        broken=_codes(limit_break)
        overlap_break=broken&up
        if overlap_break:
            issues.append(AuditIssue(
                "WARN","BREAK_AND_LIMIT_UP_OVERLAP",
                "same code appears in break and final limit-up pools",
                len(overlap_break),
            ))

    return issues


def summarize_issues(issues: list[AuditIssue]) -> dict:
    return {
        "errors":sum(x.count for x in issues if x.severity=="ERROR"),
        "warnings":sum(x.count for x in issues if x.severity=="WARN"),
        "issue_types":len(issues),
        "issues":[x.as_dict() for x in issues],
    }
