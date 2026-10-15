# Luna Goal live checkpoint — 2025 TRAIN / 2026H1 VALIDATION

**Active instruction:** [2025→2026H1 hard Goal](../docs/LUNA_GOAL_2025_TRAIN_2026_VALIDATE.md) · [Full Luna prompt](../docs/LUNA_GOAL_PROMPT_2025_2026.md). This file deliberately contains NO obsolete 2020-start runbook.

## Fixed contract

| Field | Current value |
|---|---|
| TRAIN | **2025-01-01..2025-12-31** |
| VALIDATION | **2026-01-01..2026-06-30** (after training freeze) |
| Active config | `config/goal_2025_2026.json` |
| Old 2020 regression config | `config/research.json`, preserve old CI only |
| Capital / fees | **CNY10000 per train/validation account**, 0.00025 each side, min CNY5 each order, stamp duty+transfer separately |
| Constraints | A-share T+1, one position, 100-share buys, limit-up no buy, limit-down no sell, cash valid, stock exchange+6-digit stable through ST/name |
| Historical protection | NEVER access 2026-07-01..2026-09-28 |
| Model responsibilities | Codex **offline research**; DeepSeek/Jev **future daily runtime only**, currently DISABLED |
| Cloudflare | R2/D1 **NOT CONNECTED** — no persistence or storage bytes available via account |
| Live trading | NO brokerage order permission |

## Verified implementation as of 2026-10-15

- `src/logic_b/goal.py` produces `dashboard.html`, `training_equity.svg/csv`, `validation_equity.svg/csv`, `iteration_history.json/csv`, `frozen_selection.json`, `goal_report.json`, `storage_inventory.json` from a ready dataset; records *actual* local file bytes and R2 null if disconnected.
- `src/logic_b/replay.py` + `research.py` support locked **2025 train / 2026H1 validation** while old2020 version remains available only as regression.
- Smoke dataset: `examples/goal_toy_2025_2026.json` is **synthetic** and not real market prices. [Goal demo #38709918043](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38709918043) attached the synthetic dashboard. Last verified test [#38710991077](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38710991077) **71 passed**.
- H01/H02 old files remain in `legacy/2026-10-15-pre-reset/`. Former 2020 research pilot is not an active train sample. `docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md` retains the psych/LogicA reference.
- **Not yet achieved:** actual entire 2025+2026H1 verified source coverage, real historical full-range equities, month-by-month source byte/record dashboard, corporate action completeness, real persistent R2 storage, deployed DeepSeek/Jev inference. Do not claim these are complete.

## Next actual work for Luna

1. Inspect latest GitHub HEAD and CI; run demo/tests.
2. Complete 2025 train + 2026H1 market source downloads with partition recovery, fixing BaoStock 10002007, local byte and row count manifests.
3. Improve long-term cache storage abstraction (R2 only with user-provided credentials); compute real by-month data footprint and growth curves.
4. Complete 1万元 fee-accurate streaming replay; 2025 V0 baseline and psych regime V1 trials, log every iteration and training chart.
5. Freeze 2025-selected version BEFORE opening 2026H1 validation, compare to V0 and report risks. No retro-selection.
6. Upload public **aggregate-only** dashboard/CSV/SVG/JSON to GitHub Actions and link to committed summary; no source raw rows, no false R2 data claims.

**Every future Luna execution must rewrite this checkpoint with true SHA/Actions/data hashes/real bytes/coverage, current strategy version, hypothesis outcomes and blockers; do not fabricate.**
