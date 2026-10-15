# RFC-009: Psychology-first A-share Ultra-short Equity Research

Status: PROPOSED — research protocol, not a profitable-strategy claim
Date: 2026-10-13
Owner: Logic-B research
Scope: mainland A-shares, long-only, ultra-short (entry intraday, exits subject to T+1)
Baseline: frozen B0.0.3 / B0-P.1, NOT replaced

## 1. Decision and objective

**Psychological mechanisms are the research foundation.** Market and execution data are imperfect observations of those mechanisms. Research engineering turns falsifiable behavioral hypotheses into testable, executable trading decisions. **Realistic net equity growth, subject to tail-risk limits, is the final objective.**

Do not optimize explanatory elegance, hit rate alone, model complexity, or the apparent quality of a historical equity curve.

Primary ranking: out-of-sample portfolio log-equity growth after commissions, transfer fees, stamp duty, market-impact/slippage and unfilled orders, with a non-compensating drawdown and data-integrity gate.
Secondary measures: trade-level net expectancy, maximum drawdown, conditional value at risk, exposure, turnover, unfilled percentage, number of closed trades, walk-forward stability and risk concentration.

No claim of historical performance is permitted until the actual dataset and reproducible run artifacts exist. No single quantitative threshold guarantees real-world profit.

## 2. The causal theory (do not quietly turn it into chart-pattern folklore)

Proposed feedback loop:
experienced or perceived P&L / news attention / expected payoff
-> belief updating, imitation, fear, profit-taking and risk appetite
-> *observable* candidate selection, order urgency, breadth, turnover and price impact
-> subsequent P&L outcomes
-> new feedback cycle.

The psychological variables are generally **latent**. With public market data we see prices, volumes, status, and sometimes order book events; we do NOT observe the same identified investors' beliefs, accounts, cost basis, intentions or future orders.

All strategy-cohort returns are **hypothetical executable proxies**, not measured P&L of actual 'hot money', institutions or retail investors. Cross-stock capital rotation is a hypothesis, not proof that the same cash migrated between the two names.

Relevant literature:
- Barber & Odean, 2008, RFS: investor attention and purchases, doi:10.1093/rfs/hhm079
- Malmendier, Pouzo & Vanasco, 2020, JFE: experience-based learning, doi:10.1016/j.jfineco.2019.11.002
- Hasbrouck, 1991, JF: order-flow/quote-change price impact, doi:10.1111/j.1540-6261.1991.tb03749.x
- Bailey et al., 2014, Notices AMS: backtest overfitting, SSRN 2308659

External results motivate hypotheses; none establishes A-share strategy profitability.

## 3. Hypotheses registered BEFORE outcome inspection

| ID | Latent mechanism | Point-in-time observable proxy | Falsifiable test |
|---|---|---|---|
| H01 | Recent winner reinforcement | Rolling *realistically executable* lagged P&L for a frozen D-1 momentum/limit-up-following cohort, alongside loss breadth and exposure | Positive-cohort state predicts better next-day *net* opportunity than negative state after controlling for market regime; test monotonicity and reversals |
| H02 | Imitation/attention diffusion | Historical theme membership, number/share of active components, synchronized volume shock, independent breadth expansion at t | Expansion improves forward *net* continuation vs a matched core-strength/momentum baseline |
| H03 | Panic and liquidity withdrawal | Fraction of prior cohort trades hypothetically underwater, negative gap frequency, limit-down/breakdown breadth | Predicts higher next-day adverse-tail loss; compare filter vs unconditional trading |
| H04 | Expectation violation | Opening auction/early price relative to *previously observable* strength and cohort expectancy proxy, measured at a fixed checkpoint | Contrary-to-expectation opening outcomes predict subsequent failed continuation/price response |
| H05 | Crowding/exhaustion | Strong attention proxy + flattening price response to turnover, repeated breaks, diminishing follow-through | Nonlinear crowding predicts net reversals rather than assuming 'more attention = always good' |

