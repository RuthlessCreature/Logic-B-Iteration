# Xuangubao Public Candidate-Slice Pipeline

## Purpose

This document defines the public-data fallback path used when the full Tushare
historical stack is unavailable or insufficient.

The Xuangubao path is intentionally a **candidate-slice pipeline** rather than a
full-market replacement. It materializes only the market data required to
replay Logic B0 candidates and held positions.

## Data model

### Evidence layer

For each trading day:

- `limit_up`
- `limit_down`
- `limit_break`
- `theme_limit_up`
- `market_indicator`

Source:

- Xuangubao public historical pool and market-indicator endpoints.

### Market layer

For each stock-day required by B0:

- `minute_1m`
- candidate/holding row in `daily`
- candidate/holding row in `limit_prices`
- `suspend`
- `stock_st`

The market layer is not expected to contain every A-share stock.

## Pre-close recovery

Historical Xuangubao minute payloads may expose a zero or missing archived
`pre_close_px`. The pipeline therefore resolves pre-close in the following
order:

1. existing canonical `limit_prices.pre_close` for the same stock-day;
2. previous trading day's cached `daily.close`;
3. previous trading day's limit-up pool final price;
4. Xuangubao historical kline `pre_close_px`, if valid.

The chosen value is recorded in minute-partition metadata.

## Price-limit derivation

For non-ST main-board stocks the fallback derives ±10% limits.

For ChiNext and STAR stocks it derives ±20% limits.

This is a fallback approximation and must not overwrite an existing canonical
price-limit row from a higher-authority source.

## ST handling

The public fallback does not currently provide an authoritative historical
daily ST-status table.

For D-day candidate filtering, the fallback may infer ST status from the D-1
limit-up evidence name when the name contains the ST marker.

The resulting rows are tagged:

```text
source=xuangubao_prior_name_inference
```

Limitation:

- an overnight ST-status change that is not represented in the D-1 evidence
  may be missed.

Therefore Xuangubao ST inference must not be described as equivalent to an
official historical risk-warning dataset.

## New-stock handling

When:

```yaml
exclude_no_limit_ipo_days: true
```

the public fallback conservatively excludes rows where:

```text
is_new_stock=true
```

before market-data fetching and replay.

This intentionally favors false exclusion over inventing a normal 10% or 20%
daily price limit for a stock that may still be in a no-price-limit IPO phase.

## Source precedence

Xuangubao market materialization is **fill-only** for canonical day rows.

If a stock-day already exists in canonical:

- `daily`, or
- `limit_prices`, or
- `stock_st`

the fallback does not silently replace it with lower-authority derived data.

Recommended practice is still to use a separate root:

```text
data-xgb/
```

for a pure public-data experiment.

## Initial preflight

Evidence endpoint:

```bash
logic-b preflight-xgb \
  --date 2026-06-30
```

Historical minute endpoint and derived market rows:

```bash
logic-b preflight-xgb-market \
  --date 2026-06-30
```

An explicit symbol and pre-close may be supplied when needed:

```bash
logic-b preflight-xgb-market \
  --date 2026-06-30 \
  --code 600000.SH \
  --pre-close 10.00
```

## Development data build

### 1. Evidence

```bash
logic-b fetch-xgb-evidence \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb
```

### 2. Candidate market slices

```bash
logic-b fetch-xgb-market \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb
```

For each D trading day, this step materializes market data for eligible D-1
limit-up candidates.

## Candidate-slice readiness

Use the Xuangubao-specific readiness gate:

```bash
logic-b xgb-readiness \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb
```

This gate checks:

- evidence partitions;
- candidate-slice market partitions;
- manifest hashes;
- expected candidate symbol-days;
- candidate daily-row coverage;
- candidate price-limit coverage;
- candidate minute-partition coverage.

It does **not** require full-market daily coverage.

## Replay

Normal pre-materialized replay:

```bash
logic-b run-b0 \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb \
  --fill all
```

If a held position later requires a stock-day that was not in the original
candidate prefetch set, enable on-demand refill:

```bash
logic-b run-b0 \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb \
  --fill all \
  --fetch-missing-minutes \
  --missing-minute-source xuangubao
```

The replay engine can request a complete missing symbol-day before evaluating a
held position's sellability.

## Walk-forward

```bash
logic-b walk-forward-b0 \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb \
  --fill realistic \
  --fetch-missing-minutes \
  --missing-minute-source xuangubao
```

## Audit boundary

The standard `audit-data` command assumes a fuller daily-market dataset and
should not be interpreted as the primary completeness gate for a pure
Xuangubao candidate-slice data root.

For the Xuangubao path, `xgb-readiness` is the authoritative completeness
gate.

Cross-source validation against higher-authority daily and price-limit data is
still recommended for sampled dates before publishing performance results.

## Integration test

Repository CI includes a small public-data integration workflow that exercises:

1. evidence preflight;
2. historical-minute preflight;
3. short evidence-window download;
4. candidate market materialization;
5. candidate-slice readiness;
6. short B0 replay.

The integration workflow is intentionally separate from the unit-test workflow
so temporary public-endpoint failures do not invalidate deterministic unit
tests.

## Research status

The Xuangubao pipeline is a fallback research path.

Performance produced by this path should be reported with its source and
limitations. It must not be mixed silently with results from a different
historical data stack.
