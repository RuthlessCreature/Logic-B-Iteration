# Logic-B Goal checkpoint — 2025 TRAIN / 2026H1 VALIDATION

**Updated:** 2026-10-15 (Asia/Shanghai)
**Active rule:** `docs/LUNA_GOAL_2025_TRAIN_2026_VALIDATE.md`; 2025 only for training and selection, 2026H1 is not read until a training freeze exists. Protected 2026-07-01..2026-09-28 data remains untouched.
**Working base before this checkpoint's commit:** `c73b0c15cafbfa4074d496e07321bfb0fa401e5a` on `research/behavioral-edge-20261013`; that HEAD's core Actions run [38716185269](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38716185269) succeeded. PR #1 is open, Draft, base `main`; no main/PR mutation.

## 2025 source coverage and measured storage

- BaoStock calendar: **243/243** 2025 trading sessions; Xuangubao event partitions: **243/243**. Event partition failures: 0. Full-year input SHA256: `475f5a64d0c1971104483e2f35a4a48af93acc5614bf9deb4efd1d395500ac7f`.
- The price universe is a **candidate-path proxy**, not the whole market. Across V0/V1/V2 there are 117 daily symbols, 28,315 month-partitioned daily symbol-days, and 322 unique 5m files/15,264 bars. Xuangubao event pools contain 31,779 event rows. V0 requests 236/236 non-suspended target 5m partitions; V1 192/192; V2 187/187. These are path-complete only; all target missing counts are zero. V0/V1/V2 suspensions: 6/3/4. BaoStock query retries/errors: 0/0 on the instrumented reruns.
- Current local physical cache: **2,130 files / 19,077,530 bytes / 18.19375 MiB**, including normalized Parquet and 100 older unpartitioned annual daily files (4,970,363 bytes) retained on disk. Month-partitioned JSON: 12,712,775 bytes; normalized month Parquet: 1,393,997 bytes (10.96% of JSON size). The 100 annual files overlap monthly rows and are counted in disk usage but not the monthly coverage totals. Per-type/month file count, rows, bytes and manifest SHA256 are in `research/goal_2025_2026/coverage_by_month.csv` and `storage_inventory.json`.
- R2/D1 are **NOT_CONNECTED**; `r2_actual_bytes=null`. The initial full-range cache download happened before byte counters existed; exact counters for that original run are unavailable. Instrumented incremental reruns report exact reused/new bytes, queries, retries and failures per version. R2 bytes are never inferred from local bytes.
- The legacy Xuangubao cache and current monthly caches are private/local only. Raw supplier records and detailed symbol-level ledgers stay ignored under `data/` and `runs/`; only aggregates/curves/hashes are staged for GitHub.

## 2025 training iterations (exploratory bar-close simulation only)

All three runs use separate CNY10,000 accounts, the active fee model, 243 sessions, T+1, one position, 100-share buys, price-limit rejects and 09:45 completed-bar-close fills. Price bands are inferred, not official; this is not broker execution or trustworthy after-cost market performance.

| Version | Change | Return | MDD | Round trips | Fees CNY | Cash days | No-fill up/down | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|
| V0_SIMPLE_STREAK | Frozen original event-streak baseline | -76.9218% | -78.0509% | 65 | 767.18 | 163 | 85 / 15 | Keep as reference |
| V1_MARKET_STATE_GATE | Gate entries when lagged vendor temperature < 40 | -80.6120% | -81.2785% | 52 | 598.20 | 178 | 69 / 13 | Reject; worse return and MDD |
| V2_BREAK_FEEDBACK_VETO | V1 plus candidate break-count <= 1 | -60.7934% | -62.3941% | 48 | 601.34 | 187 | 81 / 8 | Reject as strategy; exploratory loss smaller, but still severe and unverified |

Precommitted exploratory score is `net_return_pct + 0.5 * signed_MDD_pct`. V2 scores best among the three, but all scores are negative and the full-market price universe, official per-security limits, 09:35 PIT, corporate actions and real-fill gates are unmet. Therefore the training freeze is **`NO_CANDIDATE`**, SHA256 `365de66462abb5802cd3bfced28a0ae290334022cb7ad2c98331dab219373e45`, recorded in `research/goal_2025_2026/frozen_selection.json`. V0 remains a reference only. The state series is a lagged vendor-pool proxy; it does not establish investor psychology. Sector/core labels are `UNKNOWN` where the source lacks legal historical labels.

The new one-pass demand planner reproduces the prior V0 2025 private snapshot byte-for-byte at canonical input SHA `475f5a64...500ac7f`, with the same account metrics, while removing repeated full-prefix replays. The old run, the streaming rerun and private ledgers are local/ignored.

## Artifacts generated

- `research/goal_2025_2026/dashboard.html`
- `iteration_history.csv/json`, `training_equity.csv/svg`
- `market_state_2025.csv/svg`, `market_state_activity.csv`, `market_state_summary.csv`
- `coverage_by_month.csv`, `storage_inventory.json`, `storage_growth.csv/svg`
- `frozen_selection.json`, `run_manifest.json`, `goal_report.json`
- Synthetic harness separately writes an explicitly synthetic dashboard under ignored `runs/goal_2025_2026_demo/`; it is not market evidence.

## Engineering and verification

- Collector supports monthly calendar/daily caches, Xuangubao error isolation, bounded BaoStock retry/re-login for `10002007`, legacy-cache migration and no repeat request for cached partitions. `LocalStore` and injectable/mockable `R2Store` are implemented; no client, secret, upload, paid API or live order was used.
- Full local suite: **89 passed**. `logic_b` synthetic replay smoke returned `PARTIAL` with +0.7036% on toy data; explicitly not a market result. Synthetic Goal dashboard generated successfully and is marked `NOT_FULLY_VALIDATED`. The repository has no `validate-config` CLI subcommand; frozen base-account invariants are covered by active config/replay tests.
- No Goal-stage commit or push has been made yet. After staging this training/freeze package, verify the new-head Actions run before any 2026H1 cache request.

## Next actions

1. Review aggregate outputs for raw supplier rows or local-path leakage, run full tests/smokes, commit and fast-forward push this training freeze to the research branch, then verify exact-HEAD CI and PR remains Draft.
2. Only after that freeze commit and CI, collect 2026-01-01..2026-06-30 Xuangubao/BaoStock data in month partitions, measure exact incremental bytes and missing days, and evaluate V0 reference only because selection is `NO_CANDIDATE`.
3. Label validation `INSUFFICIENT` for economic conclusions if official price limits, PIT availability, company actions or executable-price evidence remain absent. Never inspect dates after 2026-06-30.
