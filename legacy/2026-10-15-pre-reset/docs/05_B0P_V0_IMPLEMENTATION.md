# B0-P v0 Implementation

## Status

B0-P.0 is an executable baseline proxy for Logic A. It is **not yet a validated profitable strategy**.

## Current pipeline

1. Previous-day THS limit-up universe
2. Previous-day interpretable ranks
3. Market-regime gate
4. Current checkpoint confirmation
5. Core-type classification
6. Tradability gate
7. Single-core selection or CASH
8. Three-level fill simulation
9. T+1 portfolio enforcement
10. Equity/trade metrics
11. Point-in-time leak guard

## Native Tushare fields

The implementation now directly supports `limit_list_ths` fields:
- `tag`: parses 首板 / N天M板
- `turnover`:成交额
- `turnover_rate`:换手率
- `open_num`:打开次数
- `limit_amount`
- `lu_limit_order`

## B0-P.0 frozen previous-day score

- height rank: 36%
- amount rank: 24%
- turnover-rate rank: 16%
- max-seal rank: 14%
- open-quality rank: 10%

These weights are deliberately **not optimized on the target two-year history**. They are a sacrificial baseline to measure before B1.

## Market gate

B0-P.0 classifies ATTACK / TRIAL / NEUTRAL / RETREAT / ICE from:
- limit-up count
- limit-down count
- break rate
- highest board
- previous limit-up median return

RETREAT and ICE block new entries.

## Execution assumptions

- Optimistic: first post-signal bar, upper-bound only.
- Realistic: first minute that is not continuously sealed/locked.
- Conservative: two consecutive openable minutes.

These are bar approximations. They are not Level-2 queue reconstruction.

## Required before publishing a two-year return

- historical market-regime builder
- checkpoint builder from minute bars
- date-aware price-limit/ST/IPO rules
- explicit exit baseline
- walk-forward runner
- artifact writer
- topic/sector point-in-time layer
- B0-H manual labels and agreement test

No return number should be treated as valid until those items are implemented.
