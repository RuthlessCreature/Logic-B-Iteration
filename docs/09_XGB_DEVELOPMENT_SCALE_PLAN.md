# XGB Development Scale Plan

## Goal

Materialize the frozen B0 development interval without repeatedly downloading
already completed Xuangubao candidate slices.

Frozen development window:

```text
2024-09-30 ~ 2026-06-30
```

Blind holdout remains excluded:

```text
2026-07-01 ~ 2026-09-28
```

## Why the build is segmented

The public candidate-slice route performs historical symbol-day minute requests.
A full development build therefore contains substantially more requests than
the evidence layer alone.

The request workflow now restores and updates an Actions cache:

```text
xgb-development-v2-*
```

Existing partitions are reused. New requests should extend the cached
development lake rather than rebuild it from zero.

## Frozen segmentation

After the pilot passes, use the following non-overlapping research windows.

| Segment | Start | End |
|---|---|---|
| S01 | 2024-09-30 | 2024-12-31 |
| S02 | 2025-01-02 | 2025-03-31 |
| S03 | 2025-04-01 | 2025-06-30 |
| S04 | 2025-07-01 | 2025-09-30 |
| S05 | 2025-10-09 | 2025-12-31 |
| S06 | 2026-01-05 | 2026-03-31 |
| S07 | 2026-04-01 | 2026-06-30 |

Holiday gaps are intentionally left to the evidence provider's trading-day
detection. The final combined calendar is authoritative for replay.

## Per-segment gate

Each segment request must pass:

1. request date is no later than `development_end`;
2. unit tests;
3. public evidence/minute preflight on a known trading day;
4. evidence materialization;
5. candidate market materialization;
6. candidate-slice readiness, including zero indicator event-date failures.

Intermediate segment P&L is diagnostic only.

Do not tune B0 thresholds from segment P&L.

## Final development gate

Only after all seven segments are cached:

### 1. Full readiness

```bash
logic-b xgb-readiness \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb
```

Required result:

```text
ready=true
```

### 2. B0 baseline

Run all fill assumptions:

```text
optimistic
realistic
conservative
```

### 3. Walk-forward

Primary development diagnostic:

```text
realistic
```

Promotion risk gate:

```text
conservative
```

### 4. Parameter neighborhood

Run the frozen 8-neighbor grid under conservative fill.

No parameter search is allowed.

### 5. B0-H alignment

At least the frozen minimum human-label sample must be available before any
promotion result can become PASS.

## Failure handling

A failed segment is retried as the same segment.

Do not widen or move the segment merely because an endpoint failed.

Classifications:

- `CODE_FAIL`
- `DATA_SOURCE_FAIL`
- `MATERIALIZATION_FAIL`
- `READINESS_FAIL`
- `REPLAY_FAIL`
- `INFRA_PASS`

## Cache rule

The accumulated XGB cache is an execution cache, not a published dataset.

Raw third-party data is not committed to Git and is not promoted to a public
research artifact.

Only run outputs, metrics, manifests, and research decisions may be retained as
normal experiment artifacts.


## Calendar integrity gate

The public Xuangubao endpoints may return stale prior-session rows when queried
for a market holiday. Research data must therefore pass two independent date
checks:

1. the evidence provider retains market-indicator rows only when their
   Shanghai-local event date equals the requested date;
2. XGB readiness rejects any stored market-indicator partition whose event date
   does not equal its partition date.

A non-empty indicator payload without a timestamp is rejected because the date
cannot be verified.

The old cache namespace `xgb-development-v1-*` is permanently invalid for
research. Only `xgb-development-v2-*` or a later explicitly audited namespace
may be used.

A known-holiday live smoke test uses 2025-01-01 and requires the provider to
return `ok=false`.


## Segment-boundary context

Segment request windows remain non-overlapping for research accounting.

Market materialization and XGB readiness automatically prepend the most recent
cached trading day before the requested start date when one exists. This
context day is used only to resolve the first requested day's D-1 limit-up
candidate dependency.

Example:

```text
S01 ends: 2024-12-31
S02 starts: 2025-01-02

materialization/readiness context:
2024-12-31, 2025-01-02, ...
```

This prevents the first trading day of each segment from losing its candidate
slice while avoiding duplicate strategy-performance accounting across segments.

The final full-development replay remains the authoritative performance run.
Segment P&L is diagnostic only.
