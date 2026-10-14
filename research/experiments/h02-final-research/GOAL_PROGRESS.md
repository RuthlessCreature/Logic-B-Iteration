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

## Final interpretation

- Fixed joint logistic forecasts lower candidate-weighted Brier than the train-prevalence baseline in exposed validation and forward development windows for all three vendor event labels. This is narrow predictive evidence only.
- None of A–G passes the predeclared paired decision gate requiring both Y2 and Y3 risk differences vs the full pool to have 95% 5-session block intervals wholly below zero. Higher continuation concentration is accompanied by higher downside-event concentration and/or substantial missed Y1 events.
- No economic edge is established. Behavioral classification is exactly `BEHAVIORAL_REINFORCEMENT_NOT_IDENTIFIED`.
- Synthetic accounts validate code paths, not historical execution probability or market performance.

## Remaining completion work

All authorized local stages are complete. Real-data execution validation remains blocked by the research source/PIT stop conditions above; the required next action is acquisition and independent approval of licensed PIT sources.

## Engineering delivery

- Analysis commit on branch: `099c99944694ad89f1b95d888ad462e96c11a1d8`; Actions `test` run [38549295074](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38549295074) and `h02-forward-market-pilot` run [38549294907](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38549294907), both success.
- Execution commit on branch: `16a402bf24b49d8787be546f9e29afc70d4b7597`; Actions `test` run [38550275360](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38550275360) and `h02-forward-market-pilot` run [38550275359](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38550275359), both success.
- Local full suite after final reference-candidate correction: `python -m pytest --override-ini='addopts=' -q` → **287 passed**, three warnings (two existing pandas B0 warnings and one invalid-timestamp fixture parsing warning). `logic-b smoke` and `logic-b validate-config config/b0.yaml` both returned `status=ok`.
- The normal HTTPS Git push for the second stage was blocked by a transient `curl 28` connection reset/timeout. The same seven-file tree was committed through the connected GitHub Git Database API with fast-forward expected-head `099c999...`; the resulting branch commit `16a402bf...` has the same tree SHA as the local execution snapshot `c88c9c9...`. No force update was used.
- PR #1 was rechecked after the second stage: `open`, `draft=true`, `merged=false`, base `main`, head `research/behavioral-edge-20261013` at `16a402bf...`.
- Main was not modified; B0 frozen config/costs were not modified; holdout was not accessed.
