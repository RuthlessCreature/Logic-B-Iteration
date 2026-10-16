# H01 Phase-A Evidence Ledger — 2026-10-13

Status: PARTIAL SOURCE AUDIT / H01 PREDICTIVE CLAIM BLOCKED

## Confirmed artifact recovered from prior historical runner

Source run: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/36656336352
Date run: 2026-09-30
Period: 2024-12-27 .. 2025-01-27
Artifact: xgb-pilot-2025-01-v2-2024-12-27_2025-01-27 (GitHub Actions)

Historical XGB candidate-data readiness (from archive):
- trade_days = 21
- candidate_symbol_days_expected = 1228
- missing evidence / market partitions = 0
- manifest_failures = 0
- candidate daily / limit / minute missing = 0
- ready = true

B0.0.3 local replay results with T+1 and commission/transfer/stamp accounting:

| Fill model | Total portfolio return | Max drawdown | Closed trades | Win fraction | Entry unfilled fraction |
|---|---:|---:|---:|---:|---:|
| optimistic | +23.52% | -10.05% | 5 | 60% | 0% |
| realistic | +24.50% | -10.05% | 4 | 75% | 20% |
| conservative | +21.29% | -12.96% | 4 | 75% | 20% |

**Interpretation: not a validated behavioral trading edge.** Only 4 closed realistic/conservative trades, a 21-session selected window, B0-specific cohort slices, and approximate fills. Annualizing this result would be misleading. It does not meet the existing 30 closed-trade B0 promotion requirement. No claim that these are real-account P&Ls.

The GitHub Actions run marked INFRA_PASS. This means its mechanical workflow succeeded, NOT that the strategy passed independent validation. Source hash validity and symbol-day readiness do not independently establish all-market event-list completeness; the H01 vendor count cross-check is separate.

## New code on branch research/behavioral-edge-20261013

- Observable market-wide limit-up repeat ratio, manifest and date guard
- H01-A expansion-window baseline vs lagged simulated follower-profit signal
- B0 replay daily equity -> synthetic follower ledger
- New market-summary count consistency audit
- Source readiness reporting, tests and actual historical evidence pilot workflow

H01 forecast score: NOT OBSERVED in the above run.
H01 actual net-equity improvement: NOT OBSERVED.
Causal psychological imitation: NOT OBSERVED.
User live-money performance: NOT OBSERVED.

## Decision

Maintain B0 as a frozen comparator. Do NOT promote any new behavioral factor from the above 21-day sample. Phase A only proceeds to an H01-A predictive run when enough time-correct cohort-return observations and verified market summaries exist.

## Live pilot run link

https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38356072553

This is an independent Jan-Mar 2025 historical evidence collection. Its completion must be checked and reported independently. Do not mark the data audit passed unless its workflow actually finishes and resulting artifact is inspected.

## Next highest-leverage action

Secure ~2 years of reproducible, day-complete XGB historical activity partitions and auditable executable-cohort daily equity with honest available_at timestamps. Run H01-A only then; preserve later untouched observations for subsequent testing.
