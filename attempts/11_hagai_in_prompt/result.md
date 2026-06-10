# Attempt 11 — result

**Date**: 2026-06-09
**Status**: **Best Track-A-compliant method on test-condition data**.
Combined 0.613 on probe60_rare_gene with single-call LLM + runner-side
hybrid direction.

## Headline

| Metric | Pure A07 | Hagai+Replogle composite (no LLM) | **A11 prompt + hybrid runner** |
|---|---|---|---|
| DE-AUROC | 0.449 | 0.531 | **0.599** |
| DIR-AUROC | 0.482 | 0.569 | **0.627** |
| **Combined** | **0.466** | **0.550** | **0.613** |

+0.147 Combined over the previous A07 best on test-condition data.

The Hagai LPS prior in the prompt fixes DE (0.449 → 0.599), and the
runner-side Replogle direction blend fixes DIR (0.480 → 0.627). Both
levers are necessary; either alone underperforms.

## Ablations on probe60

### Effect of the Hagai prompt block (LLM alone, no runner blend)

| | DE | DIR | Combined |
|---|---|---|---|
| A07 prompt (no Hagai)        | 0.449 | 0.482 | 0.466 |
| **A11 prompt (with Hagai)**  | **0.599** | 0.480 | **0.539** |

Adding Hagai to the prompt gives **+0.150 DE-AUROC** with no change in DIR.
The mouse-native magnitude signal is what was missing.

### Effect of the runner-side direction blend on top of A11

Non-full strategy with `r_full = 0.4 × r_LLM + 0.6 × sigmoid(3 × Replogle.logfc)` fixed:

| Non-full r strategy on probe60 | DE | DIR | Combined |
|---|---|---|---|
| LLM r (no override)            | 0.599 | 0.507 | 0.553 |
| Hagai LPS sign                 | 0.599 | 0.589 | 0.594 |
| **r = 0.62 (train prior)** ✅  | **0.599** | **0.627** | **0.613** |
| Hash jitter (10 salts mean)    | 0.599 | ~0.616 | ~0.616 ± 0.018 |

Constant 0.62 wins because:
1. The LLM's r is near-random on test-condition data, so leaving it in
   degrades the blended ranking.
2. Hagai's LPS direction is informative but doesn't transfer perfectly to
   CRISPRi (different perturbation type).
3. The train prior reflects the true up:down ratio (2.2:1) and provides a
   consistent reference value.

### Confirmation: alpha sweep on the full-tier blend

| alpha (LLM weight) | DE | DIR | Combined |
|---|---|---|---|
| 0.0 (pure Replogle) | 0.599 | 0.449 | 0.524 |
| 0.2 | 0.599 | 0.457 | 0.528 |
| **0.4** ✅ | 0.599 | 0.507 | 0.553 |
| 0.5 | 0.599 | 0.482 | 0.540 |
| 1.0 (pure LLM) | 0.599 | 0.480 | 0.539 |

α=0.4 (LLM 40%, Replogle 60%) is the sweet spot on the full-tier
subset within the larger hybrid pipeline.

### Sanity: hybrid hurts on eval60 (which has gene-prior leakage)

Apply the same hybrid recipe to A07's eval60 outputs:

| | DE | DIR | Combined |
|---|---|---|---|
| Pure A07 on eval60 (leakage-inflated) | 0.601 | 0.645 | **0.623** |
| A07 + hybrid on eval60                | 0.601 | 0.431 | 0.516 |

This confirms the hybrid is specifically a **test-condition lever**.
eval60's gene-prior leakage gave the LLM a free DIR signal that the hybrid
replaces with prior — a net loss when the leakage is real. On test (no
leakage available), the hybrid is the right move.

## Coverage on the actual test set

| Signal source | Test rows covered | % |
|---|---|---|
| Hagai (mouse-BMDM LPS) — pert OR gene | 1166 / 1813 | 64.3% |
| Replogle full (direct ortholog logFC for the pair) | 994 / 1813 | 54.8% |
| Replogle pert-only (top responders for ortholog of pert) | 149 / 1813 | 8.2% |
| Neither Hagai nor Replogle full | ~519 / 1813 | ~28.6% |

So ~55% of test rows will get the hybrid Replogle blend on DIR; the rest
will get the 0.62 prior. The Hagai magnitude signal helps DE on 64% of rows.

## Expected Track-A LB

Probe60 closely matches test on signal-coverage distribution
(see `attempts/10_test_signal_audit/coverage.json`):

| Tier | Probe60 share | Test share |
|---|---|---|
| Tier 0 (rich: Replogle full + KG both sides + desc both sides) | 55% | 54% |
| Tier 1 (mid: KG both sides + desc both sides, no Replogle direct) | 35% | 37% |
| Tier 3 (one-sided) | 8% | 9% |

So **expected test Combined ≈ 0.55-0.61** with A11 prompt + hybrid runner.

Top-4 public LB band is 0.628-0.650. We are within ~0.02-0.07 of the
band on a **Track-A-compliant single-call architecture** for the first
time. Earlier attempts that scored 0.62-0.64 on eval60 were leakage-
inflated; their honest test estimate is now revised downward to ~0.47
without the hybrid.

## Verdict

This is the **first attempt with a credible 0.55+ test estimate on a
Track-A-compliant architecture**, validated against:
1. A test-mimic probe (probe60_rare_gene).
2. Two independent signal sources (Hagai mouse-BMDM LPS + Replogle ortholog).
3. A robust non-jittery runner recipe.

Ship `pipeline/prompt_builder_v3.py` + `pipeline/runner.py:hybrid_direction`
as the Track-A submission pipeline.

## Next levers (not blocking ship)

- **Per-row LLM-vs-prior gating**: maybe trust LLM r when it deviates
  sharply from 0.5 (>0.20). Initial test (`Hybrid + LLM r when far from 0.5`)
  hurt slightly (0.535 vs 0.613); deferred.
- **Other Task3_data**: Tahoe100, Kang, Perturb_KHP could give additional
  CRISPRi-like signal sources to cover the 28% of test rows currently
  served by prior alone.
- **Replogle blend alpha per tier**: maybe lower alpha (more Replogle, less LLM)
  helps further. Modest expected gain.

## Inputs / outputs

See `attempts/11_hagai_in_prompt/README.md` for the full file list.
