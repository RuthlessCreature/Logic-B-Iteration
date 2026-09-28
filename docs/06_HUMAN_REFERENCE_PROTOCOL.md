# B0-H Human Reference Protocol

## Purpose

B0-H is the human-reference representation of Logic A. Its role is not to
produce the final historical return directly. Its role is to define what
Logic A actually meant at a decision point, so that B0-P can be checked for
semantic fidelity before return optimization begins.

## Labeling rule

A B0-H label must be created using only information that was available at the
specified decision time.

For example, a label at 09:35 may use:

- D-1 limit-up system and board hierarchy;
- D-1 theme structure;
- opening auction information observable by the market;
- price/volume information up to 09:35;
- known market-regime evidence from completed prior sessions.

It may not use:

- the 10:00, 14:30 or close outcome of the same day;
- the next-day premium;
- the realized P&L;
- knowledge that a stock later became the cycle leader.

## Sampling plan

The first reference set should be stratified rather than purely random.

Recommended minimum:

- 40 ATTACK/TRIAL decision points;
- 40 NEUTRAL decision points;
- 40 RETREAT/ICE decision points;
- 30 high-board competition days;
- 30 middle-board-heavy days;
- 30 strong-theme breadth days;
- 30 weak-theme / isolated limit-up days;
- representative one-price, T-shape and turnover-board cases.

A single day can satisfy multiple strata.

## Label fields

See `schemas/human_reference.schema.yaml`.

The label should explicitly record:

- whether Logic A allows a new position;
- selected core, if any;
- core type;
- candidate set;
- rejected candidates and reasons;
- theme evidence;
- rationale;
- confidence.

## Alignment metrics

B0-P is compared to B0-H before P&L optimization.

Primary metrics:

- action agreement;
- selected-code agreement when B0-H says BUY_CORE;
- core-type agreement;
- label coverage.

P&L is intentionally excluded from this stage.

## Promotion rule

A proxy change that increases historical return while reducing B0-H alignment
is not automatically an improvement to Logic A. It should be classified as a
new strategy hypothesis and evaluated as B1+, not silently folded into B0.

## Disagreement review

Every disagreement is assigned one of:

- H-ERROR: human label is later judged inconsistent with the frozen protocol;
- P-ERROR: proxy failed to express Logic A;
- AMBIGUOUS: Logic A itself is underspecified;
- DATA-GAP: required point-in-time evidence is unavailable.

AMBIGUOUS cases should produce a specification decision before additional
threshold tuning.
