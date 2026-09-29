# XGB Pilot Acceptance Gate — 2025-01

Request:

```text
research/run_requests/20260929-xgb-pilot-2025-01.json
```

Window:

```text
2024-12-27 ~ 2025-01-27
```

## Purpose

This run is an infrastructure/data pilot, not a strategy-selection experiment.

It must not be used to tune B0 thresholds.

## Hard acceptance criteria

The pilot passes only when all conditions below are satisfied.

### 1. CI / code integrity

- deterministic unit tests pass;
- the research workflow completes successfully.

### 2. Public data preflight

Both must pass:

- Xuangubao evidence preflight;
- Xuangubao historical-minute preflight.

### 3. Candidate-slice readiness

The authoritative XGB readiness check must report:

```text
ready = true
```

Required candidate symbol-days must have complete:

- evidence;
- daily candidate row;
- price-limit row;
- minute partition;
- valid manifest/hash.

Any missing required candidate-minute partition is a pilot failure.

### 4. Replay completeness

The following fill models must all finish:

- optimistic;
- realistic;
- conservative.

The runner must not terminate due to:

- missing dataset;
- missing held-position symbol-day;
- malformed price-limit row;
- point-in-time contract violation.

### 5. Research-governance integrity

The pilot must not:

- touch the blind holdout;
- change B0 strategy thresholds based on pilot P&L;
- alter the frozen core hierarchy;
- use the pilot result to promote a strategy version.

## Observational outputs

The following are recorded but are **not pass/fail strategy criteria** for this pilot:

- total return;
- expectancy;
- win rate;
- drawdown;
- closed-trade count;
- fill-model spread;
- endpoint runtime.

A negative return does not fail this infrastructure pilot.

A positive return does not validate B0.

## Scale-up condition

Only after this pilot passes may the public-data pipeline be expanded to a
larger development slice.

Recommended next scale:

```text
2025-01-01 ~ 2025-03-31
```

followed by the frozen full development interval:

```text
2024-09-30 ~ 2026-06-30
```

The blind holdout remains locked.


## Fixture correction

The first workflow attempt used 2025-01-31 as the preflight date. That date is
inside the official 2025 Spring Festival market closure. The pilot fixture was
therefore corrected to 2025-01-27, the last Monday before the closure.

This correction changes neither B0 strategy rules nor acceptance thresholds.
