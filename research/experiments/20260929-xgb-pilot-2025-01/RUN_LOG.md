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
