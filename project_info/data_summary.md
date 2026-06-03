# Data summary — MLGenX Bioreasoning Challenge Track A

Files downloaded into this folder on 2026-06-03 from the Kaggle competition data endpoint. See `overview.md` for the biological context, label definitions, evaluation metric, and submission spec.

## Files
| File | Bytes | Rows (excl. header) | Columns |
|---|---:|---:|---|
| `train.csv` | 223,222 | 7,705 | `id, pert, gene, label` |
| `test.csv`  | 45,625  | 1,813 | `id, pert, gene` |

The Track A `sample_submission_track_a.csv` and `prompt.txt` are not exposed through the public data-download endpoint — they need to be pulled from the Kaggle Data tab (logged-in browser session). The expected schema is documented in `overview.md`.

## Schema
- `id` — `{pert}_{gene}` (e.g. `Aars_Actb`, `Stat1_Irf1`).
- `pert` — perturbed (CRISPRi knocked-down) gene.
- `gene` — target / readout gene whose expression may change.
- `label` (train only) — ternary: `up`, `down`, `none`. See `overview.md` for the FDR + |logFC| thresholds.

Gene symbols are **mouse** (MGI nomenclature). Cell type = mouse BMDMs.

## Sample rows
`train.csv`:
```
id,pert,gene,label
Psmd4_Anxa2,Psmd4,Anxa2,down
Cul2_Upp1,Cul2,Upp1,none
```
`test.csv`:
```
id,pert,gene
Slc35b1_Pdia6,Slc35b1,Pdia6
Rprd2_9930111J21Rik2,Rprd2,9930111J21Rik2
```

## Label distribution (train)
| Class | Count | % |
|---|---:|---:|
| `none` | 4,260 | 55.3% |
| `up`   | 2,359 | 30.6% |
| `down` | 1,086 | 14.1% |

The class imbalance is intentional: per-perturbation sampling keeps up to 9 top DEGs plus a similar number of negatives. Predict-`none` accuracy ≈ 55% is the trivial baseline; AUROC of a `none`-only classifier on the DE task is 0.5.

## Train / test split — fully held-out on both axes
| Axis | Train unique | Test unique | Overlap |
|---|---:|---:|---:|
| `pert` (80/10/10) | 386 | 96 | **0** |
| `gene` (60/20/20) | 1,570 | 636 | **0** |

Every test row has both an **unseen perturbation** and an **unseen readout gene**. Memorization will not transfer — the model must generalize via gene representations (sequence, function, embeddings, pathway/GO priors, etc.).

## Modeling notes
1. **Validation split must mimic the test split.** Random row-level splits will leak. Use a group-out scheme that holds out perturbations *and* readout genes simultaneously (Track-A test is double-disjoint).
2. **Two scores per row.** The metric needs `prediction_up` and `prediction_down` as separate scalars — `prediction_up + prediction_down` drives the DE-AUROC, and the ratio `prediction_up / (prediction_up + prediction_down)` drives the DIR-AUROC. A softmax over the three classes is the natural parametrization (drop the `none` head's mass into the implicit residual `1 - up - down`).
3. **Gene/perturbation representations to consider:** pretrained gene LMs (Geneformer, scGPT), protein-language embeddings (ESM) on the encoded protein, curated annotations (GO, Reactome, STRING PPI), or zero-shot LLM reasoning over the symbol — appropriate given the "Use LLMs..." framing and the Track-A prompt-only constraint.
4. **Track A is prompt-only with 3 seeds.** Record the full LLM trace per seed and total tokens — these are required metadata. Final `prediction_up`/`prediction_down` are typically the seed-average.

## Origin & citations
- Data: genome-wide CRISPRi Perturb-seq screen on mouse BMDMs, processed by the CropFlow differential-expression pipeline.
- Format inspired by **PerturbQA** (Wu et al., *ICLR 2025*).
