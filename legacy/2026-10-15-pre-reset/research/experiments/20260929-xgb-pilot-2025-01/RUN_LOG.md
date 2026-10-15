# XGB Pilot Run Log — January 2025

Frozen experiment:

- window: 2024-12-27 .. 2025-01-27
- blind holdout: not touched
- B0 threshold tuning: forbidden
- purpose: infrastructure/data/replay validation only

## Attempt 1

Workflow run:

```text
36520855952
```

Result:

```text
DATA_SOURCE/PREFLIGHT FAIL
```

Cause:

The preflight fixture used 2025-01-31, which is inside the official 2025
Spring Festival market closure.

Action:

- corrected preflight/end fixture to 2025-01-27;
- no strategy rule changed;
- no acceptance threshold changed.

## Attempt 2

Workflow run:

```text
36521142458
```

Result:

```text
REQUEST RESOLUTION FAIL
```

Cause:

The shell step wrote `REQUEST_FILE` to `$GITHUB_ENV` and then attempted to
read it from Python in the same step. GitHub Actions only injects that file
into subsequent steps.

Action:

- exported `REQUEST_FILE` in the current shell;
- later moved request validation into tested Python code and CLI;
- no strategy rule changed.

## Attempt 3

Formal parameterized workflow run:

```text
36521214434
```

Data results:

```text
trade_days: 22
evidence: PASS
candidate market materialization: PASS
candidate_symbol_days materialized: 1426
candidate_symbol_days expected by readiness: 1183
candidate daily missing: 0
candidate limit missing: 0
minute partitions missing: 0
manifest failures: 0
ready: true
```

Observed throughput:

```text
evidence: ~3m26s
candidate market: ~13m24s
```

Replay result:

```text
REPLAY_FAIL
```

Failure:

```text
MissingReplayDataError:
no limit price for held 000759.SZ on 20250102
```

Root cause:

Candidate-slice readiness correctly guarantees D market data for D-1 limit-up
candidates. A position bought on D can still be held on D+1 even when the stock
is not part of the D limit-up pool. The old replay version checked the held
stock's next-day limit price before on-demand symbol-day materialization.

Fix:

Current main calls on-demand market materialization for the held symbol before
loading the day's exit state. A dedicated replay regression test now covers the
case where the held stock is absent from the next day's candidate slice.

No strategy threshold or core-selection rule changed.

## Attempt 4

Triggered by commit:

```text
5da1fd78d8a2bd61ba4ad48958eb5bd2aec3d71d
```

Workflow run:

```text
36522501707
```

Purpose:

Re-run the exact frozen pilot window and acceptance gate on the repaired replay
state machine.

This attempt also uses the hardened research workflow:

- tested request validator;
- serialized XGB materialization;
- explicit restore/save development cache;
- structured market-materialization progress;
- post-run attribution;
- expanded execution/performance diagnostics.

Status:

```text
IN PROGRESS
```


## Throughput caveat

Attempt 3 overlapped with a deprecated diagnostic run that was hitting the same
public Xuangubao endpoints at the same time. Its observed market-materialization
runtime must therefore **not** be linearly extrapolated to the full development
window.

Future development requests are serialized by workflow concurrency and reuse an
incremental cache. Scale decisions should use single-run segment timings only.


## Attempt 5

Workflow run:

```text
36655033818
```

Data/cache result:

- request validation: PASS
- cache restore: PASS
- evidence: PASS
- candidate market: PASS
- cache save: PASS
- candidate readiness: PASS

Replay advanced beyond the prior held-symbol limit-price failure.

New failure:

```text
KeyError: 'ts_code'
at replay candidate filtering
```

Root cause:

A valid no-candidate day can arrive as a zero-column DataFrame. The replay
runner treated an empty pool as normal in some branches but later indexed
`candidates["ts_code"]` unconditionally when applying valid-price-limit
filters.

Fix:

Candidate frames are now normalized to include an empty `ts_code` column
before any filtering. A dedicated regression test verifies that a zero-column
empty candidate partition produces a normal CASH day rather than an exception.

No strategy threshold or core-selection rule changed.


## Attempt 6 — PASS

Workflow run:

```text
36655350711
```

Final classification:

```text
INFRA_PASS
```

Hard-gate result:

- request validation: PASS
- deterministic tests: PASS (104 tests)
- public endpoint preflight: PASS
- evidence materialization: PASS
- candidate market materialization: PASS
- development cache restore/save: PASS
- candidate readiness: PASS
- B0 optimistic replay: PASS
- B0 realistic replay: PASS
- B0 conservative replay: PASS
- post-run attribution: PASS
- final enforce gate: PASS

Cache-resume observation:

- restored XGB cache: ~8 MB;
- evidence materialization: ~1.8 s;
- candidate market resume: ~3.4 s;
- candidate symbol-days represented: 1426.

This confirms that the incremental development-cache path is operational.

Pilot-only replay observations:

| Fill | Total return | MDD | Closed trades | Win rate | Expectancy | Buy unfilled | Sell unfilled |
|---|---:|---:|---:|---:|---:|---:|---:|
| optimistic | 23.52% | -10.05% | 5 | 60% | 4.55% | 0% | 16.67% |
| realistic | 24.50% | -10.05% | 4 | 75% | 5.88% | 20% | 20% |
| conservative | 21.29% | -12.96% | 4 | 75% | 5.33% | 20% | 33.33% |

These returns are **not** strategy-validation evidence. The pilot contains only a
small number of closed trades and exists to validate the infrastructure and
execution model.

Conservative execution diagnostics include:

- one suspended sell attempt;
- one sealed-limit buy block;
- one additional conservative sell block;
- one tail loss <= -5%.

No B0 threshold or core-selection rule was changed from these results.


## Calendar integrity invalidation

A post-pilot audit found that the Xuangubao market-indicator endpoint can return
stale rows from the previous trading day when queried on a market holiday.

The provider previously overwrote those rows with the requested date without
checking the returned timestamp. This caused 2025-01-01 to appear in the pilot
trade calendar.

Impact:

- Attempt 6 remains useful as an infrastructure/replay-path test.
- Attempt 6 P&L, trade counts, regime sequence and strategy statistics are
  **INVALIDATED** as research evidence.
- Any development segment built from cache version `xgb-development-v1` is
  invalidated.
- The blind holdout was not touched.

Corrective action:

1. XGB indicator rows are now filtered by Shanghai-local event date.
2. Non-empty indicator payloads without timestamps are rejected.
3. Development cache namespace is bumped from
   `xgb-development-v1` to `xgb-development-v2`.
4. The pilot must be rerun from a clean v2 cache before development expansion
   resumes.

No B0 strategy threshold was changed.


## Live calendar-fix verification

Workflow:

```text
Xuangubao Provider Smoke
run 36656484189
```

Result: PASS.

The live provider check queried the known A-share market holiday 2025-01-01
and returned:

```text
ok=false
trade_date=20250101
indicator_rows=0
limit_up_count=0
limit_down_count=0
```

The same smoke run also cross-checked normal trading sessions and confirmed that
limit-up, broken-board and limit-down pool counts matched the close
market-indicator counts.

## Invalid S01 cancellation

The first S01 development run:

```text
36655583632
```

was launched before the calendar-integrity defect was found and used the
invalid v1 cache/data contract. It was explicitly preempted and ended as
`cancelled`.

Its outputs must not be used for research or promotion decisions.
