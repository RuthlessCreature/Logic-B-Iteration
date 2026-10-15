# H02 P2-A coverage matrix — 2020-01-03 sample

Date: 2026-10-14 (Asia/Shanghai)
Branch: `research/behavioral-edge-20261013`
Scope: three candidate symbol-days from D-1 `2020-01-02` to D `2020-01-03`. Minute bars were re-queried from the existing Xuangubao provider on 2026-10-14. Each query was repeated once; canonical normalized-record SHA256 values matched for all three pairs. The rows themselves were held in memory only and were not committed. Candidate membership and BaoStock status remain supported by archived workflow outputs.

Machine-readable row-level status: [P2A_COVERAGE_MATRIX_20261014.json](P2A_COVERAGE_MATRIX_20261014.json).
The fixed-schema canonicalizer is [`h02_coverage_matrix.py`](../../../src/logic_b/h02_coverage_matrix.py); `tests/test_h02_coverage_matrix.py` checks byte-identical serialization for repeated input, duplicate symbol-day rejection, the protected-date guard, and fail-closed behavior when official limits are absent.

## Evidence by layer

| Symbol-day | D-1 candidate | Independent daily D | ST / halt reference D | Official price limits D | Minute sample D | PIT certified | Execution ready |
|---|---|---|---|---|---|---|---|
| 000998.SZ / 2020-01-03 | Present in prior-day limit-up universe | BaoStock EOD present; cross-provider OHLC agrees | BaoStock `isST=false`, `tradestatus=true`; EOD only | Missing | Xuangubao 245 bars; five bars at 11:31–11:35; current P0 audit blocks | No | No |
| 000716.SZ / 2020-01-03 | Present in prior-day limit-up universe | BaoStock EOD present; open/low differ by RMB 0.02 | BaoStock `isST=false`, `tradestatus=true`; EOD only | Missing | Xuangubao 245 bars; five bars at 11:31–11:35; current P0 audit blocks | No | No |
| 600421.SH / 2020-01-03 | Present in prior-day limit-up universe | BaoStock EOD present; cross-provider OHLC agrees | BaoStock `isST=true`, `tradestatus=true`; EOD only | Missing | Xuangubao 148 bars; current audit returns `STRUCTURALLY_VALID` | No | No |

The earlier full-day audit covered 94 D-1 candidates and reported SHA-verified minute partitions; 89 passed its provisional >=180-bar threshold. Applying the P0 strict session audit to current provider responses found 11:31–11:35 bars in 000998.SZ and 000716.SZ, so those two now fail closed despite passing the older threshold. The selected 600421.SH case shows why low minute counts must not be relabeled as a halt or corruption without separate evidence. None of the three rows has a verified executable fill.

## Provenance and reproducibility limits

- Direct minute re-query: `XuangubaoMarketProvider` converted Unix `tick_at` values through `Asia/Shanghai` and returned naive local timestamps. Canonical normalized-frame hashes, identical on two queries per symbol: 000998.SZ `8b3504e992b44a2b45d9a49d8ab7e3b6c69d8dd1d0193254332b858e7c0e1af0`; 000716.SZ `9595206d408e675b944f41aafa38d034694d1362daca9d76d5bca024faf4951a`; 600421.SH `232392a48e3b0680a3ba24c2074a1efb476c54c040300df8940af0d7efbe92ce`. The hash covers `DataFrame.to_json(orient=records,date_format=iso,double_precision=15)` UTF-8 bytes, not the provider's original response payload.
- Candidate pool source: [full-day audit run 38384217991](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38384217991), based on archived `h01-raw-2020h1` source artifact SHA256 `09dbc7f75aa7df0789abff863992d61d6ebbee892dc120c6c9a7b942d4af2c9e`. That run reported all three historical minute manifests verified. Its retained 605-byte artifact is a summary; it does not contain raw minute partitions or per-symbol historical partition digests.
- Independent status/cross-source comparison: [run 38384941333](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38384941333), BaoStock EOD versus Xuangubao 1m. The 661-byte summary artifact SHA256 is `87c62d95d7a314ea325401c97ecfd8c65f07521232c66fa1af9d9fe215bfba9f`.
- The repository separately records a narrow BaoStock historical reference batch of 264/264 candidate-days for 2020-01-03, 2020-01-06 and 2020-01-07. Its `isST` and `tradestatus` are EOD reference fields, not proven public by each day's 09:35 decision.
- No independent exchange calendar record was present in the retained sample report. Provider code converts the Unix timestamps to `Asia/Shanghai`, then strips timezone metadata; PIT publication time is still unproven.
- The official price-limit permission probe recorded `BLOCKED_MISSING_TUSHARE_TOKEN` ([run 38403924915](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403924915)). No computed 5/10/20% substitute was used.
- The older batch's individual minute partitions and exact per-partition hashes were not retained in its summary artifact. Identical rerun output and per-row source hashes therefore cannot be independently reproduced from this checkout.

## Gate

`BLOCKED_INCOMPLETE_PROVENANCE_AND_EXECUTION_EVIDENCE`: current structural audit passes 1/3 minute samples; official limits are 0/3, PIT-certified rows are 0/3, and execution-ready rows are 0/3. The 000716.SZ daily/minute discrepancy remains open. The two 11:31–11:35 cases are failed structural inputs, not filled or repaired. No return calculation or net-equity claim was made. The protected 2026-07-01 through 2026-09-28 holdout was not accessed.

## Next action

Preserve one approved historical sample's raw, licensed inputs and source manifest in a controlled artifact, then rerun the deterministic matrix builder against those exact inputs. Keep the official-limit gate blocked until authorized Tushare access and real point-in-time status timing are independently proven.