**First wedge:** H01, with H03 as safety filter only AFTER H01's standalone result is recorded.
**Alternative:** H02 if H01 fails or required cohort proxies cannot be computed.
**Rejected for phase 1:** 'Identify named hot-money accounts from price action' or LLM opinion as the primary trading signal.

Anti-narrative principle: a pretty psychological explanation without predictive and executable benefit is a failed hypothesis.

## 4. Experimental cohort definitions

Create a registry of static, parameter-frozen, reproducible proxy trading rules. Initially:
- COHORT_MOMENTUM: previous-day strongest tradable names, fixed entry at next decision checkpoint and pre-registered T+1 exit.
- COHORT_BREAKOUT: intraday momentum/breakout signals observable strictly before decision time, with executable fills modeled later.
- COHORT_DIP: prior-day sharp losers, next-day rebound proxy (control group).

For every cohort define **universe, eligibility, as-of timestamp, tie-breaking, fee schedule, limit-up/limit-down logic, unfilled treatment, exit handling, T+1 and suspension logic**. The first version may start with H01 using the COHORT_MOMENTUM alone.

Do NOT equate these synthetic cohort returns with actual collective investor profits or actual net fund flows. No price level derived from future data may define the cohort at a past checkpoint.

## 5. As-of correctness: core engineering contract

Primary research checkpoint: **09:35 Asia/Shanghai** for research comparability to B0. No new trades from 09:30 through 09:35 if B0's frozen guard remains in effect; executable fills start only AFTER the feature data has completed and the decision is generated.

Event fields: `trade_date`, `exchange_time`, `available_at`, `source`, `revision`, `symbol`, `feature_name`, `feature_value`, `population`, `quality_flag`, `data_hash`.

Data availability, not just event timestamp, determines whether a feature is legal. A bar ending at 09:35 cannot both generate the 09:35 signal and fill at a price inside that same completed bar.

Historical themes, IPO status, risk warning/ST, corporate actions, suspensions and daily price limits must be known as of the tested date. Universe must avoid survivorship bias.

## 6. Data adequacy and immediate bottleneck

Existing Logic-B B0 Xuangubao fallback is a **D-1 limit-up candidate slice**. This is sufficient for its own narrow B0 replay but INSUFFICIENT to measure full-market participant cohorts, selection bias, dip controls or broad attention diffusion.

Data tiers:
- Tier D (mandatory): point-in-time whole eligible universe daily OHLCV/adjustment, status, official limits, trading calendar, historical top gainers/losers, limit-up/limit-break/limit-down evidence, and historical sector constituents where used.
- Tier M (mandatory before an intraday strategy claim): minute data for chosen cohorts plus predeclared controls, selected at the prior checkpoint; support conservative fill replay.
- Tier L2 (optional): timestamped trades, orders/cancellations and order book. No synthetic depth or inferred 'actual institution activity' from OHLCV.

Preflight permission, cost and sample integrity. Missing critical coverage -> `BLOCKED`, NOT an optimistic backtest. Keep Tushare and Xuangubao data lineage separate and compare overlapping dates before combination.

## 7. Reuse the existing engineering foundation

Keep existing frozen:
- B0.0.3 and B0-H/B0-P alignment;
- B0 T+1, no same-bar fills, limits/suspensions, trade accounting;
- SHA256 data manifest, readiness/audit, walk-forward, locked holdout;
- non-compensating promotion gate.

Add new modules, do not silently redefine B0:
```
src/logic_b/behavior/
    cohort_registry.py         # explicit proxy agent policies and constraints
    asof_features.py           # frozen feature-time definitions
    hypothesis_h01.py          # first behavioral state hypothesis
    experiment_runner.py       # paired B0/cash/momentum comparison
schemas/behavioral_feature.schema.yaml
research/experiments/<id>/     # hypothesis, inputs, full failed & passed trials
```

Inputs: canonical point-in-time lake; versioned registry; immutable experiment manifest.
Outputs: cohort_features.parquet, signals.parquet, fills.parquet, daily_equity.parquet, metrics.json, fold_metrics.parquet, missing_data.json, run_manifest.json, and a decision PASS/FAIL/BLOCKED.

