# H02 Stage-0 — 2020 Historical Minute Feasibility and Remaining Execution Gate

Date: 2026-10-13. Branch: `research/behavioral-edge-20261013`.
Research purpose: build a *real, point-in-time, fee-inclusive simulated follower cohort* (H02), after H01-A failed to establish stable predictive gain.

## Reproducible empirical source results

Historical evidence archive: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38358815302

1. 2020-01-03 individual-point test against 2020-01-02 D-1 closing limit-up list:
   - 000998.SZ and 000716.SZ fetched, each 245 historical one-minute rows, 09:31 through 15:00, included 09:35, valid OHLC and timestamps.
   - Run: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38383737325
2. 2020-01-03 ten-symbol materialization:
   - 10/10 had >=180 minute records, 09:35 checkpoint, consistent OHLC/trading date, minute SHA manifest, derived daily/limit rows.
   - Run: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38383954684
3. **All prior-day limit-up symbols on 2020-01-03:**
   - 94 distinct candidate symbols queried; 94 returned historical minute sets with correct dates, 09:35 checkpoint, OHLC and sha verification.
   - 89/94 (94.68%) also met the provisional *>=180 bars* coverage threshold. The five under threshold (still time-correct and OHLC-consistent) were:
     - 600421.SH: 148 bars
     - 600485.SH: 160
     - 600652.SH: 127
     - 600654.SH: 125
     - 600666.SH: 178
   - Thin trading and data incompleteness are not distinguishable from bar counts alone. **Do not mark these as halted, corrupted, unfillable, or discard them without independent exchange-volume / trade-status checks.**
   - Run: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38384217991

This establishes **a historical minute endpoint actually works on a 2020 full-day universe**, not complete 2020-2026 coverage, and not an investable backtest.

## Critical historical trading-rule correction

On the provider, `XuangubaoMarketProvider.limit_prices`, ordinary ChiNext price bands now switch from 10% to 20% on 2020-08-24 rather than applying a blanket 20% to all historical dates. Strict boundary tests cover 2020-08-21, 2020-08-24, 2020-01-03, 2026-06-30.

These *computed* bands are tagged `xuangubao_derived_not_official`. They are NOT official stock-specific limits. ST, IPO exemption, delisting and other exceptional cases are not established by this simple formula. Date-specific independently sourced `stk_limit`, `stock_st`, `suspend_d` or equivalent authoritative fields are required for H02 execution certification.

Source: Shenzhen Stock Exchange announcement on the 2020-08-24 ChiNext reform: https://www.szse.cn/aboutus/trends/news/t20200821_580924.html

## New fail-closed H02 data contract

`src/logic_b/h02_certification.py` inspects:
- official-date limit-price provenance;
- independently sourced point-in-time ST and suspension states (even if the list is empty);
- D-1 limit-up candidates and D historical minute partitions with verified manifest and correct date;
- permanent H01/H02 development cutoff 2026-06-30, with original holdout locked.

`READY_FOR_FURTHER_EXECUTION_AUDIT` means **only the source-provenance prerequisite** passed; it NEVER represents validated trade profits. `net_equity_validated` is always false until a separate execution backtest is audited.

As of this report: publicly archived historical XGB sample has *only inferred* price bands/ST and halt indicators. Hence H02 trade-equity promotion gate remains BLOCKED_UNCERTIFIED_EXECUTION_INPUTS.

## Next fixed engineering delivery

1. Acquire independent historical official date-specific limits, ST flags and suspension status; run source quality checks against actual daily bars and corporate actions (account for IPO/no-limit days).
2. Scale candidate minute history by small checkpointed calendar shards. Carry forward D-1 context, check OHLC, time zone, intraday completeness and episode-specific low-liquidity cases. Preserve source manifests and failures; do not silently fill absent bars.
3. Freeze a synthetic *executable follower cohort* with a realistic decision checkpoint and T+1 costs. Distinguish gross return, fees, realistic fills, nonfills, and forced holds. Compare against frozen B0 and cash; do not tune B0 using protected holdout.
4. Score H02-R, H02-C and H02-X separately against lagged market/volatility baselines. If no robust gain, stop without promoting.

**No 2020-2026 executable net-equity claim exists. No actual investor identity or psychology is observed in these feeds.**
