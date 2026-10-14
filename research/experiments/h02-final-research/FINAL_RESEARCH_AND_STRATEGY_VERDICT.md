# LOGIC-B FINAL RESEARCH & STRATEGY VERDICT

**Run date:** 2026-10-14 (Asia/Shanghai)  
**Branch target:** `research/behavioral-edge-20261013`  
**Starting HEAD:** `b338f7e3c87597fa079a377e4b336f60b6117712`  
**Classification:** exploratory vendor-event prediction and synthetic execution mechanics only.  
**Protected holdout:** not accessed.

## Final verdict

| Question | Verdict | Evidence and limit |
|---|---|---|
| `PREDICTIVE_EDGE` | **DEMONSTRATED, narrowly** | Fixed L2 logistic models improve candidate-weighted Brier against the train-prevalence baseline on exposed validation and forward windows for Y1/Y2/Y3 vendor-event labels. Day-block intervals for the joint model are above zero in all six target/phase comparisons. These labels are vendor-pool outcomes; PIT availability and official event semantics are uncertified. |
| `DECISION_EDGE` | **NOT DEMONSTRATED** | No frozen A–G policy passes the predeclared paired risk gate requiring both Y2 and Y3 differences vs the full candidate pool to have 95% 5-session block intervals entirely below zero. Concentrating Y1 continuation also concentrates downside labels, while abstention cuts many Y1 events. |
| `ECONOMIC_EDGE` | **INSUFFICIENT EVIDENCE / BLOCKED** | No independent OHLC, official per-security price limits, certified PIT ST/halt status, historical candidate-minute bars, order book, or real fills. Fees and a synthetic account replay cannot substitute for observed executable fills or after-cost market returns. |
| `BEHAVIORAL_REINFORCEMENT` | **`BEHAVIORAL_REINFORCEMENT_NOT_IDENTIFIED`** | No direct investor-account, order-flow, or feedback-loop observations. Vendor event persistence alone does not identify investor psychology. |

## Research design and data evidence

Five approved, full-archive SHA-pinned development ZIPs were used. The normalized matrix is **36,775 candidate symbol-days**, covering 2024-09-30 through 2026-06-30:

| Split | Candidate symbol-days | Outcome sessions | Status |
|---|---:|---:|---|
| Train through 2025-06-30 | 17,729 | 179 | Model fitting, preprocessing, OOF cutoffs |
| Validation 2025H2 | 9,015 | 126 | Exposed validation |
| Forward 2026H1 | 10,031 | 116 | Exposed development; not a holdout |

Event-source manifests verified **1,207/1,207** and auxiliary manifests **1,803/1,803**. The normalized feature matrix SHA256 is `f1a8a9e34feb9bffc78bdb9cfe35dae2c0fe1418f9fe4b13822be205845b5dd9`. The five source archive hashes are in [features.json](features.json).

The targets are vendor limit-up/down event-pool membership. They are not independently verified official limit-price events, returns, fills, or P&L. Features are structurally dated no later than D-1, but historical source publication time and availability by the next session’s 09:35 decision are **PIT_UNVERIFIED**. Y3 labels are phase-purged; the terminal sessions without a complete forward window are excluded from Y3 denominators and retained as zero-observation sessions in block resampling.

The local environment had no `TUSHARE_TOKEN`; only the boolean presence check was recorded. No token was read, printed, or used. Official price-limit acquisition was not attempted. The independent OHLC, official limit prices, PIT ST/halt status, candidate minutes, order book, and feedback data required to validate real execution are absent from the approved archives.

## Forecast model comparison

Models are fixed L2 logistic specifications: train-only median imputation and standardization; penalty 1.0; 400 fixed gradient steps. No evaluation-period tuning was used. Model families are market-state-only, stock-structure-only, and joint; nonlinear models were not added because no preregistered capacity/complexity need was established. Rare-event average precision (AP), Brier, log loss, calibration bins, equal-width ECE, and descriptive calibration intercept/slope are in [forecast.json](forecast.json). Calibration intercept/slope are descriptive point estimates on each evaluation set, not independently validated calibration claims.

