# Attempt 09 — Rare-gene probe result

**Date**: 2026-06-09
**Status**: **Definitive negative finding** — attempt 07 does not transfer
to test-condition data. Combined AUROC drops from 0.623 (eval60) to 0.466
(rare-gene probe). Below random.

## Headline

On 60 train rows where the readout gene appears 2-4× in train (mimicking
test's double-disjoint structure on the gene axis), DeepSeek-Reasoner with
attempt 07's single-call prompt:

| Metric | eval60 (popular genes, leakage) | **probe60 (rare genes, test-like)** | Δ |
|---|---|---|---|
| DE-AUROC | 0.601 | **0.449** | -0.152 |
| DIR-AUROC | 0.645 | **0.482** | -0.163 |
| **Combined** | **0.623** | **0.466** | **-0.157** |

Combined of **0.466 is below random (0.500)**. Attempt 07 is **actively
mis-ranking** these rows.

## Baselines on the same probe60

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| Random | 0.5 | 0.5 | 0.5 |
| Gene-only baseline (cheats via same-gene neighbors) | 0.117 | 0.623 | 0.370 |
| Pert-only baseline (cheats via same-pert neighbors) | 0.143 | 0.766 | 0.455 |
| **Attempt 07** | 0.449 | 0.482 | **0.466** |

Pert-only baseline (Combined 0.455) cheats by looking at other train rows
with the same pert (~19 same-pert neighbors per row). On the actual test
set, pert is also unseen → pert-only collapses to 0.5. Same for gene-only.

**Attempt 07 ≈ pert-only baseline** (0.466 vs 0.455), but pert-only's
signal source (same-pert train neighbors) doesn't exist on test. So
attempt 07's predicted test Combined is closer to 0.466, and possibly
worse on the all-genes-unseen-pert-unseen subset.

## Interpretation

The audit of eval60 already showed attempt 07's DIR collapsed from 0.741
(high gene-prior) to 0.438 (low gene-prior). The rare-gene probe confirms
this generalises:

> When the prompt's signals (KG retrieval, Replogle ortholog, BMDM
> context, LLM pretraining) don't fire, attempt 07 produces noise.

Looking at the per-row P_DE distribution: ~50 rows are P_DE ∈ [15, 25];
~50 rows are P_up ∈ [45, 60]. The LLM defaults to a narrow band around
the conservative anchor and rarely commits to a confident prediction
when the gene is obscure (Riken IDs, lncRNAs without orthologs).

This is the failure mode GPT's 2026-06-09 discussion §1.5 predicted:
**plausibility is not prediction**. Without rich biological signal per
gene, the LLM can't actually rank.

## Implication for the previous attempts

All previous attempts (A03 / A04 / A05 / A06 / A07) measured eval60
leakage, not real signal. The 0.014 Combined gap between A04 / A05 / A07
was **completely** inside the leakage band. The user's instinct
("不要关注这个小的gap了，这是之前误打误撞的") was right.

## What this means for Track A

Submitting attempt 07 as-is is expected to score **≈ 0.47-0.50 on the
public LB** — basically random, possibly worse than a uniform-prior
baseline. We need a paradigm change before any GPT-OSS-120B spend.

## Three honest next moves

1. **Cross-check on A04 / A05 prompts** (cheap, ~$0.30, 5 min):
   verify they are also ≈ 0.47-0.50 on probe60 — if any of them is
   noticeably higher we've found the "real" workhorse to revive.
2. **Two-tier prediction** (cheap, ~30 min code, 0 API):
   - Tier A (high-info rows): use attempt-07 LLM when gene has KG
     neighbors / Replogle ortholog / known function description.
     Expected AUROC > 0.5.
   - Tier B (low-info rows): output the *training prior* (P_DE = base
     rate of `none` ≈ 0.45; P_up = 0.62 from train up:down ratio) with
     small jitter from row-level deterministic hash so AUROCs don't tie.
     Expected AUROC ≈ 0.5.
   - Tier A's lift on its subset + Tier B's 0.5 floor can beat the
     attempt-07-only 0.466 baseline.
3. **Pivot to the GPT discussion's paradigm A** (CORE-style same-readout
   contrastive evidence + signed pathway features). Bigger lift but real
   work; requires KG signed edges + functional gene category embeddings
   that we don't have today.

## Inputs / outputs

- Input probe: `scripts/eval_metric_v4.py:pick_rare_gene(60, seed=789)` —
  60 train rows where gene_count ∈ [2, 4], stratified 23 up / 12 down /
  25 none for apples-to-apples with eval60.
- Outputs:
  - `attempts/09_rare_gene_probe/outputs/probe60/single/{id}.json` — 60 LLM responses
  - `attempts/09_rare_gene_probe/outputs/probe60_log.txt` — eval log
  - `attempts/09_rare_gene_probe/audit_baselines.json` — gene/pert baselines
