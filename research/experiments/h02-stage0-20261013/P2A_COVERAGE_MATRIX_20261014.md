# H02 P2-A coverage matrix — 2020-01-03 sample

Date: 2026-10-14 (Asia/Shanghai)
Branch: `research/behavioral-edge-20261013`
Scope: three archived candidate symbol-days from D-1 `2020-01-02` to D `2020-01-03`. This is a bounded evidence reconstruction from existing GitHub Actions job output and summary artifacts. It is **not** a fresh raw-data replay.

Machine-readable row-level status: [P2A_COVERAGE_MATRIX_20261014.json](P2A_COVERAGE_MATRIX_20261014.json).

## Evidence by layer

| Symbol-day | D-1 candidate | Independent daily D | ST / halt reference D | Official price limits D | Minute sample D | PIT certified | Execution ready |
|---|---|---|---|---|---|---|---|
| 000998.SZ / 2020-01-03 | Present in prior-day limit-up universe | BaoStock EOD present; cross-provider OHLC agrees | BaoStock `isST=false`, `tradestatus=true`; EOD only | Missing | Xuangubao 245 bars; 09:35 present; partition manifest verified | No | No |
| 000716.SZ / 2020-01-03 | Present in prior-day limit-up universe | BaoStock EOD present; open/low differ by RMB 0.02 | BaoStock `isST=false`, `tradestatus=true`; EOD only | Missing | Xuangubao 245 bars; 09:35 present; partition manifest verified | No | No |
| 600421.SH / 2020-01-03 | Present in prior-day limit-up universe | BaoStock EOD present; cross-provider OHLC agrees | BaoStock `isST=true`, `tradestatus=true`; EOD only | Missing | Xuangubao 148 bars; 09:35 present; partition manifest verified | No | No |

The full-day audit covered 94 D-1 candidates and reported SHA-verified minute partitions. The selected 600421.SH case shows why low minute counts must not be relabeled as a halt or corruption without separate evidence. None of the three rows has a verified executable fill.

## Provenance and reproducibility limits

- Candidate/minute source: [full-day audit run 38384217991](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38384217991), based on archived `h01-raw-2020h1` source artifact SHA256 `09dbc7f75aa7df0789abff863992d61d6ebbee892dc120c6c9a7b942d4af2c9e`. The run reported all three minute manifests verified. Its retained 605-byte artifact is a summary; it does not contain raw minute partitions or the per-symbol partition digests.
- Independent status/cross-source comparison: [run 38384941333](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38384941333), BaoStock EOD versus Xuangubao 1m. The 661-byte summary artifact SHA256 is `87c62d95d7a314ea325401c97ecfd8c65f07521232c66fa1af9d9fe215bfba9f`.
- The repository separately records a narrow BaoStock historical reference batch of 264/264 candidate-days for 2020-01-03, 2020-01-06 and 2020-01-07. Its `isST` and `tradestatus` are EOD reference fields, not proven public by each day's 09:35 decision.
- No independent exchange calendar record or exchange-timezone field was present in the retained sample report. The minute timestamps are naive local-looking values, not timezone-certified timestamps.
- The official price-limit permission probe recorded `BLOCKED_MISSING_TUSHARE_TOKEN` ([run 38403924915](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403924915)). No computed 5/10/20% substitute was used.
- The older batch's individual minute partitions and exact per-partition hashes were not retained in its summary artifact. Identical rerun output and per-row source hashes therefore cannot be independently reproduced from this checkout.

## Gate

`BLOCKED_INCOMPLETE_PROVENANCE_AND_EXECUTION_EVIDENCE`: 3/3 sample minute partitions were structurally reported usable, but official limits are 0/3, PIT-certified rows are 0/3, and execution-ready rows are 0/3. The 000716.SZ discrepancy remains open. No return calculation or net-equity claim was made. The protected 2026-07-01 through 2026-09-28 holdout was not accessed.

## Next action

Preserve raw, licensed inputs and a source manifest for one approved historical sample, then rerun a deterministic matrix builder that writes the full per-partition SHA and all six evidence levels. Keep the official-limit gate blocked until authorized Tushare access and real point-in-time status timing are independently proven.
