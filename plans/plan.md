# Plan — what's next

Forward-looking only. Historical decisions live in `progress.md`. Each entry is one candidate attempt with rationale, expected impact, and concrete deliverables.

## Current strategic frame

Public leaderboard ceiling looks like ~0.65 (top-4 cluster 0.628–0.650). Replogle-only baseline applied naively (0.5 default for no-prior rows) likely scores ~0.55. To push above 0.60, the LLM needs more than a scalar to work with.

Architecture: per-question prompt is **four conceptual layers**.

| Layer | Adds | Status |
|---|---|---|
| 1 — Replogle scalar | logFC + top responders for the pert | ✅ shipped in attempt 02 |
| 2 — KG mechanism context | pert↔gene path in STRING/Reactome, pathway membership, GO overlap | ❌ attempt 03 |
| 3 — Cell-type translation guide | static rules for "what transfers K562/RPE1 → BMDM and what doesn't" | ❌ attempt 03 |
| 4 — Case-based exemplars (optional) | retrieved similar (pert', gene', label) triplets from train | ⏳ deferred |

## Pending — in order

### P1 · Run baseline (attempt 02) on the LLM server
Run `scripts/run_inference.py` with deployed GPT-OSS-120B against the 1,813 baseline prompts × 3 seeds.

- Cost: ~3 hours of inference time
- Deliverable: `attempts/02_baseline_prompts/outputs/{seed}/{id}.txt` + the real Kaggle Public LB score in `result.md`
- Decision point: the LB score tells us how much room layers 2-3 need to fill

### P2 · Attempt 03 — KG + cell-type guidance
Add Layer 2 + Layer 3 to the prompt.

- Implement `pipeline/kg_retrieval.py` (STRING PPI mouse + Reactome mouse GMT → per (pert, gene) shortest path, pathway overlap, GO term overlap)
- Implement `pipeline/celltype_guide.py` (static rule block: which gene categories transfer well from K562/RPE1 to BMDM, which don't)
- Extend `pipeline/prompt_builder.py` to inject the two blocks (≤400 tokens each, keep total under 4096)
- Regenerate 1813 prompts under `attempts/03_kg_celltype/prompts/`
- Re-run LLM × 3 seeds
- Compare against attempt 02
- Expected gain: **+0.03–0.05 combined AUROC**

### P3 · Attempt 04 — auxiliary DE classifier (decide after P2)
Triggered only if P2 doesn't lift DE-AUROC to ~0.60+.

- Train a small LightGBM (Replogle logFC vec + pathway distance + gene class + baseline expression + train pert-class × gene-class DE rate → P_DE)
- Inject prediction into prompt as an external scalar
- Expected gain: **+0.02–0.03 combined AUROC**

### P4 · Submission format verification (before first real upload)
- Pull real `sample_submission_track_a.csv` from logged-in Kaggle Data tab
- Diff column names / types against `pipeline/runner.assemble_submission()`
- Test the zip on a one-row submission through Kaggle's validator
- Cost of skipping: 0-score submission, wastes a daily slot

## Deferred / closed

- **Layer 4 case-based exemplars** — implementation cost is high; user's prior work shows "vote bias" risk where the example label distribution dominates over example facts. Revisit only if Layers 2-3 land cleanly.
- **Ortholog mapping improvements** — pilot showed saturation (no AUROC gain). Closed.
- **Public BMDM CRISPRi lookup** — competition source is Genentech-internal. Closed.
- **PubMed abstract retrieval** — too noisy, high token cost. Subsumed by Layer 3 static rules.
