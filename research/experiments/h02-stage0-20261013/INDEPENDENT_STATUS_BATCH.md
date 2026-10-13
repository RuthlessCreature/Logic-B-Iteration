# H02 independent candidate-state ingestion — 2026-10-13

## Verified end-to-end batch (historical, not a tradable replay)

- GitHub run: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403595165
- Window: D-1 limit-up candidates on 2020-01-03, 2020-01-06, 2020-01-07 (2020-01-02 is warmup).
- Expected stock-days: **264**.
- BaoStock valid independent historical daily stock-days: **264** (100% in this narrow window), missing: 0; failed symbols: 0.
- Historical ST flags: **53 stock-days** (NOT 53 distinct stocks).
- Historical non-trading flags: **2 stock-days** (NOT 2 distinct stocks).
- Stored separately as SHA256-verified `h02_reference_daily/YYYYMMDD.parquet` during the CI run; no overwriting previous XGB evidence and no replacing canonical official limit or halt partitions.
- Test suite: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403605377 (PASS).

**Limitations:** BaoStock data are historical daily EOD records, `isST` and `tradestatus` are not yet independently certified as available at each day 09:35; `stk_limit` remains absent; thus the 264 records are for data quality, not trading signals or executable net returns.

## Official daily price-limits credential probe

- GitHub run: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403924915
- Result: **BLOCKED_MISSING_TUSHARE_TOKEN**. The workflow executed and archived a JSON report (GitHub job success denotes successful diagnosis, NOT access success).
- It tested for `TUSHARE_TOKEN` presence without revealing a credential. It did not query `stk_limit`, `stock_st`, or `suspend_d` because no credential was present.
- Do NOT replace this missing official price-limit dataset by an inferred 5/10/20% band and claim precise fill simulation.

## Next test

- Jan 2020 batch source-state collection submitted:
  https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38404221537
- Covers all historical D-1 closing limit-up candidate symbol-days in January 2020; output must be read from its artifact **after** successful completion; do not assume 100% coverage in advance.
- Frozen original 2026-07-01..09-28 blind holdout remains inaccessible for H02 research.
- Stage 0 H02: not completed. Six-year after-cost equity curve: not available.

## Decision policy

Do not repeat H01 market-proxy tuning: its long-horizon paired predictive gain was statistically unsupported. H02 must identify directly simulated after-cost follower P&L and demonstrable point-in-time crowding before claiming a psychological edge. Old B0 remains frozen.
