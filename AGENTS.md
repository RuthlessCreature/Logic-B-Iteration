# Logic-B Autonomous Research Goal — current project, not legacy

## Non-negotiable user outcome

Deliver an understandable, reproducible **personal trading research system**:
2020-01-01 to 2026-06-30 Xuangubao event data + BaoStock real historical OHLC,
a 10,000 CNY single-position T+1 account, commission **0.025% EACH SIDE
minimum 5 CNY**, separately dated taxes/transfer fees, buy-at-limit-unfillable
and sell-at-limit-unfillable, ranked candidate + empty-cash days, real price
simulation, annual cash/equity curve and independent human FOLLOW/NO_FOLLOW.

A stock remains one instrument across ST/*ST/name changes. Symbols include exchange.

The LLM must propose **falsifiable, machine-validated strategy versions**, never
fabricate data, rewrite trade fills, or place broker orders. Validation dates
2025-01-01..2026-06-30 are chronologically subsequent to training
2020-01-01..2024-12-31, but repeated selection on validation contaminates that
segment; keep a versioned search ledger. Do not touch old protected
2026-07-01..2026-09-28 market data.

## GitHub

Research branch: `research/behavioral-edge-20261013`, PR #1 Draft,
base `main`. Do not alter main, merge PR, or force push.
Every significant engineering stage must have tests and actual CI on its SHA.

`legacy/2026-10-15-pre-reset/` is an *entire byte-identical archive* of previous
logic_b H01/H02 code/data proofs/workflows and strategy definitions. You may read
for inspiration, but don't re-enable its CI or treat archived event forecasts as
current after-cost returns.

## Priority queue (execute autonomously, don't ask for ordinary engineering choices)

1. Keep new `logic-b-core` pytest and deterministic synthetic cash smoke green.
2. Audit real-data January 2020 workflow `first-real-data-pilot`; summarize
   missing K bars, candidate selection, filled buys/sells, locked exits and
   marking staleness. Never promote 7- or 16-day mark-to-market to annual alpha.
3. Run *entire* January 2020 with incremental local XGB + BaoStock cache,
   then 2020 year, then remaining years to June 2026. Never commit proprietary
   raw market responses to public GitHub. Prefer SHA manifests and aggregate
   summaries. Fix re-downloads, rate limits and source gaps before scaling.
4. Historic corporate actions: price bars must be consistent with share count
   and splits/dividends; reject unjustified cash-equity performance across
   unresolved ex-rights days. Preserve historical ST and price-limit bands.
5. Link LLM research CLI to frozen training-only stats; queue candidate hypotheses,
   compare against unchanged baseline in chronological validation, report
   negative outcomes too. Never mutate transaction fees to produce profit.
6. For each tested strategy version produce: 2020..2026 yearly trade count,
   completed trades, unfillable entries/exits, daily equity, realized/unrealized
   P&L, costs, max drawdown, data coverage and reproducible code/data IDs.
7. A user-readable `python -m logic_b.follow` watchlist is always
   review-only. No broker integration without explicit permission.

## Done criterion

User can read one annual equity table and a stable FOLLOW / NO_FOLLOW
decision with traceable candidate reason and risk, after actual market-price
replay, and can request another version without losing a prior result.
Do not equate passing unit tests or making an LLM call with actual validated
research results. If full historical data cannot be obtained, give
`PARTIAL` with measured date/price gaps and a viable best-effort alternative.
