# H02 FAST-TRACK progress

Updated: 2026-10-14 (Asia/Shanghai)
Branch: `research/behavioral-edge-20261013`

## Checkpoints

| Checkpoint | Status | Evidence / numerator / denominator | Commit / CI |
|---|---|---|---|
| FAST-0 baseline and inventory | PARTIAL | Remote and local HEAD at start `843970a73aa097ccf95629ad379ec882ca4ec6f1`; PR #1 open Draft, base `main`; baseline Actions run 38513680605 succeeded. No local `data-xgb`, `data/raw`, `runs`, cache, or Parquet/CSV/SQLite/JSONL partitions found. `TUSHARE_TOKEN` not configured locally. | This checkpoint is recorded with the P1 fix commit below. |
| FAST-1 three-symbol historical diagnostic | PARTIAL | Existing 2020-01-03 sample has 3/3 rows, Xuangubao normalized minute query hashes repeated pairwise (normalized only; provider raw response not retained), minute structural audit 1/3, official limits 0/3, PIT verified 0/3, execution eligible 0/3. `000998.SZ` and `000716.SZ` each have five 11:31–11:35 rows; `000716.SZ` BaoStock daily vs XGB minute open/low differ by RMB 0.02. `600421.SH` has 148 bars and is EOD ST reference; low bar count is not classified as halt. | Prior evidence: [run 38384217991](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38384217991), [run 38384941333](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38384941333). See `P2A_COVERAGE_MATRIX_20261014.md` and JSON. |
| FAST-2 2020-01-03 all candidates | PARTIAL | Existing historical report says 94/94 candidate symbols returned minute sets; 89/94 met the old provisional >=180-bar threshold. The retained 605-byte workflow artifact is a summary and does not contain rows or individual partition hashes; the current checkout has no raw partitions. These figures are inherited reported results, not independently replayed counts. | [Run 38384217991](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38384217991); artifact SHA256 `bb00d97fa1ac409cf886f8e79f48905a9601ff5030968f4e55911b0d55b2f9fc`. |
| FAST-3 January daily coverage | BLOCKED / not independently replayed | Prior report's 985 candidate-days is explicitly unverified as a current denominator. No daily partitions or manifest present locally. A small historical BaoStock reference batch reports 264/264 rows for Jan 3, 6, 7 only; these are EOD references, not 09:35 PIT inputs. | Historical evidence: [run 38403595165](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403595165); Jan coverage output [run 38404221537](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38404221537). |
| FAST-4 synthetic ledger | PARTIAL / ongoing | Existing tests cover T+1 runner entry/exit, suspension carry, lock-limit execution rejections, and fee accounting. Gaps identified: multi-day combined limit-lock/halt ledger, no-fallback after blocked first candidate, UNKNOWN minute-label fail-closed, and explicit distinction between simulated fill and real-fill certification. | No new ledger commit yet. |
| FAST-5 development replay | BLOCKED | No local partitions were found for 2024-09-30..2026-06-30; no fully certified continuous sample or verified expected candidate denominator can be claimed. No replay or return calculation was run. | Requires licensed data partitions and PIT/official-limit evidence. |

## P1 metric correction

The matrix now preserves upstream PIT/fill statements as `PIT_claimed` / `fill_claimed`, forces independently verified PIT/fill/hash/official-limit counts to zero absent a verifier, and keeps the aggregate gate BLOCKED. It validates `sample_size_symbol_days` and `sample_symbols` against the actual rows. The actual retained three-row sample remains BLOCKED.

Local checks before commit: full pytest passed; `logic-b smoke` passed; `logic-b validate-config config/b0.yaml` passed; `git diff --check` passed. Commit and matching CI URL are appended once the remote run completes.

## Permissions and immediate blockers

- Local Tushare credential: absent (`TUSHARE_TOKEN_CONFIGURED=False`; secret value was never read or printed).
- Existing official-limit probe: `BLOCKED_MISSING_TUSHARE_TOKEN`, [run 38403924915](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403924915). Its 316-byte artifact SHA256 is `7409ba5e30835e4a18359d945aa274c3bbfca9da272530aec312995456a96e6c`.
- Official per-stock limits: 0/3 in the current sample; PIT ST/halt publication times: 0/3 verified; executable rows: 0/3.
- To clear the official-data blocker, the user must provide an authorized Tushare credential with applicable historical `stk_limit`, `stock_st`, and `suspend_d` access, or authorize and provision another licensed source with per-stock/per-day values and historical publication/effective-time evidence. No purchase or access bypass has been attempted.

No main/config change, holdout access, parameter tuning, fabricated historical bars, or real-return claim was made.
