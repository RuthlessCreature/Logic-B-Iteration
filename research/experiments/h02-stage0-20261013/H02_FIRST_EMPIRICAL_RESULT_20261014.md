# H02 FIRST EMPIRICAL RESULT — TIER D, NOT TRADING PERFORMANCE

Scope: 2024-09-30 through 2026-06-30. These are same-vendor event-pool membership observations, not strategy signals, trade outcomes, or investor-psychology evidence.

## Three observed statistics

- **Next-session limit-up-pool continuation:** 9,371 / 36,775 = 25.4820% (pooled symbol-day rate). Daily mean 25.4440%; daily median 24.1758%.
- **Next-session limit-down-pool event:** 1,230 / 36,775 = 3.3447% (pooled symbol-day rate). Daily mean 3.4213%; daily median 2.1978%.
- **Limit-down-pool event within next three trading sessions:** 4,801 / 36,580 = 13.1247% (pooled symbol-day rate). Daily mean 13.2067%; daily median 10.6667%.

The three-day risk denominator includes only outcome days with all three subsequent sessions inside the development cutoff. Duplicated symbol-days across dates are not independent observations.

## Annual and half-year splits

| Period | Outcome days | Prior-pool symbol-days | Next-day up-pool | Next-day down-pool | 3-session down-pool |
|---|---:|---:|---:|---:|---:|
| 2024 | 62 | 8,619 | 2,703/8,619 (31.36%) | 382/8,619 (4.43%) | 1,558/8,619 (18.08%) |
| 2025 | 243 | 18,125 | 4,563/18,125 (25.18%) | 548/18,125 (3.02%) | 2,187/18,125 (12.07%) |
| 2026 | 116 | 10,031 | 2,105/10,031 (20.98%) | 300/10,031 (2.99%) | 1,056/9,836 (10.74%) |
| **Half-year** | | | | | |
| 2024H2 | 62 | 8,619 | 2,703/8,619 (31.36%) | 382/8,619 (4.43%) | 1,558/8,619 (18.08%) |
| 2025H1 | 117 | 9,110 | 2,323/9,110 (25.50%) | 292/9,110 (3.21%) | 1,191/9,110 (13.07%) |
| 2025H2 | 126 | 9,015 | 2,240/9,015 (24.85%) | 256/9,015 (2.84%) | 996/9,015 (11.05%) |
| 2026H1 | 116 | 10,031 | 2,105/10,031 (20.98%) | 300/10,031 (2.99%) | 1,056/9,836 (10.74%) |

Unweighted daily rates (mean / median, by outcome day):

| Period | Next-day up pool | Next-day down pool | D..D+2 down pool |
|---|---:|---:|---:|
| 2024 | 32.36% / 30.83% | 4.37% / 2.53% | 18.55% / 13.33% |
| 2025 | 25.69% / 25.00% | 3.29% / 2.47% | 12.86% / 9.71% |
| 2026 | 21.24% / 19.58% | 3.19% / 2.04% | 11.04% / 9.53% |
| 2024H2 | 32.36% / 30.83% | 4.37% / 2.53% | 18.55% / 13.33% |
| 2025H1 | 26.35% / 25.56% | 3.55% / 2.67% | 14.56% / 11.25% |
| 2025H2 | 25.07% / 24.76% | 3.04% / 1.82% | 11.28% / 9.52% |
| 2026H1 | 21.24% / 19.58% | 3.19% / 2.04% | 11.04% / 9.53% |
| Overall | 25.44% / 24.18% | 3.42% / 2.20% | 13.21% / 10.67% |

## Provenance, coverage, and interpretation

- Source: [H01 artifact run 38358815302](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38358815302); whole ZIP SHA verified 5/5; selected calendar/limit_up/limit_down manifest hashes verified 1207/1207.
- Coverage: 421/421 requested outcome sessions have a prior candidate pool; 601/601 limit_up and 601/601 limit_down partitions are present.
- The 2024-09-30 observation uses 2024-09-27 only as D-1 context. Three-session risk stops before any window extending past 2026-06-30. No protected holdout data were opened.
- The event calculation crosses 3 half-year archive seams using the verified combined trading calendar. Missing in-scope up/down partitions: 0/0.
- `limit_up` / `limit_down` are Xuangubao provider event pools. The retained project artifact and provider adapter do not establish whether membership means closing at the limit or an intraday event; results therefore remain same-vendor pool transition rates.
- This adds the correct frozen development-range slice, a same-day downside proxy, and a three-session downside proxy to the prior H01 continuation proxy. It does not establish causality or strategy edge.
- No inferential confidence interval is reported: this is a descriptive census of archived vendor observations, with repeated securities across days and no independence assumption.
- Tier E remains BLOCKED by absent official per-stock limits, PIT status/timestamps, execution-time semantics, verified fills, and unresolved source license/availability terms. No B0 signal, win rate, returns, or equity curve were evaluated.

## Whole archive SHA256

- `h01-raw-2024h1.zip`: `1abfc7022075958537e635b107c0919a68122dc0ff6b7a97cec6132f9ab6fec8`
- `h01-raw-2024h2.zip`: `ddd770f7f0dc1322c2d782ae1925d43df302570277c0b53af0bde8bef674c1ad`
- `h01-raw-2025h1.zip`: `cb9bca81e71fa42ed85659564e5a6a7f446f25cbfc1bc7005d734529dbdc0c67`
- `h01-raw-2025h2.zip`: `8c4a9c90acfc9b7e841a453b127b2dcfb6dcc68e43566ca9f5838d1dcbcb0144`
- `h01-raw-2026dev.zip`: `7da9da754fb7d976b03a371666fd9d27fec0fcaf4f4f784dbecae01e978e857c`

Daily aggregate counts and partition SHA256 references are in the companion JSON. No symbol-level rows are included.

## Reproduction and engineering evidence

The command below reads only the five named development archives. Each complete ZIP is checked against the embedded allowlist before any ZIP member is opened; the script then verifies selected raw partition SHA256 values and manifest row counts before calculating results.

```powershell
$ArtifactDir = "$env:TEMP\h02-fastcheck-artifacts-20261014"
python scripts/h02_first_empirical_result.py `
  --artifacts `
    "$ArtifactDir\h01-raw-2024h1.zip" `
    "$ArtifactDir\h01-raw-2024h2.zip" `
    "$ArtifactDir\h01-raw-2025h1.zip" `
    "$ArtifactDir\h01-raw-2025h2.zip" `
    "$ArtifactDir\h01-raw-2026dev.zip" `
  --json research/experiments/h02-stage0-20261013/H02_FIRST_EMPIRICAL_RESULT_20261014.json `
  --markdown research/experiments/h02-stage0-20261013/H02_FIRST_EMPIRICAL_RESULT_20261014.md
```

The pinned source run and archive SHA256 values are listed above and in the JSON. Do not use the `2026observed` artifact.

