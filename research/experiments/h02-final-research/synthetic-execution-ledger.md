# H02 synthetic execution mechanics ledger

**Synthetic only. This is not historical trading or fill evidence.**

B0 version: `B0-P.1 (frozen)`; configured B0 thresholds and `config/b0.yaml` unchanged.

## Locked-up priority candidate and no fallback

Signal: `SYN-A`; selected buy attempt: `SYN-A` / `sealed_limit_no_open`. No alternative buy attempt was made.

## T+1, locked lower limit, suspension, resumed exit

The lifecycle scenario records the next-session locked-limit sell rejection, a suspension-blocked sell, and a later post-09:35 exit. Additional scenarios cover two consecutive locked sessions, a same-day old-position exit that suppresses an otherwise eligible replacement, insufficient cash, and exact maximum round-lot sizing after fees. The report records daily buy/sell attempt caps.

Missing/zero-volume/checkpoint-only bars do not fill. Non-finite/non-positive prices or official limits, negative volume, inconsistent OHLC, and invalid/duplicate/out-of-order timestamps are rejected before any fill. Costs are calculated from the same `TradingCosts` instance used by the replay runner.

No row refers to an actual security or market date. The scenario has no evidentiary weight for realized returns, execution probability or net expectancy.
