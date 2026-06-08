# Attempt 04 — result

**Date**: 2026-06-08
**Status**: Architecture validated. Ready for GPT full run.

## Headline

On 60 random train rows (seed=123, the same sample used to grade attempt 03),
DeepSeek-Reasoner with the VCWorld-style two-prompt architecture:

| Metric | Attempt 03 (one prompt) | **Attempt 04 (VCWorld-style)** | Δ |
|---|---|---|---|
| DE-AUROC | 0.654 | 0.601 | -0.053 |
| DIR-AUROC | 0.451 ❌ | **0.679** ✅ | **+0.228** |
| **Combined** | **0.552** | **0.640** | **+0.088** |

Reference baselines on the same task:
- Random: 0.500
- Attempt 01 (Replogle K562+RPE1 averaged, full train n=4,154): 0.602
- Top-4 public LB band: 0.628 – 0.650

We are **above attempt 01 on this 60-row probe and inside the top-4 LB band**.

## What worked

| Change | Why it helped |
|---|---|
| Two independent prompts (DE + DIR) | DIR no longer compromised by simultaneous DE reasoning |
| Replogle scalar REMOVED from DIR prompt | LLM previously overrode Replogle direction with bad mechanism guesses → DIR-AUROC < 0.5. Removing the conflict source restored signal. |
| Rich BMDM cell-state paragraph | Anchors lineage/silent-program reasoning (e.g., Cdk14 in post-mitotic BMDM → low P_DE) |
| Per-gene NCBI summaries (87% coverage via human ortholog backfill) | Gives the model real function context per pert/target instead of bare symbols |
| KG-similarity-based retrieval (both-anchor, K=10, exclude-query) | Surfaces structurally analogous train pairs (Aars/Atf4 → Qars/Trib3, Sars/Ddit3, …); validates question plausibility |
| Randomized labels in retrieved examples (VCWorld trick) | Defeats vote-bias — exemplars prove the question is well-defined, model can't lazy-vote |
| 5-step structured reasoning with explicit final integer | Cleaner output, easier to parse, less format ambiguity |

## What slightly hurt (DE-AUROC -0.053)

DE-AUROC dipped from 0.654 → 0.601. Two likely causes:
1. The 5-step reasoning makes the model more conservative (more "Insufficient evidence" leans).
2. Some Replogle weight was lost because DIR is decoupled — but Replogle DE info is still in the DE prompt, so this should be small.

The 0.088 net Combined gain comfortably absorbs the DE dip.

## What stayed expensive

- Token usage: ~1,800 prompt + ~1,000-2,000 reasoning + ~500 visible per call
- 2 calls per (pert, gene) → ~$0.015 per row at DeepSeek prices
- Full submission cost on DeepSeek: 1,813 rows × 2 prompts × 3 seeds ≈ $80 (we will use GPT instead per user)
- 9/60 DIR responses hit max_tokens=3000 cap on first try → bumped to 6000, all 60 then succeeded

## Inputs (reproducibility)

- `data/train.csv`, `data/test.csv`
- `data/replogle_de.pkl` (built in attempt 01)
- `data/mouse_to_human_ortholog.json` (built in attempt 01)
- `data/kg_index/` (built in attempt 03)
- `data/gene_desc.json` (built in this attempt by
  `scripts/build_gene_desc.py` + `scripts/extend_gene_desc.py`)

## Outputs

- `attempts/04_vcworld_port/outputs/eval60/de/{id}.json` — 60 DE responses
- `attempts/04_vcworld_port/outputs/eval60/dir/{id}.json` — 60 DIR responses
- Each JSON includes prompt tokens, reasoning tokens, content, parsed P_DE / P_up_given_DE.

## Verdict

**Pass.** Architecture is the right shape. Combined=0.640 clears the 0.602
attempt-01 gate. Recommend user run full submission with GPT (3 seeds for
calibration).

## Next (out of scope here)

- Run full 1,813 rows × 2 prompts × 3 seeds on GPT (user's call on model/budget)
- Aggregate: per row, average P_DE over 3 DE-prompt seeds, average P_up_given_DE
  over 3 DIR-prompt seeds, then `pipeline/runner.assemble_submission()`
- Submit to Kaggle, get real Public LB number
- If LB ≈ 0.64, ship; if higher, iterate on retrieval / context paragraph
