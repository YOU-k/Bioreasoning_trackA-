# Attempt 11 — Hagai mouse-BMDM LPS prior in single-call prompt + runner-side Replogle DIR blend

## Why

Attempt 09 (rare-gene probe) showed attempt 07 collapses on test-condition
data (Combined 0.466). Audit 10 showed ~90% of test rows DO have signal
sources (Replogle, KG, gene descriptions). The bottleneck wasn't signal
availability — it was that our prompt only surfaced **human cross-species**
direction (Replogle K562/RPE1) and the LLM kept overriding it with weak
mechanism guesses.

The dataset survey turned up `/data2/lanxiang/data/Task3_data/Hagai.h5ad`:
mouse BMDM stimulated with LPS for 6h vs control, 15,053 mouse cells.
This is the missing **mouse-native** signal source: per-gene LPS direction
+ magnitude with no ortholog hop required.

Attempt 11 adds Hagai as a primary prior to the prompt AND ships a
runner-side Replogle direction blend.

## Implementation

### 1. Build the Hagai prior (one-time)
- `scripts/build_hagai_prior.py` reads the Hagai h5ad, subsets to mouse,
  computes per-gene CPM-normalized log2(mean_LPS6+1) - log2(mean_ctrl+1)
  + Mann-Whitney U p-value, then Bonferroni-corrected p_adj.
- Output: `data/hagai_lps_prior.json` (6,619 mouse genes).
- Coverage: 44.5% of train genes, **44.0% of test genes**, **53.1% of test perts**.

### 2. Surface Hagai in the prompt
- `pipeline/hagai_prior.py` exposes the lookup table.
- `pipeline/prompt_builder_v3.py` adds a Hagai block between the analog/contrast
  retrieval and the Replogle block. Two lines per query: one for the perturbed
  gene's LPS response, one for the target gene's.
- Updated rules R3 (Hagai magnitude → P_DE prior) and R4 (Replogle direction
  transfer) explicitly.

### 3. Runner-side hybrid direction
- `pipeline/runner.py:hybrid_direction(...)` is the new function used inside
  `assemble_submission()`:

  ```
  if Replogle.tier(pert, gene) == 'full':
      r_replogle = sigmoid(3.0 * Replogle.get_pair_logfc(pert, gene))
      r_final    = 0.4 * r_LLM + 0.6 * r_replogle
  else:
      r_final = 0.62          # train prior up:down ≈ 2.2 : 1
  ```

- `apply_hybrid_direction=True` by default; flip to False for an LLM-only
  ablation.

## Probe60 results (rare-gene, seed=789)

LLM probe (60 calls):

| Metric | A07 (no Hagai, no blend) | **A11 (Hagai prompt, no blend)** | **A11 + hybrid runner** |
|---|---|---|---|
| DE-AUROC | 0.449 | **0.599** | **0.599** |
| DIR-AUROC | 0.482 | 0.480 | **0.627** |
| **Combined** | 0.466 | 0.539 | **0.613** |

Compared to all earlier baselines on the same probe60:

| Predictor | DE | DIR | Combined |
|---|---|---|---|
| Random | 0.500 | 0.500 | 0.500 |
| Pure Hagai+Replogle composite (no LLM) | 0.531 | 0.569 | 0.550 |
| A05 (two-prompt, non-compliant) | 0.595 | 0.509 | 0.552 |
| **A11 + hybrid (this attempt)** | **0.599** | **0.627** | **0.613** |

A11+hybrid is the best Track-A-compliant method on test-condition data.

### Sanity check: hash-jitter on the prior 0.62 boosts further but is unstable

Replacing the constant 0.62 for non-full rows with a hash-based jitter
(r ∈ [0.61, 0.63] per-row) gives Combined 0.59-0.64 depending on the
salt. Mean over 10 salts = 0.616 (negligible lift over 0.613). Not robust;
NOT enabled in the runner default.

### Sanity check: hybrid HURTS on eval60

On eval60 (popular train genes with rich same-gene leakage available),
applying the hybrid on attempt-07 outputs yields Combined 0.516 vs
the leakage-inflated A07-only 0.623. This confirms the hybrid is
specifically the right move on **test-condition** data (no train neighbors),
which is what the actual Kaggle test set looks like.

## Expected Track A LB

Probe60 closely matches test signal-coverage distribution (Tier 0 / Tier 1 / Tier 3
share = 54% / 35% / 8% on probe60 vs 54% / 37% / 9% on test). So
**expected test Combined ≈ 0.55-0.61 with A11 prompt + hybrid runner**.

Top-4 public LB band is 0.628-0.650. We are within ~0.02-0.07 of the band
on a Track-A-compliant single-call architecture for the first time.

## Inputs

- `data/{train,test}.csv`, `data/replogle_de.pkl`, `data/mouse_to_human_ortholog.json`
- `data/kg_index/`, `data/gene_desc.json`
- **new**: `data/hagai_lps_prior.json` (from `scripts/build_hagai_prior.py`)
- Source: `/data2/lanxiang/data/Task3_data/Hagai.h5ad` (mouse subset)
- `pipeline/prompt_builder_v3.py` (Hagai block added, R3/R4 rewritten)
- `pipeline/hagai_prior.py` (new loader module)
- `pipeline/runner.py` (`hybrid_direction()` + integration in `assemble_submission`)
- `scripts/eval_metric_v4.py`

## Outputs

- `attempts/11_hagai_in_prompt/outputs/probe60/single/{id}.json` — 60 LLM responses
- `attempts/11_hagai_in_prompt/outputs/probe60_log.txt` — raw eval log
- `attempts/11_hagai_in_prompt/outputs/blend_ablation.txt` — alpha sweep
- `attempts/11_hagai_in_prompt/prompts/example_*.txt` — 3 dry-run prompts
- `attempts/11_hagai_in_prompt/result.md` — final numbers + verdict