No external LLM should directly invent training labels, synthesize facts about account behavior or bypass hard trading rules. LLM may propose hypotheses and audit result anomalies; numerical engine computes signals, fills and P&L deterministically.

## 8. Comparison: what makes a hypothesis actionable?

Paired validation on identical dates, tradable universe, decision times, information cutoffs, capital, position policy and fill-cost scenarios:
1. B0.0.3 frozen baseline;
2. cash/no-trade risk baseline;
3. naive pre-registered momentum baseline;
4. B1-H01 psychology-conditioned strategy.

Chronological development / walk-forward / untouched blind holdout. Existing repository's 2024-09-30..2026-06-30 development, 2026-07-01..2026-09-28 holdout are already historically frozen, so we may NOT mine outcomes in the previously designated blind period and then describe it as untouched evidence for a new psychology strategy. If prior researchers have seen it, mark it contaminated for this new hypothesis and reserve later-forward data.

Required reporting includes conservative net results, trade count, bootstrap interval by trading-date block, worst regimes, sensitivity neighbors and explicit missing-data percentage. Verify after transaction costs and fill failures.

**Initial engineering go/no-go thresholds (prospectively chosen, not results):**
- critical daily universe coverage >= 99%, required feature lineage 100%, no future leakage;
- >= 30 closed trades per meaningful comparison; if fewer, `BLOCKED`, not PASS;
- realistic AND conservative net expectancy > 0;
- positive paired after-cost equity benefit vs chosen baseline in a genuinely unseen period, with directionally stable walk-forward folds;
- max simulated drawdown <= 25% to stay compatible with B0's existing high-risk research gate; this is NOT a recommended personal drawdown budget;
- 100% unit-test coverage for specified time-gating/suspension/limit-lock scenarios (test-case coverage, not code coverage).

These thresholds are provisional B1 research gates; freeze them in a separate versioned config BEFORE running B1 returns. No retrospective tuning for PASS.

## 9. Phases, owners and acceptance

**Phase A — Data truth / 48-hour audit.** Owner: research engineering. Deliver: source capability matrix, all-day universe coverage audit, minute coverage by cohort, permission status, data dictionary, missingness report. Fail if the existing B0-only candidate lake is used to claim whole-market psychology coverage.

**Phase B — H01 behavioral feature, no trades.** Deliver: frozen cohort definitions, time-correct rolling net outcome series, counterexamples, negative controls, lookahead unit tests and a feature manifest. Fail if hypothetical fill losses on limit-down or missing order books are ignored.

**Phase C — executable experiment.** Deliver: B0 vs cash vs naive momentum vs B1-H01, realistic/conservative fills, paired equity and risk report, ablations with cohort reinforcement removed. Fail if net benefit disappears outside in-sample or in conservative fills.

**Phase D — paper trading then risk-limited pilot.** Minimum forward evidence duration must be chosen prospectively after Phase C, not reverse engineered from an attractive first month. Gate by signal/filled-order parity, data latency, exposure, kill-switch behavior, broker compatibility and current rules. No automatic live deployment from research PASS.

Human ownership:
- user: risk budget, risk tolerance and approval of any move from simulated to live;
- research engine: deterministic data, evaluation and audit;
- model/assistant: hypothesis generation, specification and analysis, never fake confirmed gains.

## 10. Stop/rollback conditions

STOP if: missing data, inability to reconstruct historical information timing, same-bar fills, disallowed future features, selection bias, illiquid unfilled entries treated as wins, unfrozen cohort edits, in-sample-only apparent edge, test contamination, missing audit artifacts, or drawdown above the frozen budget.

ROLLBACK: route to B0 research-only mode and cash/paper observation, with unchanged original B0 code. Never override a red data/risk gate by manual 'confidence'.

## 11. Next actual task

Run Phase A data audit **before** adding H01 model complexity. Existing README explicitly states no verified two-year B0 return has been published. Deliver data readiness and first frozen cohort registry, then revisit any predictive claim.
