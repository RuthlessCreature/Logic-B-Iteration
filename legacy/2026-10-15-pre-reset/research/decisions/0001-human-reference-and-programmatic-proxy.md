# Decision 0001 — Split B0 into Human Reference and Programmatic Proxy

Date: 2026-09-28
Status: Accepted

## Context

Logic A contains high-information concepts such as “总龙头”“板块核心容量”“最强换手前排”“退潮”“冰点”“辨识度”。

These concepts are useful to a human trader but are not yet deterministic functions of raw market data.

Directly translating them into arbitrary thresholds would silently change the strategy before the baseline is measured.

## Decision

Maintain two B0 representations:

### B0-H
Human reference implementation.

Used for:
- historical manual review;
- labeling representative days;
- comparing machine decisions with intended Logic A;
- resolving semantic ambiguity.

### B0-P
Programmatic proxy.

Used for:
- full historical replay;
- systematic backtest;
- parameter sensitivity;
- version iteration.

## Consequence

The project will measure two different errors:

1. **Strategy error**: B0-H itself chooses a losing setup.
2. **Proxy error**: B0-P fails to represent what B0-H would have chosen.

Without this separation, proxy mistakes could be misinterpreted as evidence that Logic A is bad, or profitable overfitting could be misinterpreted as an improvement to Logic A.

## Rejected Alternative

“直接给所有语义设阈值，然后用收益率优化阈值。”

Rejected because it allows the optimizer to redefine the meaning of Logic A using future outcomes.
