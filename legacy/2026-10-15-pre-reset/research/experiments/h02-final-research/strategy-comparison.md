# H02 frozen A–G strategy and tail-risk comparison

**Research-only vendor event labels. PIT_UNVERIFIED; no realized returns, fill quality, costs, or executable edge.**

Matrix SHA256 `f1a8a9e34feb9bffc78bdb9cfe35dae2c0fe1418f9fe4b13822be205845b5dd9`; rows 36,775; thresholds were fitted using training dates only.

Rules A–G and their exact train-only definitions/cut points are in the JSON. Validation 2025H2 and 2026H1 are exposed development windows. Every capped rule selects at most three research shortlist names per session; a separate highest-ranked name is counted as the one-name final candidate.

## Policy outcomes

| Phase | Rule | Selected | Empty sessions | Coverage | Y1 rate | Y2 rate | Y3 rate | ΔY2 vs pool | ΔY3 vs pool | Missed Y1 | Y1 loss | Worst 5-session Y3 | Decision gate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| validation_2025H2 | A_full_pool_reference | 9015 | 0 | 100.00% | 24.85% | 2.84% | 11.08% | 0.00% | 0.00% | 0 | 0.00% | 5.28% | FAIL |
| validation_2025H2 | B_continuation_top3 | 378 | 0 | 4.19% | 53.17% | 10.32% | 35.22% | 7.48% | 24.14% | 2039 | 91.03% | 0.00% | FAIL |
| validation_2025H2 | C_transparent_risk_score_top3 | 378 | 0 | 4.19% | 47.62% | 6.35% | 26.34% | 3.51% | 15.26% | 2060 | 91.96% | 6.67% | FAIL |
| validation_2025H2 | D_C_plus_train_oof_down3_cap | 372 | 2 | 4.13% | 37.63% | 2.42% | 11.83% | -0.42% | 0.75% | 2100 | 93.75% | 0.00% | FAIL |
| validation_2025H2 | E_B_veto_streak_3plus | 378 | 0 | 4.19% | 37.04% | 6.08% | 22.04% | 3.24% | 10.96% | 2100 | 93.75% | 0.00% | FAIL |
| validation_2025H2 | F_B_abstain_compounded_weak_market | 351 | 9 | 3.89% | 52.99% | 10.26% | 34.78% | 7.42% | 23.70% | 2054 | 91.70% | 0.00% | FAIL |
| validation_2025H2 | G_C_abstain_model_disagreement | 372 | 2 | 4.13% | 42.74% | 5.11% | 19.35% | 2.27% | 8.28% | 2081 | 92.90% | 0.00% | FAIL |
| forward_2026H1 | A_full_pool_reference | 10031 | 0 | 100.00% | 20.98% | 2.99% | 10.74% | 0.00% | 0.00% | 0 | 0.00% | 2.33% | FAIL |
| forward_2026H1 | B_continuation_top3 | 348 | 0 | 3.47% | 50.29% | 11.49% | 35.67% | 8.50% | 24.94% | 1930 | 91.69% | 0.00% | FAIL |
| forward_2026H1 | C_transparent_risk_score_top3 | 348 | 0 | 3.47% | 42.24% | 4.89% | 22.51% | 1.89% | 11.78% | 1958 | 93.02% | 0.00% | FAIL |
| forward_2026H1 | D_C_plus_train_oof_down3_cap | 342 | 2 | 3.41% | 31.87% | 4.09% | 14.62% | 1.10% | 3.88% | 1996 | 94.82% | 0.00% | FAIL |
| forward_2026H1 | E_B_veto_streak_3plus | 348 | 0 | 3.47% | 37.07% | 4.60% | 19.01% | 1.61% | 8.27% | 1976 | 93.87% | 0.00% | FAIL |
| forward_2026H1 | F_B_abstain_compounded_weak_market | 318 | 10 | 3.17% | 51.57% | 12.26% | 36.86% | 9.27% | 26.12% | 1941 | 92.21% | 6.67% | FAIL |
| forward_2026H1 | G_C_abstain_model_disagreement | 342 | 2 | 3.41% | 33.04% | 3.51% | 16.96% | 0.52% | 6.22% | 1992 | 94.63% | 0.00% | FAIL |

All rules preserve the same candidate-weighted 5-session moving-block estimand for event rates and include 95% intervals in JSON. Tail tables report session q90/q95, worst single session, worst rolling five-session rate, and top-ten symbol event concentration. Fixed regime and interaction tables retain adverse/empty groups; they are descriptive and not multiplicity-adjusted.

## Limits

Vendor event-pool membership is not independently verified official price-limit status. Features are D-1 but publication-time availability at 09:35 is uncertified. The source archive lacks independent OHLC, official limit prices, PIT ST/halt, minute bars and executable fills. Therefore these comparisons cannot demonstrate economic edge.

`BEHAVIORAL_REINFORCEMENT_NOT_IDENTIFIED`: no direct investor account, order-flow, or feedback-loop data are present.
