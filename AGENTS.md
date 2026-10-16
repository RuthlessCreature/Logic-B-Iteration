# Logic-B · LUNA GOAL ACTIVE CONTRACT — 2026-10-15

**READ IN ORDER (these files control, no independent guessing):**
1. [docs/LUNA_GOAL_2025_TRAIN_2026_VALIDATE.md](docs/LUNA_GOAL_2025_TRAIN_2026_VALIDATE.md)
2. [docs/LUNA_GOAL_PROMPT_2025_2026.md](docs/LUNA_GOAL_PROMPT_2025_2026.md)
3. [research/GOAL_CHECKPOINT.md](research/GOAL_CHECKPOINT.md)
4. [docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md](docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md) for participant psychology, Logic A and MarketState
5. [docs/RESEARCH_VS_RUNTIME_ARCHITECTURE.md](docs/RESEARCH_VS_RUNTIME_ARCHITECTURE.md) for Codex offline research versus future DeepSeek/Jev runtime

## ONLY active market-data research time split

- **TRAIN 2025-01-01 through 2025-12-31 inclusive.**
- **VALIDATION 2026-01-01 through 2026-06-30 inclusive.**
- TRAIN: fit/iterate/select models using **2025 only**.
- VALIDATION: open **once after** training-selected strategy version freezes; 2026H1 is *development validation*, not untouched blind OOS. Do not select by validation returns.
- Old 2020-2024 experiments and previous 2020-based instructions are **historical references only** (under `legacy/` or Git history). Never pull them into this Goal's active training/evaluation.
- **Protected 2026-07-01..2026-09-28: never open, query, download, visualize or train on.**
- `config/goal_2025_2026.json` is the **ACTIVE config**. `config/research.json` is legacy compatibility for previous CI/regression tests, not the Goal config.

## The outcomes user must SEE and AUDIT

1. **Actual storage:** by source/type/year/month, row counts, trading days, file count, bytes, MiB/GiB, CSV+SVG storage-growth curve; local physical bytes versus R2 actual bytes as independent quantities. R2 and D1 are currently **NOT CONNECTED**, not permanently storing data. No fake size or invented Cloudflare cost. Never publish raw third-party market records in GitHub.
2. **The complete 2025 TRAIN iteration timeline:** V0 baseline and each meaningful psychological/MarketState/LogicA experiment, predeclared hypothesis + changed rule + source/as-of + after-cost account returns, MDD, locked fills, abstain days, KEEP/REJECT, code/data SHA and CI link. SVG/CSV training-equity curves for every version. Preserve negative results.
3. **Only AFTER freeze:** 2026H1 VALIDATION comparing final frozen winner (or NO_CANDIDATE) versus V0 from **separate CNY10000 accounts**; SVG/CSV equity, risk and fees. Do not splice money curves or tune using 2026 validation.
4. **Click-through HTML dashboard** and GitHub Actions aggregate attachments, not empty placeholders. Distinguish synthetic workflow fixture versus actual historical simulations.
5. Honest `NO_FOLLOW` whenever proof, period coverage or execution realism is insufficient. No live broker orders.

## Sources and account invariant

- Xuangubao: actual lagged limit-up/down/broken boards, source-comparable market sentiment/theme data.
- BaoStock: unadjusted daily + historical 5-minute bars, dated ST status and prior price reference. Fix historical `10002007` request failure, cache/retry individual partitions. Do not use D end-of-day evidence at D09:35.
- 10,000 CNY initial capital **per sample window**; CNY5 minimum broker commission each buy and each sell, 0.00025 each side, applicable stamp duty and transfer fees separate; T+1; 100-share buy lots; single position, cash valid; limit-up cannot buy, limit-down cannot sell, suspension/lock must carry position. Stock identity exchange+six digits independent of name/ST. Resolve corporate actions before economic claims.
- A simple consecutive-limit-up proxy is **not** the real complete Logic A. Participant psychology can only be inferred as falsifiable observable proxies, not mind-reading or established causality.

## Agent roles

- **OpenAI Codex:** OFFLINE engineer/researcher who investigates, optimizes, backtests, writes tests, proposes/freeze strategy versions. Never needed as synchronous runtime dependency.
- **DeepSeek:** FUTURE DAILY RUNTIME contextual inference, currently disabled/unconnected/not billed.
- **TypeSafe Jev:** FUTURE DAILY RUNTIME choice/score/noul decision model, currently disabled/unconnected/not billed.
- Deterministic risk/execution gates always retain hard authority. Users must approve any paid API connection, broker integration or actual live orders.

## Execution order, without recurring permission requests

1. Inspect branch latest HEAD + CI, keep PR #1 Draft; do not touch main or force-push. Run pure synthetic `python -m logic_b.goal` dashboard and tests to establish harness (do NOT claim it is historical P&L).
2. Acquire actual 2025 and 2026H1 event/K-line data by recoverable calendar/month partitions. Report real size, missing days and failures; fix BaoStock `10002007`; add permanent storage abstraction (R2 only after credentials and consent).
3. Fix incremental portfolio replay and fees/ex-rights/T+1/price limit/data quality. The 2025 train and 2026 validation equity must come from true source bars with explicit fill assumptions.
4. Implement lagged psych/MarketState V1 then compare V0/V1 and finite subsequent research iterations **inside 2025** with all iterations visible.
5. Select by predeclared train metric, write frozen version manifest, THEN inspect **2026H1** once. Report winner vs V0 regardless of outcome.
6. Publish visible HTML/SVG/CSV, source-size/coverage charts, trading audits, current strategy + version change history + Follow/NO_FOLLOW. Update GitHub checkpoint with SHA, CI, data hash, real coverage and next work.

**NOT DONE:** a green CI, synthetic demo, model endpoint stub, 2020 pilot, Brier score, or nice reasoning prose. **DONE:** the actual bounded research with real data and auditable failures/curves/size, or clearly declared unavailable evidence, never fabricated. Continue independently within existing authorization; no background promises without an actual scheduled service.
