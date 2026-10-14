# H02 Final Research Goal Progress

Updated: 2026-10-14 (Asia/Shanghai)

## Scope and protected invariants

- Work continues from `research/behavioral-edge-20261013` at `b338f7e3c87597fa079a377e4b336f60b6117712` in the isolated H02 worktree.
- PR #1 remains Draft/Open. Do not modify `main`, merge PR #1, force-push, or change `config/b0.yaml` or frozen strategy/cost parameters.
- No 2026-07-01 through 2026-09-28 real holdout data was read, downloaded, evaluated, or unlocked.
- Five approved SHA-pinned Tier-D development archives only; row-level feature matrix stays in ignored local storage.

## Completed empirical work

- Rebuilt the feature report with full phase calendars in the 5-session block bootstrap, retaining zero-candidate/label-purged sessions.
- Compared train-prevalence, market-only L2 logistic, stock-only L2 logistic, and joint L2 logistic models on Y1/Y2/Y3. Added AP, equal-width ECE, calibration bins, descriptive calibration intercept/slope, candidate-weighted Brier bootstrap and day+symbol sensitivity intervals.
- Evaluated train-origin 5-session blocked rolling OOF predictions with a two-session purge to set thresholds. Froze seven A–G reference/ranking/abstention rules before evaluating exposed 2025H2 and 2026H1. Each capped rule keeps at most three research candidates per session and reports one final candidate per session, coverage, empty sessions, Y1 opportunity loss, Y2/Y3, paired 5-session bootstrap differences against full pool, tail metrics and fixed strata.
- Expanded synthetic execution evidence for zero/missing bars, invalid minute data, insufficient funds, maximum affordable lot sizing, sell-before-buy sequencing, consecutive locked sessions, suspension/resumption, T+1 and daily attempt counts. Bad minute bars now fail closed; insufficient cash is a recorded non-fill.

## Current data evidence

- 36,775 candidate symbol-days from 2024-09-30 through 2026-06-30: train 17,729 rows/179 sessions; validation 9,015/126; forward development 10,031/116.
- Event manifests verified 1,207/1,207; auxiliary manifests 1,803/1,803. Archive hashes and normalized matrix hash are in `features.json`.
- Y1/Y2/Y3 are vendor event-pool membership labels, not certified official price-limit or return labels. Publication-time/PIT availability at 09:35 is unverified.
- No independent OHLC, official per-stock limits, certified PIT ST/halt state, minute bars, order book, real fills, or investor feedback/account flow. Real after-cost validation remains blocked.

## Preliminary interpretation

- Fixed joint logistic forecasts lower candidate-weighted Brier than the train-prevalence baseline in exposed validation and forward development windows for all three vendor event labels. This is narrow predictive evidence only.
- None of A–G passes the predeclared paired decision gate requiring both Y2 and Y3 risk differences vs the full pool to have 95% 5-session block intervals wholly below zero. Higher continuation concentration is accompanied by higher downside-event concentration and/or substantial missed Y1 events.
- No economic edge is established. Behavioral classification is exactly `BEHAVIORAL_REINFORCEMENT_NOT_IDENTIFIED`.
- Synthetic accounts validate code paths, not historical execution probability or market performance.

## Remaining completion work

1. Rerun the full suite after the final source edits and record exact collected/passed count.
2. Generate and review `FINAL_RESEARCH_AND_STRATEGY_VERDICT.md`, reproduction instructions and all machine-readable artifacts.
3. Commit/push the research analysis stage to the permitted branch and verify CI for that SHA.
4. Commit/push the execution hardening stage and verify CI for that SHA.
5. Recheck PR #1 head/status and protected invariants; report any CI/auth/data-source barrier without making unsupported claims.
