# Attempt 01 — Result

## AUROC table (vs train labels)

| Variant | n_rows | DE-AUROC | DIR-AUROC | Combined |
|---|---:|---:|---:|---:|
| K562 (naive upper) | 3,936 | 0.524 | 0.625 | 0.574 |
| RPE1 (naive upper) | 4,141 | 0.539 | 0.633 | 0.586 |
| K562 + RPE1 averaged | 4,194 | 0.542 | 0.663 | **0.602** |
| K562 ∩ RPE1 (perts in both) | 3,883 | 0.548 | 0.671 | 0.609 |
| K562 top-200 thresholded | 3,936 | 0.526 | 0.559 | 0.542 |
| K562 top-50 thresholded | 3,936 | 0.524 | 0.542 | 0.533 |
| mygene ortholog only | 4,063 | 0.540 | 0.661 | 0.601 |
| mygene + upper fallback (final) | 4,154 | 0.541 | 0.663 | 0.602 |

Random baseline: 0.500. Noise floor on n≈4000: ±0.008.

## Findings
1. **DE channel ≈ random.** Cross-species transfer of "is this gene DE?" is
   essentially uninformative. Cell-type-specific universal drift (`G_c` in the
   Fig 6 decomposition) dominates which genes show up as top hits, and that
   component does not conserve K562/RPE1 → BMDM.
2. **DIR channel is real and useful.** Conditional on a gene being DE, the
   direction transfers across species and cell types (AUROC 0.62–0.67).
3. **Averaging K562 + RPE1 helps.** Two epithelial-leukemia averages remove
   cell-type-specific noise; DIR rises from 0.625/0.633 → 0.663.
4. **Thresholding hurts.** Raw logFC carries continuous ranking signal that
   AUROC consumes; binning into top-N discards information.
5. **Better ortholog mapping does not help.** mygene's modern names (e.g.
   `AARS1`) sometimes miss Replogle entries (which uses older `AARS`). A
   merged map with uppercase fallback rescues ~10 perts but does not move
   AUROC. Cause: the perts rescued were not the ones carrying meaningful signal.

## Verdict
Replogle is **a DIR prior**, plug it into `P_up_given_DE`. It is **not a DE
detector**, do not let it drive `P_DE`. The DE channel must come from
non-Replogle sources (KG retrieval, mechanistic reasoning, auxiliary classifier).

## Coverage on test set (downstream impact)
- `full` (both pert and gene have Replogle data): **994 / 1,813 = 55%**
- `pert_only` (pert has Replogle, target is Riken-style or no ortholog): **149 (8%)**
- `none` (pert is BMDM-relevant TF/signaling, not in K562/RPE1 essential): **670 (37%)**

The 37% `none`-tier rows are typically the most biologically interesting
(TFs, signaling) and need an entirely separate signal source.
