# H01 Interim Report — 2026-10-13 (2020+ collection in progress)

**STATUS: LONG-HORIZON DATA COLLECTION IN PROGRESS; 2020+ NET-EQUITY BACKTEST BLOCKED.**

Requested source start: 2020-01-01 (non-trading day); first market session verified: 2020-01-02.
Collection requested through last completed market date 2026-10-12, 14 semiannual segments.
Long-horizon study development cutoff: 2026-06-30.
2026-07-01..2026-09-28 original B0 blind holdout not used for new H01 tuning.

## Source pilot audit

2020-01-02..2020-01-10: 7 trade sessions retrieved via Xuangubao. 6/7 source pool counts match market closing summary; 2020-01-07 limit-up pool 98 names vs vendor indicator 99 (one-name discrepancy). This is an explicit data-definition/data-integrity discrepancy. No proof of complete 2020 population or eligible net-equity backtest. [Run](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38358060216)

2025-01-02..2025-03-31: 57 trade sessions; 56 closing-limit-up continuation ratios computed; 57/57 vendor same-provider count check passed; mean repeat ratio 25.0497%. Cross-check is not independent validation. [Run](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38357161904)

## H01-A: real historical predictive diagnostics, not strategy P&L

Target: next close limit-up repeat fraction.
Baseline: prior repeat fraction + prior limit-up count.
H01: add prior 3 trading sessions' vendor prior-limitup basket performance proxy.

34 chronological evaluation days (2025Q1):
- baseline MAE: 0.05946676
- H01 MAE: 0.05756489
- paired improvement: 0.001901868 (0.1902 percentage points)
- relative MAE improvement: 3.1982%
- H01 lower error: 21/34 days
- 5-trading-day circular block bootstrap, 10000 draws, 95% paired-improvement CI: [-0.00139238, +0.00613155] = [-0.1392, +0.6132] percentage points.

The confidence interval includes zero. **No statistically robust incremental effect established; no evidence of actual investor imitation or net-profitability.** [Statistics run](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38359189455)

## Previous B0 execution-engine short pilot (NOT H01 trading returns)

2024-12-27..2025-01-27, 21 trade sessions, 1228 candidate symbol-days data ready, initial modeled equity RMB 1,000,000:

| Fill mode | Modeled total return | Max DD | Closed trades | Win rate |
|---|---:|---:|---:|---:|
| optimistic | +23.5186% | -10.0463% | 5 | 60% |
| realistic | +24.4975% | -10.0473% | 4 | 75% |
| conservative | +21.2933% | -12.9607% | 4 | 75% |

Only 4 realistic/conservative completed trades; minute-bar execution assumptions remain imperfect. No long-horizon strategy performance inference allowed. [B0 archived run](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/36656336352)

## Expanded historical collection

[14-segment workflow](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38358815302) started. Once all partitions pass calendar coverage, source manifest, count mismatches and point-in-time availability audits, assess H01-A chronological prediction; separately implement realistic execution H01-B before discussing equity performance.

As of this report: **2020+ completed backtest P&L: unavailable, BLOCKED.**
