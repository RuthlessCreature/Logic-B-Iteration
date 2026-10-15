# H02 final stock-event feature and conditional-rate research

**Classification:** TIER D exploratory vendor event data; all historical input availability is `PIT_UNVERIFIED`. This is not trading performance.

Study: 20240930 through 20260630. Training ends 20250630; validation ends 20251231; forward development ends 20260630.

Generated 36,775 stock-day rows from five SHA-pinned archives. The row matrix is local ignored output only; normalized SHA256: `f1a8a9e34feb9bffc78bdb9cfe35dae2c0fe1418f9fe4b13822be205845b5dd9`.

All feature rows use D-1 or earlier event pools. D outcomes are labels only. Historical publication time is not certified.

## Outcome and group tables

The group schema and every predeclared level are in the machine-readable JSON. Empty groups are retained. Confidence intervals use a deterministic 5-trading-day circular block bootstrap (1,000 replicates). They describe clustered event rates; overlapping labels and exposed development periods still limit inference.

| Phase | Target | Events / eligible candidate symbol-days | Rate | 95% day-block interval |
|---|---|---:|---:|---:|
| train | Y1_D_vendor_limit_up_pool | 5,026/17,729 | 28.3490% | 25.7920%–30.6619% |
| train | Y2_D_vendor_limit_down_pool | 674/17,729 | 3.8017% | 2.9488%–4.6775% |
| train | Y3_D_to_D2_vendor_limit_down_pool | 2,740/17,599 | 15.5691% | 12.4277%–18.6516% |
| validation_2025H2 | Y1_D_vendor_limit_up_pool | 2,240/9,015 | 24.8475% | 23.4262%–26.3407% |
| validation_2025H2 | Y2_D_vendor_limit_down_pool | 256/9,015 | 2.8397% | 2.3099%–3.4570% |
| validation_2025H2 | Y3_D_to_D2_vendor_limit_down_pool | 982/8,863 | 11.0798% | 9.5319%–13.1339% |
| forward_2026H1 | Y1_D_vendor_limit_up_pool | 2,105/10,031 | 20.9849% | 19.3227%–22.8709% |
| forward_2026H1 | Y2_D_vendor_limit_down_pool | 300/10,031 | 2.9907% | 2.3350%–3.7415% |
| forward_2026H1 | Y3_D_to_D2_vendor_limit_down_pool | 1,056/9,836 | 10.7361% | 8.5666%–13.2070% |

## Feature availability and boundary

The archives include vendor limit-break pools, market-indicator snapshots and theme labels, so those are summarized as vendor-derived features where structurally present. No turnover, capital-flow, order-book, or independent sector-core truth is inferred beyond fields present in the archive. `theme_hhi` is only concentration of vendor theme assignments.

The source archive has no independent daily OHLC, official per-stock limit prices, independently PIT-timed ST/halt status, or candidate minute bars. No actual fill, return, drawdown, or net equity result can be computed.

## Reproduction

```powershell
python scripts/h02_final_stock_features.py --artifacts <five approved h01-raw ZIP paths> --out-json runs/h02-final-research/features.json --out-markdown runs/h02-final-research/features.md --matrix-out runs/h02-final-research/feature-matrix.csv
```
