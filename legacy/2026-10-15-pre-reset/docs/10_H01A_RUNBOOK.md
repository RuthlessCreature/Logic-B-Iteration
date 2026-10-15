# H01-A Runbook: Psychology to Observable Continuation

Status: EXPLORATORY. No claim of real alpha, trading profit, or identified investor motives.

## Hypothesis

Past *experienced* profitability may reinforce repeated momentum-following purchases and prompt imitation. Public bars do not reveal private investor identities or beliefs.

The narrow observable test asks: **does yesterday-known, fee-inclusive simulated follower profitability add forecast information for today's fraction of yesterday's closing limit-up stocks that again close limit-up today?**

This limit-up repeat ratio is a proxy for momentum continuation, NOT actual measured buying by an identified cohort or causal proof of imitation.

## Data contract

Input market data:
- Xuangubao-style historical market-wide limit_up/YYYYMMDD partitions
- calendar, SHA256 manifests, all required trading dates
- B0 replay data from a preexisting realistic or conservative run OR a separately built executable-cohort ledger

An executable-cohort ledger has: cohort_id, trade_date, net_equity_return (decimal), available_at (timezone-aware).

Missing sessions do not count as 0% returns. For a portfolio that did not trade, use its legitimately observed mark-to-market return including unsold positions.

The B0 adapter models *one simulated B0-protocol follower*, NOT a population of real retail traders; do not mistake B0 for direct human psychology measurements. No account identification is attempted.

## Run data readiness only

    python -m logic_b.h01_cli --data-root data-xgb --start 2024-09-30 --end 2026-06-30 --out runs/h01-a-check

Writes h01_market_activity.parquet when limit-up lists are complete and verified.

Without a cohort ledger, exit 2 with BLOCKED_MISSING_EXECUTABLE_COHORT_LEDGER is the EXPECTED result, not an execution failure. Data corruption/missing lists return BLOCKED_DATA_INVALID.

## Run exploratory H01-A with a completed B0 portfolio

    python -m logic_b.h01_cli --data-root data-xgb --start 2024-09-30 --end 2026-06-30 --b0-daily-equity runs/B0_REALISTIC/daily_equity.parquet --initial-cash 1000000 --out runs/h01-a-b0

initial-cash MUST equal the run's original configuration; B0 portfolio must have already included legitimate fills, fees, T+1, locked exits, holdings and suspension marks. The option --cohort-equity path.parquet --cohort-id ID accepts other audited cohort ledgers.

## Forecast design

- Decision timestamp: D 09:35 Asia/Shanghai.
- Experience features: only COMPLETED, actually available D-1 and older outcomes.
- Target: D close-to-close limit-up repeat fraction; only known at D close.
- Previous-day activity labels are legal only if published before D 09:35.
- Baseline regressors: prior repeat fraction and log1p(prior-day limit-up count).
- Enhanced regressors: baseline plus lagged simulated B0-cohort 3-session compounded returns.
- Estimation: one-way expanding training window, no shuffling, fixed ridge penalty.
- Minimum training 120 observations, minimum subsequent predictions 40.

Outputs: h01_market_activity.parquet, h01_joined.parquet, h01_predictions.parquet, h01_metrics.json. They quantify forecast errors, not trading profit or statistically proven causation. Report NO_IMPROVEMENT as a genuine negative result.

The 16:00 Shanghai market-observation timestamp is a conservative explicit assumption for finalized daily list observation; it is not a verified third-party data-publication SLA. A forward data feed must confirm operational availability.

## Strict blockers and limitations

- Never fill missing historical days with zero limit-up stocks.
- Do not use today's outcome to generate today's 09:35 signal.
- Do not treat an omitted/unsellable loser as a realized winner.
- Never unlock the previously frozen July-September 2026 blind period for iterative research under the pretense it is untouched.
- H01-A predictive performance does NOT imply the ability to earn an after-cost return.
- Any feature prediction edge requires a second-stage realistic policy simulation and out-of-sample equity/risk comparison against B0 and cash, and later forward validation.

## Project decision

Psychology remains the theoretical foundation. Observable market data are imperfect measurement instruments. Net-equity growth is the objective, but all claims are BLOCKED until there is evidence.

## Added data cross-check (market summary count)

Where the source stores both the closing market-wide summary indicator and historical limit-up list, use the stricter command:

    python -m logic_b.h01_cli --data-root data-xgb --start 2024-09-30 --end 2026-06-30 --audit-market-summary --out runs/h01-a-audited

The command writes h01_source_count_audit.parquet and h01_source_count_audit.json. If the vendor's closing count differs from the fetched list, the result is BLOCKED, not silently labeled complete. **The two endpoints come from the same vendor**: agreement is an internal consistency check, not independent population confirmation. Source-specific definitions may differ; investigate and document disagreements before enabling H01 inference.

## Market-level experience proxy (does not need executable cohort equity)

A psychologically closer but **non-tradable** observable is the vendor's end-of-day `yesterday_limit_up_avg_pcp`: it describes average performance of the prior day's limit-up basket; it is NOT the realized return of accounts or an executable investable strategy. The original vendor units are preserved. An arithmetic mean of previously completed sessions is used, not a fictitious compounded portfolio return.

    python -m logic_b.h01_cli --data-root data-xgb --start 2024-09-30 --end 2026-06-30 --vendor-market-experience --audit-market-summary --out runs/h01-a-market

Baseline: prior repeat rate and limit-up count. Enhanced: plus lagged 3-day mean prior-day-limit-up-basket performance at the vendor's close. Model time-gating remains 09:35; the current day's basket performance is forbidden as a current-day feature.

This pathway directly tests the market-observable **reward history** premise before attempting the stronger and costlier claim of actual investor imitation. An accuracy gain DOES NOT establish either imitation causality or net-profitability. The separately cost-accounted B0-follower ledger remains an independent alternative experience proxy.
