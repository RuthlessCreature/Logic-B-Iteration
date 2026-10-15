# H02 forecast and candidate-risk ranking research

**Tier D exploratory research. No actual returns, costs, fill evidence, or PIT certification.**

Matrix SHA256: `f1a8a9e34feb9bffc78bdb9cfe35dae2c0fe1418f9fe4b13822be205845b5dd9`; rows: 36,775.

## Forecast model comparison

| Target | Evaluation phase | Model | Brier | Log loss | AP | Brier gain vs prevalence | 95% candidate-weighted day-block CI | Two-way day/symbol CI |
|---|---|---|---:|---:|---:|---:|---|---|
| continuation_D | validation_2025H2 | prevalence_baseline | 0.18796 | 0.56375 | 0.2441 | n/a | — | — |
| continuation_D | validation_2025H2 | market_state_logistic | 0.18890 | 0.56633 | 0.2546 | -0.00094 | [-0.00265, 0.00006] | [-0.00302, 0.00024] |
| continuation_D | validation_2025H2 | stock_structure_logistic | 0.17585 | 0.53396 | 0.3891 | 0.01211 | [0.00963, 0.01445] | [0.00810, 0.01694] |
| continuation_D | validation_2025H2 | joint_logistic | 0.17625 | 0.53518 | 0.3874 | 0.01171 | [0.00839, 0.01462] | [0.00693, 0.01694] |
| continuation_D | forward_2026H1 | prevalence_baseline | 0.17124 | 0.52794 | 0.2399 | n/a | — | — |
| continuation_D | forward_2026H1 | market_state_logistic | 0.17059 | 0.52623 | 0.2128 | 0.00065 | [-0.00000, 0.00131] | [-0.00009, 0.00138] |
| continuation_D | forward_2026H1 | stock_structure_logistic | 0.16059 | 0.50031 | 0.3346 | 0.01065 | [0.00807, 0.01298] | [0.00716, 0.01413] |
| continuation_D | forward_2026H1 | joint_logistic | 0.15954 | 0.49707 | 0.3392 | 0.01170 | [0.00911, 0.01397] | [0.00779, 0.01538] |
| down_next_D | validation_2025H2 | prevalence_baseline | 0.02768 | 0.13051 | 0.0238 | n/a | — | — |
| down_next_D | validation_2025H2 | market_state_logistic | 0.02744 | 0.12689 | 0.0575 | 0.00024 | [0.00011, 0.00040] | [0.00008, 0.00043] |
| down_next_D | validation_2025H2 | stock_structure_logistic | 0.02646 | 0.11344 | 0.1055 | 0.00122 | [0.00067, 0.00188] | [0.00030, 0.00226] |
| down_next_D | validation_2025H2 | joint_logistic | 0.02618 | 0.11075 | 0.1262 | 0.00151 | [0.00086, 0.00229] | [0.00057, 0.00260] |
| down_next_D | forward_2026H1 | prevalence_baseline | 0.02908 | 0.13539 | 0.0315 | n/a | — | — |
| down_next_D | forward_2026H1 | market_state_logistic | 0.02889 | 0.13264 | 0.0543 | 0.00019 | [0.00005, 0.00039] | [0.00001, 0.00041] |
| down_next_D | forward_2026H1 | stock_structure_logistic | 0.02824 | 0.12414 | 0.0912 | 0.00084 | [0.00028, 0.00147] | [0.00009, 0.00163] |
| down_next_D | forward_2026H1 | joint_logistic | 0.02795 | 0.12163 | 0.1100 | 0.00113 | [0.00043, 0.00199] | [0.00025, 0.00218] |
| down_three_D_to_D2 | validation_2025H2 | prevalence_baseline | 0.10054 | 0.35656 | 0.1008 | n/a | — | — |
| down_three_D_to_D2 | validation_2025H2 | market_state_logistic | 0.09958 | 0.35111 | 0.1452 | 0.00096 | [-0.00045, 0.00246] | [-0.00063, 0.00269] |
| down_three_D_to_D2 | validation_2025H2 | stock_structure_logistic | 0.08876 | 0.30835 | 0.3030 | 0.01178 | [0.00849, 0.01530] | [0.00624, 0.01710] |
| down_three_D_to_D2 | validation_2025H2 | joint_logistic | 0.08859 | 0.30502 | 0.3142 | 0.01195 | [0.00784, 0.01621] | [0.00564, 0.01789] |
| down_three_D_to_D2 | forward_2026H1 | prevalence_baseline | 0.09817 | 0.35075 | 0.1194 | n/a | — | — |
| down_three_D_to_D2 | forward_2026H1 | market_state_logistic | 0.09786 | 0.34698 | 0.1256 | 0.00031 | [-0.00148, 0.00195] | [-0.00171, 0.00220] |
| down_three_D_to_D2 | forward_2026H1 | stock_structure_logistic | 0.08977 | 0.31608 | 0.2672 | 0.00840 | [0.00474, 0.01291] | [0.00358, 0.01354] |
| down_three_D_to_D2 | forward_2026H1 | joint_logistic | 0.09034 | 0.31391 | 0.2614 | 0.00783 | [0.00424, 0.01170] | [0.00303, 0.01283] |

## Candidate ranking (forward development period)

| Policy | Selected | Continuation rate | Next-day down rate | Three-day down rate |
|---|---:|---:|---:|---:|
| unfiltered_all_candidates | 10031 | 20.98% | 2.99% | 10.74% |
| streak_2plus_top3 | 348 | 37.36% | 10.34% | 33.92% |
| risk_adjusted_top3 | 348 | 41.95% | 4.89% | 22.51% |
| risk_adjusted_top1 | 116 | 49.14% | 5.17% | 22.81% |

Bootstrap intervals use a candidate-weighted Brier gain ratio in every five-session moving-block replicate. The sensitivity interval resamples day blocks and symbol clusters. Average precision supplements Brier/Log Loss for rare down-event labels; calibration bins and ECE are present in JSON.

Validation and 2026H1 are exposed research windows, not independent holdouts. Training metrics are resubstitution diagnostics only. The 2026H1 data are not used to set features, model parameters, or risk gates.

No high-capacity nonlinear model was added: the fixed model-family comparisons are the market-only, stock-only, and joint regularized logistic specifications. This avoids adding complexity without a preregistered reason.

The prior ranking remains exploratory and is superseded by the frozen risk-policy comparison report. No actionable or executable edge is established.
