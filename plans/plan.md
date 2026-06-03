# Track A pipeline — current state and next steps

## Done

### A. Improved ortholog mapping
- **Tools used**: `mygene.info` HomoloGene + naive uppercase fallback.
- **Output**: `mouse_to_human_ortholog.json` (2,222 mouse symbols → human via HomoloGene; 2,273 with uppercase fallback for Replogle-named cases like `Aars` → `AARS`).
- **Coverage** (mygene + uppercase fallback):

  | Set | n | with prior | %|
  |---|---:|---:|---:|
  | test perts | 96 | 62 | 65% |
  | train perts | 386 | 251 | 65% |
  | test genes | 636 | ≈530 | 83% |

- **Result on cross-species transfer**: combined AUROC = **0.602** (K562+RPE1 averaged), unchanged from naive uppercase. The 30+ rescued perts didn't shift the overall signal because mygene was already finding most useful orthologs.
- **Takeaway**: ortholog improvement is **maxed out**. DIR transfer caps at ~0.66, DE transfer at ~0.54.

### B. Searched for the BMDM CRISPRi source
- The competition is the **inaugural BRChallenge** at **MLGenX@ICLR 2026**.
- Workshop organizers: Aviv Regev, Tommaso Biancalani (both Genentech), Fabian Theis, plus Mihaela van der Schaar, Ehsan Hajiramezanali, Arman Hasanzadeh, Wei Qiu.
- PerturbQA (Wu et al ICLR 2025) is Genentech — the competition's "format inspired by PerturbQA" + the unidentifiable `CropFlow` pipeline name both point to **internal Genentech tooling**.
- Public mouse BMDM CRISPRi Perturb-seq with ≥482 perturbations matching the test set: **no candidate found** across scPerturb, X-Atlas/Orion, VIPerturb-seq, Hagai 2018, the Replogle/Nadig PerturbQA datasets, the Sankaran macrophage CRISPR work, etc.
- **Conclusion: no direct answer lookup possible. The competition's source data is almost certainly Genentech-internal.**

### C. Pipeline scaffold built
`pipeline/`:
| File | Purpose |
|---|---|
| `replogle_prior.py` | Loads K562+RPE1 averaged DE; per (pert, gene) returns logFC + top responders + tier label |
| `prompt_builder.py` | Builds per-question prompt for GPT-OSS-120B (≤4096 tokens, double-AUROC parameterization, anchor scale, disconfirming step) |
| `output_parser.py` | Parses `P_DE` + `P_up_given_DE` integer outputs; produces `p_up`, `p_down`; safe fallback on parse failure |
| `runner.py` | `build_all_prompts()` → 1,813 prompts; `assemble_submission()` → submission.csv from per-seed LLM outputs |

`prompts/` — **1,813 question-specific prompts written, median 1,018 tokens (≤4,096 budget)**.

Tier distribution on test set:
- `full` (Replogle has both pert+gene): **994 rows (55%)**
- `pert_only` (Replogle has pert, gene has no ortholog): **149 rows (8%)**
- `none` (pert is BMDM-specific TF/signaling, not in K562/RPE1 essential): **670 rows (37%)**

Round-trip validated: a sample LLM-style output is correctly parsed into `p_up`/`p_down`.

---

## What's still missing for a real submission

### 1. Actually run GPT-OSS-120B × 3 seeds × 1,813 prompts (= 5,439 inferences)
- GPT-OSS-120B requires substantial GPU (single A100 80GB is tight, two recommended for batching at temp=1).
- Estimated runtime: with vLLM and ~200 output tokens each, 5,439 × ~2s = ~3 hours on 2× H100. On a single A100, ~6-8 hours.
- Tool: vLLM with `temperature=1.0, top_p=1.0, seed ∈ {42, 43, 44}`.
- Output structure expected by `assemble_submission()`:
  ```
  outputs/42/{id}.txt       <- raw LLM output, seed 42
  outputs/43/{id}.txt
  outputs/44/{id}.txt
  outputs/tokens/{id}.json  <- {"42": n42, "43": n43, "44": n44}
  ```

### 2. Improve the 37% "none-tier" rows
For the 670 test rows where Replogle gives no signal, the LLM has only its parametric knowledge. Most of these perts are **BMDM-relevant TFs / signaling** (Cebpb, Stat1, Nfkb1, Irf-family, Plcg2, Pak2, …) — exactly the rows where Replogle is uninformative but the biology is richest. Options:

- **KG retrieval** (STRING/Reactome/GO over mouse): for each `(pert, gene)`, find shortest path and pathway co-membership; embed as a compact context block.
- **PubMed abstracts**: pre-fetch (pert, "BMDM" OR "macrophage") top-5 abstracts, distill into 1-line summaries.
- **Public BMDM stimulation data** (your P031/P032, Hagai 2018, etc.): even though they're stimulations not KD, they tell us which genes respond to inflammatory signaling in BMDM context — useful as gene-expression-context prior.

These would lift `none`-tier from ~0.50 baseline AUROC up; expected total combined target 0.70-0.75 vs the current Replogle-alone floor of 0.60 (on rows where it applies).

### 3. Train an auxiliary DE classifier
Replogle's DE channel is weak (0.54). A small LightGBM/MLP on features (Replogle vec, pathway distance, gene class, train pert-class × gene-class DE rate, expression level) could deliver 0.65+ for DE specifically. Then feed its prediction into the prompt as another scalar input.

### 4. Lock down the actual `submission.csv` upload format
We never could pull `sample_submission_track_a.csv` from the public Kaggle API — only the rules tab text. Before zipping the first real submission, **download the sample from the logged-in Data tab** to verify column types match exactly (`tokens_used` int, `prediction_up` float, reasoning_trace string, etc.) and that submission.csv + prompt.txt go into the zip with no extra files.

---

## Files in this folder
```
data:          train.csv (7705 rows), test.csv (1813 rows)
priors:        mouse_to_human_ortholog.json, replogle_de.pkl (450 K562 + 506 RPE1 perts)
docs:          overview.md, data_summary.md, analysis.md, tricks.md, plan.md (this)
pipeline:      pipeline/{replogle_prior,prompt_builder,output_parser,runner}.py
prompts:       prompts/*.txt   (1813 files, median 1018 tokens each)
```
