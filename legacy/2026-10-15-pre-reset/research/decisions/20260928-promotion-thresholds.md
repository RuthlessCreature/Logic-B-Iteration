# Decision: Freeze Promotion Thresholds Before Development Baseline

Date: 2026-09-28

Status: Accepted

## Context

Logic-B is intended to improve a trading system through chronological evidence,
not by moving evaluation criteria after seeing the development curve.

The repository already requires:

- conservative-fill positive expectancy;
- multi-fold stability;
- parameter-neighborhood stability;
- complexity control;
- B0-H semantic fidelity.

Those requirements were previously qualitative. Leaving their thresholds
undefined until after the development baseline would create a material
researcher-degree-of-freedom problem.

## Decision

Promotion thresholds are frozen in `config/b0.yaml` before the full
2024-09-30 through 2026-06-30 development baseline is inspected.

A candidate version is evaluated through conjunctive gates.

There is no compensating total score.

A strong return cannot offset:

- missing B0-H alignment;
- insufficient sample size;
- unstable parameter neighborhoods;
- excessive drawdown;
- excessive rule complexity.

## Frozen thresholds

### Conservative-fill baseline

- closed trades: at least 30;
- expectancy: strictly greater than 0;
- absolute maximum drawdown: no more than 25%.

### Walk-forward

- folds: at least 4;
- positive-return fold rate: at least 60%;
- positive-expectancy fold rate: at least 60%;
- closed validation trades: at least 20.

### B0-H alignment

- matched human labels: at least 80;
- action agreement: at least 80%;
- selected-code agreement: at least 70%;
- core-type agreement: at least 75%.

### Parameter neighborhood

- stability result must be explicitly PASS;
- at least 8 neighboring parameter configurations must be tested.

### Complexity

Per promoted version:

- no more than 1 primary rule change;
- no more than 2 new free parameters.

## Gate semantics

Each gate returns one of:

- PASS;
- FAIL;
- BLOCKED.

Overall status:

1. any FAIL -> FAIL;
2. otherwise any BLOCKED -> BLOCKED;
3. otherwise PASS.

Missing or non-finite metrics are BLOCKED rather than silently treated as
successful evidence.

## Threshold changes

A threshold may be changed only if:

1. the reason is documented in a new decision record;
2. the change is made before inspecting the evaluation set to which the new
   threshold will be applied;
3. the old threshold and reason for replacement remain in version history.

Blind-holdout results may not be used to redefine a threshold and then rerun
the same holdout as if it remained blind.

## Consequences

These thresholds are governance choices, not claims of universal market truth.

A strategy may be economically interesting and still remain BLOCKED because
the evidence package is incomplete.

That is intentional.
