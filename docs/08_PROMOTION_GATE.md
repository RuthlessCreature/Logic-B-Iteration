# Promotion Gate

## Purpose

`promotion-check` determines whether an experiment may become a new named
Logic-B version.

It is deliberately non-compensating.

The gate does not calculate a weighted score where one exceptional metric can
cancel a structural weakness.

## Required evidence

### Conservative-fill metrics

Usually:

```text
runs/<baseline-conservative>/metrics.json
```

Required fields include:

- `closed_trades`;
- `expectancy`;
- `max_drawdown`.

### Walk-forward summary

Usually:

```text
runs/walk_forward_<...>/summary.json
```

Required fields include:

- `folds`;
- `positive_return_fold_rate`;
- `positive_expectancy_fold_rate`;
- `closed_trades`.

### B0-H alignment metrics

Generate:

```bash
logic-b align-b0 \
  --human research/human_labels.csv \
  --proxy runs/<run>/signals.parquet \
  --out runs/<run>/human_alignment.csv \
  --metrics-out runs/<run>/human_alignment_metrics.json
```

### Parameter-neighborhood study

Expected JSON shape:

```json
{
  "stable": true,
  "tested_neighbors": 12,
  "notes": "No sign reversal around the frozen parameter point."
}
```

### Candidate complexity metadata

Expected JSON shape:

```json
{
  "candidate_version": "B1.0.0",
  "primary_rule_changes": 1,
  "new_free_parameters": 1,
  "hypothesis": "Example hypothesis"
}
```

## Run the gate

```bash
logic-b promotion-check \
  --conservative runs/<conservative>/metrics.json \
  --walk-forward runs/<walkforward>/summary.json \
  --alignment runs/<run>/human_alignment_metrics.json \
  --stability research/experiments/<id>/neighborhood.json \
  --candidate-meta research/experiments/<id>/candidate_meta.json \
  --out research/experiments/<id>/promotion.json
```

Exit code:

- 0: PASS;
- 2: FAIL or BLOCKED.

## PASS / FAIL / BLOCKED

### PASS

All required gates have sufficient evidence and meet their frozen threshold.

### FAIL

At least one completed gate violates a hard requirement.

Examples:

- conservative expectancy is not positive;
- drawdown exceeds the maximum;
- walk-forward stability is too weak;
- complexity exceeds the version budget.

### BLOCKED

A required evidence package is missing or non-finite.

Examples:

- too few human labels;
- no parameter-neighborhood study;
- expectancy cannot be calculated because there are no closed trades.

BLOCKED is intentionally different from FAIL.

It means the research claim is not yet sufficiently tested.

## Governance

Thresholds are frozen in:

```text
config/b0.yaml
```

Decision record:

```text
research/decisions/20260928-promotion-thresholds.md
```

Thresholds must not be moved after inspecting the corresponding evaluation
results merely to obtain a PASS.
