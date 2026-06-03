# Attempt 01 — Cross-species transfer pilot

## Hypothesis
Human CRISPRi response (Replogle K562 + RPE1, ~4,400 perturbations between them)
can be used as a prior for mouse BMDM CRISPRi response (Track A test set), via
mouse → human gene ortholog mapping.

If the cross-species + cross-cell-type transfer is strong enough, Replogle
serves as the primary numerical signal for the offline pipeline. If weak,
it falls back to a low-weight auxiliary feature.

## What was tested
1. **Ortholog mapping strategies**: naive uppercase, mygene HomoloGene, and a
   merged (mygene + uppercase fallback) version.
2. **Replogle source variants**: K562 alone, RPE1 alone, K562+RPE1 averaged
   (union over perts), K562 ∩ RPE1 intersection.
3. **Score variants**: raw logFC vs top-N thresholded (top-50, top-200).
4. **Evaluation**: predict train.csv labels (the only ground truth available) by
   looking up each `(pert, gene)` pair's logFC in Replogle, then computing
   DE-AUROC and DIR-AUROC.

## Inputs
- `data/train.csv`
- `data/test.csv`
- `/data/data/biodata/scRNAseq/drug_pert/normalized/P007_ReplogleWeissman2022_K562_essential.h5ad`
- `/data/data/biodata/scRNAseq/drug_pert/normalized/P007_ReplogleWeissman2022_rpe1.h5ad`
- `/data/yy_data/RVQ-Alpha/data_utils/gene_name_list_with_index.csv` (var_index → human gene symbol)

## Outputs (consumed by `pipeline/`)
- `data/mouse_to_human_ortholog.json` — mouse symbol → best human ortholog
  (mygene first, naive uppercase if mygene's modern symbol is missing in Replogle).
- `data/replogle_de.pkl` — pickled dict with `k562`, `rpe1`, `combined` (averaged
  union) DE vectors keyed by mouse symbol, plus `sym_to_idx` and `m2h` maps.

## Scripts
- `build_ortholog.py` — runs mygene queries + builds the merged map.
- `pilot_run.py` — computes per-pert pseudobulk DE on Replogle K562/RPE1 and
  reports AUROC variants.

Result and conclusions: see `result.md`.
