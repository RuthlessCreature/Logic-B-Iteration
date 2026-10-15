# H02 data access requirements and shortest unblock path

Checked: 2026-10-14. Scope: 2020-01-03 three-symbol pilot and development data no later than 2026-06-30. The protected 2026-07-01..2026-09-28 interval is excluded.

## Current observed state

- Local environment has no `TUSHARE_TOKEN` configured. The value was never read or printed.
- The latest historical CI probe available at the start of this work reported `BLOCKED_MISSING_TUSHARE_TOKEN`; its successful job status meant the probe ran, not that the source was accessible: [run 38403924915](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403924915).
- Current retained 2020-01-03 matrix: 3 candidate symbol-days; official limit evidence 0/3; independently verified PIT ST/halt 0/3; execution eligible 0/3.
- No local 2024-09-30..2026-06-30 market partitions or runs were found. Expected continuous-period denominator is unknown until licensed candidate/calendar partitions are available.

## Data permission and source capability

| Need | Candidate endpoint/source | Documented capability | Permission and remaining caveat |
|---|---|---|---|
| Per-stock daily upper/lower limits | Tushare Pro `stk_limit` | `trade_date, ts_code, pre_close, up_limit, down_limit, asset_type, exchange`; up to 5,800 rows/request; documented update around 09:00 | 2,000 points required. Must still check all 3 symbol-days, special/no-limit cases, row uniqueness, numeric validity, units/adjustment, and obtain historical publication-time evidence. The current provider note is not a retained 2020 publication log. [Official docs](https://tushare.pro/document/2?doc_id=183) |
| Historical ST labels | Tushare Pro `stock_st` | Historical daily ST list from 2000-01-01; up to 1,000 rows/request; documentation says updated at 09:20 | 3,000 points required. Page-level update schedule is not proof that the exact historical 2020 snapshot was available before that day's 09:35 decision. [Official docs](https://tushare.pro/document/2?doc_id=397) |
| Suspension/resumption facts and intraday timing | Tushare Pro `suspend_d` | Daily suspension/resumption records since 2000-01-03; `suspend_timing` is present for intraday suspension | 2,000 points required. Documentation says update is irregular; historical publication time and per-symbol sample coverage must be checked. [Official docs](https://tushare.pro/document/2?doc_id=214) |
| 1-minute historical bars, if needed as an alternative licensed source | Tushare historical minute | 1/5/15/30/60-minute data since 2009 | Separately licensed, documented at RMB 2,000/year for individuals; this is not approved or purchased. Existing Xuangubao minute provenance/time-label/license still needs clarification. [Official permission table](https://tushare.pro/document/2?doc_id=290) |
| Independent daily EOD reference | BaoStock | Prior workflow obtained unadjusted daily OHLC, `isST`, `tradestatus` | Existing 2020 records are EOD references only. They do not certify 09:35 PIT availability and cannot replace official price limits. |

## Fastest safe permission probe

1. The user can provision an authorized Tushare token with `stk_limit`, `stock_st`, and `suspend_d` access in the local `TUSHARE_TOKEN` environment variable or as the repository Actions secret. Do not send the token in chat or commit it. Confirm the required points/permissions are already available; no purchase is implied by this request.
2. Run the existing narrow probe workflow for **2020-01-03 only** and the three existing symbols (`000998.SZ`, `000716.SZ`, `600421.SH`). It records status without displaying credentials and is bounded to `stk_limit`, `stock_st`, `suspend_d`.
3. Validate actual output values and coverage. Preserve returned rows only where source terms permit. Record retrieval time separately from historical effective/publication time; without defensible 09:35 availability evidence, retain `PIT_UNVERIFIED`.
4. For a 2024-2026 development slice, first provide or enable authorized candidate/calendar/daily/minute partitions and license terms. There are currently 0 discovered local partitions and no verified expected denominator, so no continuous eligible window can be named yet.

## Permission request to user

Please provide one of the following when convenient:

- An already-authorized token configured locally or as a GitHub Actions secret, plus confirmation that it has the three endpoint permissions above; or
- A licensed alternative dataset containing per-symbol/per-date official-equivalent upper/lower limits, ST state, suspension timing, and historical publication/effective timestamps for the required development dates.

If neither is available, no official-data request can pass. The 2020 minute diagnosis, synthetic execution tests, and offline/cache inventory can continue independently. No data purchase or access bypass has been attempted.

## Source restrictions still unresolved

The archived Xuangubao minute/candidate artifacts show hashes and source tags, but the retained project files do not establish redistribution terms for those endpoints. Do not republish raw artifacts or start another broad live query until the applicable terms and an approved retention boundary are documented. Existing historical logs/artifact summaries can still be cited as prior observations, not as a current reproducible data lake.
