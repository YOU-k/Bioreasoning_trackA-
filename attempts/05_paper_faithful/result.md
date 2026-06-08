# Attempt 05 — result

**Date**: 2026-06-08
**Status**: eval complete. **Tie with attempt 04** on the 60-row probe.

## Headline

On the same 60 random train rows (seed=123) used to grade attempts 03 / 04,
DeepSeek-Reasoner with paper-faithful analog+contrast retrieval (real labels):

| Metric | Attempt 03 (one prompt) | Attempt 04 (random labels) | **Attempt 05 (paper-faithful)** | Δ vs 04 |
|---|---|---|---|---|
| DE-AUROC | 0.654 | 0.601 | **0.610** | +0.009 |
| DIR-AUROC | 0.451 | **0.679** | 0.665 | -0.014 |
| **Combined** | **0.552** | **0.640** | **0.637** | **-0.003** |

`n_pos / n_neg` for DE: 35 / 25. For DIR: 23 / 12 (subset where true label ∈ {up, down}).
All 60 rows parsed; 360s wall-clock at concurrency=8.

## Verdict — Tie (per pre-registered gate)

- Gate said: Pass if Combined > 0.640, Tie if ∈ [0.60, 0.64], Fail if < 0.60.
- Result: 0.637, within the tie band.
- DE-AUROC moved up slightly (+0.009) — paper-faithful labels arguably let
  the model use real evidence on the DE call.
- DIR-AUROC moved down slightly (-0.014) — within sampling noise on 35
  positive rows.
- Combined difference (-0.003) is well within 60-row noise.

## What we now know

Attempt 04's "VCWorld randomized labels" story was the **wrong attribution**
for why the DIR-AUROC jumped from 0.451 → 0.679. The real ingredients were:

1. **Two independent prompts** (DE and DIR), so DIR isn't forced to co-emit DE
2. **Removing the Replogle scalar from the DIR prompt** (was the main culprit
   in attempt 03 — the LLM kept overriding it with bad mechanism guesses)
3. **Rich BMDM cell-state paragraph** (lineage-aware reasoning)
4. **Per-gene NCBI summaries** (real function context per pert/target)
5. **KG-similarity retrieval** (5 analog + 5 contrast surfaces analogous cases)

Items 1-5 are present in both attempts 04 and 05. The **only** thing that
changed in attempt 05 is **how the labels are rendered**: real vs random.
That change moved the metric by 0.003 — i.e., not the active ingredient.

## Recommendation for full GPT run

Use **attempt 05 prompts** (paper-faithful). Reasons:

- Same score within noise on this probe
- Conceptually cleaner / matches the published method
- Preserves real-label signal that *could* help on larger / different data
- Single source of truth for "what we'd cite as our method"

If GPT shows materially different behavior, run a one-row sanity check
comparing both prompt styles before committing the full $80 GPT spend.

## Inputs (reproducibility)

- `data/train.csv`, `data/test.csv`
- `data/replogle_de.pkl`
- `data/mouse_to_human_ortholog.json`
- `data/kg_index/`
- `data/gene_desc.json`
- `pipeline/prompt_builder_v2.py` (rewritten to use analog+contrast)
- `pipeline/retrieve_examples.py` (new: `retrieve_analog_contrast`, `format_block_analog_contrast`)
- `scripts/eval_metric_v3.py`

## Outputs

- `attempts/05_paper_faithful/outputs/eval60/de/{id}.json` — 60 DE responses
- `attempts/05_paper_faithful/outputs/eval60/dir/{id}.json` — 60 DIR responses
- `attempts/05_paper_faithful/outputs/eval60_log.txt` — eval log with metric
- `attempts/05_paper_faithful/prompts/example_Aars_Atf4_{DE,DIR}.txt` — dry-run reference
