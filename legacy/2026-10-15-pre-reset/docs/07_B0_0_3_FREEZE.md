# Logic B0.0.3 Freeze Record

## Status

**Frozen development baseline**

- Logic specification: `B0.0.3`
- Programmatic proxy: `B0-P.1`
- Freeze date: 2026-09-28
- Development window: 2024-09-30 through 2026-06-30
- Blind holdout: 2026-07-01 through 2026-09-28

No historical performance claim is part of this freeze record.

## Purpose

This freeze separates strategy-definition work from empirical evaluation.

After this point, B0.0.3 should be evaluated as written. Changes motivated by
observed development-set or holdout performance must not be silently folded
back into B0.0.3.

## Frozen strategy semantics

### Candidate universe

- Previous-trading-day THS limit-up pool.
- Main board, ChiNext and STAR Market only.
- Exclude current ST / risk-warning stocks.
- Exclude current suspended stocks.
- Exclude candidates without valid official daily price limits.

### Core hierarchy

1. Total market leader.
2. Sector capacity core.
3. Strongest turnover front.
4. Explicit catch-up core.

The highest available hierarchy is selected first. If that candidate fails
confirmation or tradability gates, the result is CASH. A lower-tier candidate
does not replace it.

### Theme evidence

Theme-dependent core labels require point-in-time historical KPL evidence from
the previous trading day. Latest-membership concept data is not used to
reconstruct historical themes.

### Market gate

New entries are blocked in RETREAT and ICE regimes.

### Decision checkpoint

Primary baseline checkpoint: 09:35.

A completed 09:35 bar may contribute to the signal, but execution may only use
later bars.

### Portfolio

- Maximum one position.
- Full-target baseline.
- A-share T+1 enforced.
- No same-day liquidation.

### Baseline exit

`E0_NEXT_DAY_0935`:

- attempt full liquidation after the first eligible next-day 09:35 checkpoint;
- if limit-down locked, remain invested and retry on subsequent sessions;
- if suspended, remain invested and retry after trading resumes.

### Execution models

- optimistic;
- realistic;
- conservative.

One-price/sealed limit-up states and locked limit-down states are explicitly
modeled rather than assumed fillable.

### Trading costs

Configurable:

- broker commission;
- minimum commission;
- transfer fee;
- sell-side stamp duty.

## Frozen research protocol

### Development window

2024-09-30 through 2026-06-30.

### Walk-forward

Default parameters:

- minimum training history: 120 trading days;
- validation window: 40 trading days;
- step: 40 trading days;
- warmup: 2 trading days.

Warmup P&L is excluded from validation performance. Validation equity is
anchored to the actual portfolio value at the end of warmup.

### Blind holdout

2026-07-01 through 2026-09-28.

The holdout is locked by default. It is not used for iterative rule changes.

## Required evaluation sequence

1. Run provider preflight.
2. Download development daily data.
3. Run data audit.
4. Download candidate minute data.
5. Pass data readiness.
6. Run B0 across optimistic / realistic / conservative fills.
7. Run chronological walk-forward.
8. Compare B0-P with B0-H human-reference labels.
9. Record development findings and failure clusters.
10. Only after strategy freeze and review, unlock blind holdout once.

## Allowed changes after freeze

The following may be fixed without creating a new strategy version only when
they do not change intended B0 semantics:

- parsing bugs;
- data-provider schema adaptation;
- incorrect timestamp handling;
- manifest/storage defects;
- execution implementation bugs where behavior contradicts this freeze record;
- missing tests;
- documentation corrections.

Any such change must include a regression test and a changelog entry.

## Changes requiring a new strategy hypothesis/version

Examples:

- new signal factors;
- new thresholds selected because they improve backtest performance;
- changing core hierarchy;
- allowing lower-tier fallback;
- changing market gate semantics;
- changing decision checkpoint;
- changing baseline exit logic;
- adding position sizing rules;
- using additional theme/flow/news features for selection;
- parameter tuning based on blind-holdout results.

These changes belong to B1+ experiments and must not be relabeled as B0.0.3.

## Known empirical gaps at freeze time

- Real development-set history has not yet been downloaded in this chat session.
- Historical minute-data entitlement has not been verified from the user's
  Tushare account in this session.
- B0-H reference labels have not yet reached the planned stratified sample size.
- No development baseline return, walk-forward performance or blind-holdout
  result has been accepted.

Therefore B0.0.3 is a **research baseline**, not evidence of profitability.