| Target | Phase | Baseline Brier | Joint Brier | Candidate-weighted Brier gain | 95% day-block CI | Joint AP |
|---|---|---:|---:|---:|---:|---:|
| Y1 continuation | 2025H2 | 0.18796 | 0.17625 | 0.01171 | [0.00839, 0.01462] | 0.3874 |
| Y1 continuation | 2026H1 | 0.17124 | 0.15954 | 0.01170 | [0.00911, 0.01397] | 0.3392 |
| Y2 next-day down event | 2025H2 | 0.02768 | 0.02618 | 0.00151 | [0.00086, 0.00229] | 0.1262 |
| Y2 next-day down event | 2026H1 | 0.02908 | 0.02795 | 0.00113 | [0.00043, 0.00199] | 0.1100 |
| Y3 three-day down event | 2025H2 | 0.10054 | 0.08859 | 0.01195 | [0.00784, 0.01621] | 0.3142 |
| Y3 three-day down event | 2026H1 | 0.09817 | 0.09034 | 0.00783 | [0.00424, 0.01170] | 0.2614 |

All gains are pooled by candidate row, and each bootstrap replicate recomputes a candidate-weighted ratio using contiguous five-session blocks on the full phase calendar. A day-plus-symbol resampling interval is reported as a sensitivity analysis, not a standard two-way cluster confidence interval. Across model families, stock structure is more useful than market-only inputs in these comparisons; joint models are similar to stock-only, with no basis to claim a unique market-behavior mechanism.

## Frozen A–G policy results

Thresholds came only from **9,113** expanding-origin, five-session blocked OOF training predictions (2024-12-30 through 2025-06-26), with a two-session purge before each scored block. Frozen thresholds: Y3 risk probability q75 = **0.20430**; cross-model Y3 risk-score range q80 = **0.18018**; market breadth q25 = **66**; lagged continuation change q25 = **−0.04317**. All rules and exact definitions are recorded in [strategy-comparison.json](strategy-comparison.json).

Each capped rule selects at most three names per session and specifies one separate highest-ranked final candidate. A is the uncapped full-pool reference. The rate difference confidence intervals use paired resampling of the same five-session date blocks.

| Phase | Rule | Selected / pool | Y1 | Y2 | Y3 | ΔY2 vs pool | ΔY3 vs pool | Missed Y1 | Decision gate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2025H2 | Full pool (A) | 9,015 / 9,015 | 24.8% | 2.8% | 11.1% | — | — | 0 | Reference |
| 2025H2 | B continuation top-3 | 378 / 9,015 | 52.9% | 10.3% | 34.9% | +7.5 pp | +23.8 pp | 2,039 | Fail |
| 2025H2 | C risk-score top-3 | 378 / 9,015 | 47.9% | 6.3% | 25.7% | +3.6 pp | +14.6 pp | 2,060 | Fail |
| 2025H2 | D C plus OOF Y3 cap | 372 / 9,015 | 37.9% | 2.4% | 12.3% | −0.4 pp | +1.2 pp | 2,100 | Fail |
| 2025H2 | E B with streak veto | 378 / 9,015 | 37.3% | 5.8% | 22.2% | +3.0 pp | +11.1 pp | 2,100 | Fail |
| 2025H2 | F B with weak-market abstention | 351 / 9,015 | 52.7% | 10.3% | 34.8% | +7.5 pp | +23.7 pp | 2,054 | Fail |
| 2025H2 | G C with disagreement abstention | 372 / 9,015 | 43.3% | 5.4% | 19.4% | +2.3 pp | +8.3 pp | 2,081 | Fail |
| 2026H1 | Full pool (A) | 10,031 / 10,031 | 21.0% | 3.0% | 10.7% | — | — | 0 | Reference |
| 2026H1 | B continuation top-3 | 348 / 10,031 | 50.0% | 10.9% | 36.2% | +8.0 pp | +25.5 pp | 1,930 | Fail |
| 2026H1 | C risk-score top-3 | 348 / 10,031 | 42.0% | 5.2% | 22.5% | +2.2 pp | +11.8 pp | 1,958 | Fail |
| 2026H1 | D C plus OOF Y3 cap | 342 / 10,031 | 31.9% | 4.1% | 15.1% | +1.1 pp | +4.4 pp | 1,996 | Fail |
| 2026H1 | E B with streak veto | 348 / 10,031 | 36.8% | 5.2% | 19.0% | +2.2 pp | +8.3 pp | 1,976 | Fail |
| 2026H1 | F B with weak-market abstention | 318 / 10,031 | 51.6% | 11.9% | 37.4% | +8.9 pp | +26.2 pp | 1,941 | Fail |
| 2026H1 | G C with disagreement abstention | 342 / 10,031 | 33.0% | 4.4% | 16.8% | +1.1 pp | +6.1 pp | 1,992 | Fail |

