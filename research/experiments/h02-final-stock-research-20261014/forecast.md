# H02 forecast and candidate-risk ranking research

**Tier D exploratory research. No actual returns, costs, fill evidence, or PIT certification.**

Matrix SHA256: `f1a8a9e34feb9bffc78bdb9cfe35dae2c0fe1418f9fe4b13822be205845b5dd9`; rows: 36,775.

## Forecast metrics

| Target | Evaluation phase | Baseline Brier | Logistic Brier | Brier gain (positive better) | 95% day-block CI |
|---|---|---:|---:|---:|---|
| continuation_D | validation_2025H2 | 0.18796 | 0.17742 | 0.01055 | [0.00748, 0.01294] |
| continuation_D | forward_2026H1 | 0.17124 | 0.16013 | 0.01111 | [0.00817, 0.01345] |
| down_next_D | validation_2025H2 | 0.02768 | 0.02613 | 0.00155 | [0.00085, 0.00267] |
| down_next_D | forward_2026H1 | 0.02908 | 0.02796 | 0.00111 | [0.00055, 0.00218] |
| down_three_D_to_D2 | validation_2025H2 | 0.10054 | 0.08838 | 0.01216 | [0.00707, 0.01671] |
| down_three_D_to_D2 | forward_2026H1 | 0.09817 | 0.08993 | 0.00824 | [0.00320, 0.01169] |

## Candidate ranking (forward development period)

| Policy | Selected | Continuation rate | Next-day down rate | Three-day down rate |
|---|---:|---:|---:|---:|
| unfiltered_all_candidates | 10031 | 20.98% | 2.99% | 10.74% |
| streak_2plus_top3 | 348 | 37.36% | 10.34% | 33.92% |
| risk_adjusted_top3 | 348 | 42.53% | 7.47% | 26.90% |
| risk_adjusted_top1 | 116 | 43.97% | 7.76% | 24.56% |

The fixed logistic forecast lowers Brier score versus a train-prevalence baseline for all three vendor-event labels in both validation and forward development windows. This is evidence for predicting vendor event membership only.

The risk-adjusted top-3/day rule raises continuation concentration, but its forward three-day vendor down-event rate (26.90%) is higher than the full pool (10.74%). This ranking did not reduce observed downside incidence. The score is `P(continuation) - 0.5*P(next-day down) - 0.5*P(three-day down)`; the weights are a transparent heuristic, not fitted utility. No actionable or executable edge is established.

Model parameters and feature list are fixed in source. Validation is descriptive and is not used for tuning; final 2026H1 results are development-only and exposed.
