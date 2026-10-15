# H01-A anomaly-quarantined sensitivity, 2026-10-13

Source run: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38358815302
Reproduction: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38382289079
Branch: research/behavioral-edge-20261013
Source: Xuangubao historical vendor event lists and end-of-day indicators.

## Decision: DO NOT PROMOTE H01

1,639 exchange calendar dates collected, 2020-01-02..2026-10-12.
H01 development-only test ends on 2026-06-30 and **does not use original July-September 2026 blind holdout**.

Source event-list vs vendor close-count disagreements: 38/1,571 = 2.419%. All disagreements are within 2020-01-07..2020-08-18; 34 have fewer rows in the list than vendor count, four have more. This exceeds the previously frozen 2% quality limit. The count comparison uses two interfaces of the same provider; a match is NOT independent verification of population coverage.

Quarantine: 38 anomalous sessions plus each one's following 3 trading sessions => 95 *unique* excluded sessions (6.05%). These are quarantined for sensitivity, not declared corrupt. The quarantine rule is fixed before rescoring.

### Paired chronological forecast, same fixed model

| Measure | Original (uncensored) | Quarantined |
|---|---:|---:|
| Trade-day test count | 1,448 | 1,353 |
| Baseline MAE | 6.98498 percentage points | 6.85435 percentage points |
| H01-enhanced MAE | 6.98312 percentage points | 6.84623 percentage points |
| Improvement | +0.00187 pp | +0.00812 pp |
| H01 lower-error fraction | 50.83% | 51.07% |

Bootstrap paired-improvement 95% interval with seed 20261013 and circular blocks:
- 5-session blocks: [-0.01003, +0.02578] percentage points
- 20-session blocks: [-0.01182, +0.02753] percentage points

Both contain zero. Thus even after quarantine **incremental predictive ability is unproven**.

Annual MAE improvement, quarantined (percentage points):
- 2020: +0.0180, 25 test days (short, insufficient)
- 2021: +0.0015, 243 test days
- 2022: +0.0408, 242 test days
- 2023: -0.0591, 242 test days
- 2024: +0.0074, 242 test days
- 2025: +0.0209, 243 test days
- 2026 Jan-Jun: +0.0669, 116 test days

Year-to-year instability (especially 2023) and extremely small overall improvement refute **promoting this specific H01 signal** on these data. These metrics predict the next *close-to-close repeated limit-up fraction*, NOT stock returns, investor P&L, or a tradable strategy. A point-in-time proxy for prior winning experiences cannot by itself establish investor imitation causality.

## Non-negotiable restrictions

- Old source mismatch cap remains 2%; run status stays BLOCKED_PROMOTION_SOURCE_COUNT_MISMATCH.
- Do not change model lookback, target, split, or quality cap to make H01 pass.
- Do not report annualized gains, Sharpe, drawdown, net-alpha or actual investor behavior from H01-A.
- No retrospective H01-B trade signals have been constructed. Zero H01-B 2020+ net-equity evidence exists.
- H02, if attempted, is a separately registered psychological hypothesis. B0 and its original chronological holdout are not altered.

Artifacts: h01_quarantined_predictions.csv, h01_quarantined_by_year.csv, h01_quarantined_dates.csv, original_vs_quarantined.json, h01_robustness_report.json.
