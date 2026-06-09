# Attempt 09 — Rare-gene probe (test-like validation)

## Why

The 2026-06-09 audit showed `eval60` had gene-prior leakage: rows had
median 4-10 same-gene neighbors in train, and attempt-07 DIR-AUROC was
correlated with that neighbor count (0.741 on high-gene-prior rows,
0.438 on low). Test set is double-disjoint (zero same-gene neighbors),
so eval60 numbers are not faithful to expected test performance.

Strict double-disjoint inside train is **impossible**: every train pert
appears at least 17 times, and all 632 rows where the gene appears
exactly once are labeled `none` (no positives for AUROC).

The next-best probe: sample 60 rows where the gene appears 2-4 times in
train (so retrieval excludes 1-3 same-gene rows, much closer to test's
zero) with mixed labels for AUROC. This is a test-mimic on the GENE axis,
which is the axis that drives DIR-AUROC contamination.

## Probe design

- Source: `data/train.csv` filtered to rows where `gene_count_in_train ∈ [2, 4]`
  (1491 candidate rows, 518 up / 154 down / 819 none)
- Stratified sample: 23 up / 12 down / 25 none (matches eval60 label
  distribution for apples-to-apples comparison)
- Sampling seed: `789` (different from eval60's `123` to avoid memorization)
- Each row has median 2 same-gene neighbors after `exclude_query=True`
- Each row has median 19 same-pert neighbors (test set is also pert-disjoint,
  but pert leakage didn't dominate DIR contamination in the audit)

## What we'll measure

Run attempt 07 prompts (`pipeline/prompt_builder_v3.py`) on the probe.
Compare to:

- attempt 07's eval60 numbers (DE=0.601, DIR=0.645, Combined=0.623)
- gene-only / pert-only baselines on the probe

## Interpretation guide

| Outcome | Verdict |
|---|---|
| Probe Combined ≥ 0.60 AND DIR ≥ 0.55 | attempt 07 transfers; ship for Track A |
| Probe Combined ∈ [0.50, 0.59] | DIR collapses but DE survives; consider DIR-only intervention |
| Probe Combined < 0.50 | attempt 07 was riding eval60 leakage; pivot needed before any GPT spend |

## Inputs / outputs

- Inputs: `data/train.csv`, `data/replogle_de.pkl`, `data/kg_index/`,
  `data/gene_desc.json`, `pipeline/prompt_builder_v3.py`
- Outputs:
  - `attempts/09_rare_gene_probe/outputs/probe60/single/{id}.json` — 60 LLM responses
  - `attempts/09_rare_gene_probe/outputs/probe60_log.txt` — eval log
  - `attempts/09_rare_gene_probe/audit_baselines.json` — gene-only / pert-only on the same probe
  - `attempts/09_rare_gene_probe/result.md` — final verdict
