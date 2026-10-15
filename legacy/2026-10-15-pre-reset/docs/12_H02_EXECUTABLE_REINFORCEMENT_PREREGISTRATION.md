# H02 — Executable Reinforcement, Crowding and Profit-Taking (preregistered proposal)

**Status: DESIGN / NOT YET BACKTESTED.** H01's market-level three-day vendor prior-limitup mean does not reliably improve daily limit-up repeat forecasting (2020-2026 development; see QUARANTINE_VERDICT_20261013.md). Do not reuse the original 2026-07-01..09-28 holdout to select new indicators.

## The psychological claim (not assumed true)

When momentum imitators EXPERIENCE executable after-cost profits, their propensity to chase may increase. When many similarly positioned traders accumulate profits or losses, their later liquidation / crowding can reverse net expected returns. Only a sequence of observable and time-correct decisions can support inference, not an attractive past equity curve.

## Three discriminating hypotheses

H02-R (real reinforcement): T+1-executable, fee-inclusive returns of a *fixed and realistic simulated momentum-follower cohort* through D-1 improve next-session participation prediction beyond prior limitup count/repeat rate and lagged market return/volatility controls. The cohort is synthetic; it is NOT a measured investor population.

H02-C (crowding): At 09:35 on D, the ratio of eligible momentum-candidate attention/activity to available supply predicts an *interaction* between prior returns and future executed candidate returns. Compare to same-time turnover, gap and recent volatility; use signed turnover or order-flow imbalance ONLY if separately sourced and timestamped. Never call bar-volume-derived approximations Level-2 OFI.

H02-X (exhaustion): Gains of early cohorts combined with weakening bid-side execution imply higher probability of adverse exits in D+1..D+3, accounting for Chinese T+1 and limit-down/halts; no assumption of ability to exit at desired price.

## Inputs and data-source gates

1. Daily candidate universe must be reconstructible at each 09:35 decision checkpoint. Do not use a day-D close-generated limit-up list as a day-D 09:35 candidate input.
2. Historical minute bars, date-specific upper/lower limits, halt statuses, the previous-day close and corporate-action treatment are REQUIRED for execution. Historical vendor market indicator datasets alone do not supply these.
3. Timestamps for all features must be <=09:35D and persisted with provenance/sha. Daily 16:00D summary becomes eligible earliest 09:35D+1 after audited availability.
4. One-share-fill fantasy prohibited: apply 100-share lot sizes, T+1, fees and slippage, nonfills on hard limit-up and locked limit-down, and missing-liquidity shutdown.
5. Prior cohort equity is *hypothetical strategy equity*; avoid labeling it actual observed crowd investor psychology.
6. Include de-listings, suspended stocks, ST status, corporate actions and point-in-time universe to avoid survivorship and hindsight inclusion.

## Measurable stages and precommitted stop signs

Stage 0: data coverage and executable replay evidence. STOP if point-in-time provenance, trading sessions, daily limits, fills, costs, or non-fill behavior cannot be audited.

Stage 1: behavior prediction. Compare baseline controls with lagged net-profit, crowding and exhaustion features through expanding chronological validation. Use block bootstrap, by-year stability, placebo checks and multiple-hypothesis correction (H02-R/C/X are separate tests). STOP if gains are tiny, directionally inconsistent or uncertainty crosses zero; do not mine periods for good-looking regimes after seeing outcomes.

Stage 2: executable capital growth. Only if Stage 1 passes: compare frozen B0 against one predeclared H02-adjusted trade gate on matched sessions. Output annual returns, trades, win fraction, gross and net expectancy, turnover, exposure, maximum drawdown, nonfills, negative tail, fee/slippage sensitivity. Default single-name concentration and A-share T+1 remain explicit. If no fill data, fail with BLOCKED_MISSING_EXECUTABLE_DATA instead of an annualized NAV.

Stage 3: prospectively quarantined validation after freezing all parameters; DO NOT unlock original 2026-07-01..09-28 B0 holdout already identified as protected.

## Engineering delivery order

- Reuse market history already collected (2020-01-01..2026-10-12) for regimes and hypothesis design, never treat its market-close summaries as intraday features.
- Audit actual coverage/price integrity of minute-bar history; first build *coverage matrix* and sample B0 cohort ledger, not a backfilled 2020+ claimed portfolio.
- Freeze cohorts, controls, metrics, data providers and time gates in a machine-readable spec before fitting.
- Backtest Stage 1 then Stage 2; preserve source-gate blocks and disclose missing years.

**Acceptance principle**: psychology explains possible demand; only after-cost executable NAV answers the business question.

## Empirical Stage-0 readiness: 2020 H1 (2026-10-13)

Audited the original archive `h01-raw-2020h1` (117 trading dates), not an assumed replacement data service:

- Five historical market evidence datasets complete; evidence manifest failures = 0.
- Four replay-critical market-wide daily datasets (daily, limit_prices, suspend, stock_st): 468/468 trading-date partitions missing in this **event-only archive**.
- Candidate symbol/days expected from prior-day closing limit-up lists: 9,637.
- Daily bars missing: 9,637; limit-price rows missing: 9,637; 1-minute symbol/day partitions missing: 9,637.
- **H02 EXECUTION GATE = BLOCKED_MISSING_EXECUTABLE_MARKET_DATA** for this sample archive. This does NOT demonstrate that such data are unavailable from other providers or in unrelated runner caches; the 2024/25 short B0 pilot indeed included replay-specific slices.

Independent reproducible run: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38383052897

Do not imply that collecting all years' XGB **evidence lists** has completed a six-year trading-backtest dataset. Next decision is sourcing, costing and checksum-auditing true daily-limit-minute OHLC with legitimate point-in-time market availability.
