# H02 Final Research Reproduction

All commands run from the repository root on branch `research/behavioral-edge-20261013`. The approved five archives are licensed/local inputs and must remain outside Git. This run used the five existing SHA-pinned `h01-raw-*.zip` archives; their hashes and all verified manifest totals are recorded in `features.json`.

## Environment

- Python 3.13 in the local test environment; project dependencies from `pyproject.toml` and `.[dev]` installed.
- `pytest` full suite; `numpy`, `pandas`, `pyarrow`, PyYAML and Tushare client package.
- No provider call is required to reproduce these outputs if the five approved archives are available.
- `TUSHARE_TOKEN` was not present in the local environment. No token value was read or printed. Official-price permission probe and real-data execution remain blocked.

## Rebuild data-derived files

```powershell
python scripts/h02_final_stock_features.py `
  --artifacts <h01-raw-2024h1.zip> <h01-raw-2024h2.zip> <h01-raw-2025h1.zip> <h01-raw-2025h2.zip> <h01-raw-2026dev.zip> `
  --out-json research/experiments/h02-final-research/features.json `
  --out-markdown research/experiments/h02-final-research/features.md `
  --matrix-out runs/h02-final-research/feature-matrix.csv

python scripts/h02_final_stock_forecast.py `
  --matrix runs/h02-final-research/feature-matrix.csv `
  --out-json research/experiments/h02-final-research/forecast.json `
  --out-markdown research/experiments/h02-final-research/forecast.md

python scripts/h02_final_strategy_research.py `
  --matrix runs/h02-final-research/feature-matrix.csv `
  --out-json research/experiments/h02-final-research/strategy-comparison.json `
  --out-markdown research/experiments/h02-final-research/strategy-comparison.md

python scripts/h02_synthetic_execution_ledger.py `
  --out-json research/experiments/h02-final-research/synthetic-execution-ledger.json `
  --out-markdown research/experiments/h02-final-research/synthetic-execution-ledger.md
```

The OOF policy fit starts after the first 60 training sessions, forecasts five-session blocks, expands the training window and purges the latest two sessions to prevent Y3 overlap. All feature preprocessing, models, risk thresholds, and policy rules use training dates only. Validation (2025H2) and forward development (2026H1) remain exposed.

## Verification

```powershell
python -m pytest -q
```

The output artifacts contain archive and normalized-matrix SHA256 values, split/coverage counts, fixed seeds, model definitions, candidate-weighted bootstrap intervals, threshold provenance, policies and execution scenario ledgers. They contain no row-level market matrix; that file remains ignored local output.
