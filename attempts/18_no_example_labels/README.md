# Attempt 18 (Test α) — Remove example labels

## Why

User's intuition: do example labels (Yes/No on each retrieval case)
actually drive LLM output, or is the structural existence of the
examples enough? If labels carry no signal, we could simplify the
prompt and avoid vote-bias concerns entirely.

## Method

`pipeline/retrieve_examples.py:format_block_no_labels` — same 10 analog
+ contrast pairs retrieved, but render each as just `pert=X, target=Y`
(no Result line).

## Result on probe60 (seed=789)

| Metric | A12 SHIP (with labels) | A18 (no labels) | Δ |
|---|---|---|---|
| DE-AUROC | 0.644 | 0.606 | -0.038 |
| DIR-AUROC (LLM-only) | 0.540 | 0.513 | -0.027 |
| Combined (LLM-only) | 0.592 | 0.559 | -0.033 |
| **Combined (+ hybrid)** | **0.643** | 0.622 | -0.021 |

Distribution barely shifted:
- P_DE mean: 0.241 → 0.215 (slightly more conservative)
- P_DE=20 cluster: 22 → 20 rows (similar)
- Top-5 P_DE: now (15, 27), (20, 20), (30, 4), (5, 4), (95, 2)
  — 8 rows moved from P_DE=20 to P_DE=15

## Verdict

Labels DO carry information (~0.038 DE-AUROC worth) but they're NOT the
dominant signal. The conservative bias in LLM output (mean P_DE = 0.24
vs train base rate 0.45) is NOT explained by example labels — it
persists even without labels.

Removing labels is a small loss, not catastrophic. The LLM still uses
the structural existence of the examples as a frame for reasoning.

## Inputs / outputs

- `pipeline/retrieve_examples.py:format_block_no_labels` (new)
- `pipeline/prompt_builder_v3.py`: added `hide_example_labels: bool = False` flag
- `scripts/eval_metric_v4.py`: added `--hide-example-labels` opt-in
- `attempts/18_no_example_labels/outputs/probe60_log.txt`
- `attempts/18_no_example_labels/prompts/example_Tlr4_Cd14.txt`
