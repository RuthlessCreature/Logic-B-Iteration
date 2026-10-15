# Luna Goal: ACTIVE EXPERIMENT 2025→2026H1 (2026-10-15 user override)

**READ THIS FIRST:** [2025 training / 2026H1 validation hard contract](docs/LUNA_GOAL_2025_TRAIN_2026_VALIDATE.md) and [direct Goal prompt](docs/LUNA_GOAL_PROMPT_2025_2026.md). This OVERRIDES all earlier instructions below stating 2020-2026 is the active data collection/research period.

**TRAIN ONLY:** 2025-01-01..2025-12-31. **VALIDATION ONLY:** 2026-01-01..2026-06-30. **Do not use any 2020-2024 market history to train/tune the ACTIVE GOAL.** Retain 2020-2024 historical samples as legacy regression fixtures. Never access protected 2026-07-01..2026-09-28.

**Active config:** `config/goal_2025_2026.json`; **old regression** `config/research.json` must NOT be used for current Goal. The `python -m logic_b.goal` CLI is the user-visible iteration + train/validation equity + storage byte dashboard. A real data acquisition pipeline and storage permanence remain to be completed. **Passing demo CI is not real training/validation.**

**Goals in priority order:**
(1) actual 2025+2026H1 vendor data (XGB pool / BaoStock bars) with monthly cache and measured physical bytes, retry failure partitions; (2) reliable 10k trading replay and as-of features;
(3) participant psychology / MarketState / MarketGate and LogicA proxy iterations on 2025 only, keep every iteration hypothesis/diff/return/MDD curve; (4) freeze training-selected version and ONLY THEN run 2026H1 validation once;
(5) user-readable HTML/SVG dashboards, coverage/storage growth by month, honest no-follow verdict and checkpoint in GitHub.
Codex=OFFLINE research/optimization. DeepSeek/Jev=FUTURE DAILY RUNTIME, both currently disabled. R2/D1 are not yet connected. No raw third-party market rows published to GitHub and no paid APIs/live broker orders without approval.

**Never select strategies using validation P&L.** Validation is an already-exposed development segment, not pristine blind OOS. If missing data, report partial status and exact missing bytes/days; don't fake the ROI. Retain PR #1 Draft, no main merge or force push. Existing parts of AGENTS.md below describe historical contracts and are superseded where they conflict with this paragraph.

---

# IMPORTANT — Read the authoritative Luna handoff first

**Critical 2026-10-15 role correction:** [Offline Codex research vs Daily DeepSeek/Jev runtime architecture](docs/RESEARCH_VS_RUNTIME_ARCHITECTURE.md) controls. Codex/OpenAI researches/trains/backtests/iterates/freeze strategy. **DeepSeek and TypeSafe Jev are intended for future actual production runtime inference** (distinct contextual LLM vs typed decision inference), not fallback research Agents. Build a deployable bounded, frozen-version runtime with explicit as-of, cost/timeouts and hard gates. They remain currently DISABLED/unconnected with no real API traffic. [Runtime scaffold](src/logic_b/runtime.py) is mock-only, not a live deployment. Future activation requires user authorization and shadow/paper verification. Do not conflate strategy validation with external provider billing or automatic broker orders.


**New reservation (2026-10-15):** TypeSafe AI Jev uses a **separate typed DecisionProvider** (choice/score/noul), not the DeepSeek/OpenAI generative LLM interface. Read [docs/JEV_TYPESAFE_RESERVED_API.md](docs/JEV_TYPESAFE_RESERVED_API.md) and Handoff §12. Official API `https://api.typesafe.ai/v1/systemone`. Both JEV and DeepSeek are **currently** disabled/unconnected/not billed, but are intended to be active runtime inference components after strategy validation and explicit authorization, no premature calls. Jev is *advisory only*, never allowed to override MarketGate or transmit orders.


**Handoff:** [docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md](docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md).
**Persistent checkpoint:** [research/GOAL_CHECKPOINT.md](research/GOAL_CHECKPOINT.md).

This project MUST study **participant psychology proxies, market emotion/earning-loss feedback, ATTACK/TRIAL/NEUTRAL/RETREAT/ICE states and risk vetoes** as a central, testable research layer connecting historical market data to practical after-cost trading decisions. This is not merely a consecutive-limit-up probability project. Read the linked handoff before altering any research architecture, treating its current project instructions as higher priority than archived H01/H02 design.

**Offline/Runtime distinction:** OpenAI Codex is the primary research/training and backtest Agent. DeepSeek and Jev are planned for *actual daily runtime inference* (separate adapters, limited budget, strict time cutoff), both not yet activated. See `config/runtime.json`. No premature external calls, silent fallbacks, model activation, or claimed production connectivity.

**Immediate tasks:** fix BaoStock 10002007 partial request failure and prevent re-fetch, implement incremental replay state, build timestamped market negative-feedback and regime V1, then paired fee-inclusive V0 vs V1 replay with failures preserved. Do not treat successful CI, 2020 January -22.98% v0 result, or story-based psychology labels as proof of a tradable edge. Protected 2026-07-01..09-28 remains inaccessible.

---

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