The exact point differences and paired confidence intervals show the result is not just a positive-versus-negative point-estimate rule: no policy had both downside-label intervals wholly below zero. D reduced Y2 in 2025H2, but its interval crosses zero and Y3 did not improve; on 2026H1 D’s Y2 and Y3 rates both remained above the full-pool rates. Every selected top-3 policy retained only roughly 3.5–4.2% of candidate rows and missed 91–95% of Y1 events.

The feature-level tail tables retain all preregistered groups and interactions, including adverse strata. In training, the Y1/Y3 event rates for vendor streaks 1 / 2 / 3+ were **21.86% / 37.31% / 53.55%** and **9.74% / 21.40% / 40.90%**, respectively. Continuation and downside event concentration move upward together. These subgroup rates are exploratory; intervals do not adjust for repeated symbols or the number of predeclared comparisons. Policy reports include per-session q90/q95, worst session, worst rolling five-session mean, top-ten symbol event concentration, and outcomes by fixed market/streak strata.

## Synthetic execution and test evidence

The [synthetic execution ledger](synthetic-execution-ledger.json) uses only synthetic 2099 dates and symbols. It covers sealed priority candidate/no fallback, 09:36 fill after a 09:35 checkpoint, T+1, multiple consecutive locked-down sessions, suspension/resumption, sell-before-buy and no same-day repurchase after a post-checkpoint exit, insufficient cash, exact one-lot and full-account maximum-lot boundaries after modelled costs, and daily buy/sell attempt limits. Missing bars, zero volume, checkpoint-only bars, invalid/zero/non-finite prices and limits, negative volume, inconsistent OHLC, invalid/duplicate/out-of-order timestamps fail closed or produce a recorded no-fill.

The synthetic account’s modeled costs are sourced from the runner’s configured `TradingCosts` object and reconciled by commission, transfer fee, and sell stamp-duty lines. These are test assumptions, not certified account fees. No synthetic ledger row is real execution evidence. Frozen `config/b0.yaml` was not changed.

The full local command `python -m pytest --override-ini='addopts=' -q` completed successfully: **286 passed** with three warnings (two existing pandas warnings from B0 theme handling and one warning generated by the invalid-timestamp test fixture). `logic-b smoke` and `logic-b validate-config config/b0.yaml` both returned `status=ok`. The suite includes regressions for full-calendar candidate-weighted bootstrap, nested forecast report generation, policy caps/paired comparisons, and synthetic failure cases.

## Engineering commits and CI

| Stage | Branch commit | GitHub Actions on exact commit |
|---|---|---|
| Forecast and policy analysis | `099c99944694ad89f1b95d888ad462e96c11a1d8` | [`test` 38549295074](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38549295074) — success; [`h02-forward-market-pilot` 38549294907](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38549294907) — success |
| Execution hardening and synthetic account ledger | `16a402bf24b49d8787be546f9e29afc70d4b7597` | [`test` 38550275360](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38550275360) — success; [`h02-forward-market-pilot` 38550275359](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38550275359) — success |

The normal Git HTTPS push for stage two hit `curl 28` connection reset/timeouts. The commit was then created through the connected GitHub Git Database API using the already verified `099c999...` expected branch head and `force=false`. Its tree SHA exactly matches the local execution snapshot (`4a2ccd55832b27ece001b52cea0050470f9ebc44`). PR #1 was verified open and Draft, unmerged, base `main`, with its head at `16a402bf...`.

## Files and reproduction

- [Feature report and source hashes](features.json) / [feature tables](features.md)
- [Forecast model comparison](forecast.json) / [forecast explanation](forecast.md)
- [Frozen A–G and tail-risk analysis](strategy-comparison.json) / [policy tables](strategy-comparison.md)
- [Synthetic execution ledger](synthetic-execution-ledger.json) / [ledger explanation](synthetic-execution-ledger.md)
- [Reproduction instructions](REPRODUCTION.md)
- Local ignored matrix: `runs/h02-final-research/feature-matrix.csv`; it contains symbol identifiers and remains excluded from Git/publication.

## Outstanding blockers and sole next step

1. No licensed, point-in-time-certified independent price/limit/status/minute/order-flow sources are available in the approved input set; `TUSHARE_TOKEN` was absent. Therefore real executable, after-cost validation is **blocked** under the handoff’s source and PIT stops.
2. Psychology/behavioral reinforcement is unidentified without direct feedback or account/order-flow evidence.
3. 2025H2/2026H1 are exposed periods; protected holdout remains untouched.

**Next action:** obtain and independently approve a licensed point-in-time source bundle for official limits, ST/halt status and candidate intraday bars before attempting any real execution replay. Do not convert this report into investment or return claims.
