# Attempt 03 — KG mechanism context + cell-type translation guide

## Hypothesis
The attempt 02 baseline gives the LLM a Replogle scalar without explaining
**how** to translate it from human K562/RPE1 to mouse BMDM. We expect the
LLM to over-trust the scalar on context-dependent genes (immune effectors,
TLR/IFN, lineage markers) where K562/RPE1 biology simply doesn't reflect
macrophage biology.

Adding two layers:

- **Layer 2 — Mouse KG mechanism context**: per query, list the pert's and
  target's Reactome pathways (top 3 each), shared pathways, and the STRING
  PPI shortest path (depth ≤3, score ≥700) between them. Gives the LLM a
  *mechanism* to reason from, not just a scalar.
- **Layer 3 — Cross-cell-type translation guide**: a static rule block
  classifying gene categories into "transfer-friendly" (UNIVERSAL_STRESS,
  TRANSLATION, CELL_CYCLE, PROTEOSTASIS, METABOLISM_CORE, CHROMATIN_GENERIC)
  versus "context-dependent" (IMMUNE_EFFECTOR, INTERFERON, TLR_NLR,
  MYELOID_LINEAGE). Plus a per-query tag block telling the LLM which
  category the specific pert and target fall in, and a one-line advice
  (trust Replogle, downweight Replogle, or use mechanism only).

## Inputs
- `data/test.csv`
- `data/replogle_de.pkl`, `data/mouse_to_human_ortholog.json` (attempt 01)
- `data/kg_index/{string_edges, gene_reactome, symbol_to_ensp}.json` (built by `build_kg_index.py`)
- Raw KG (one-time download, ~600 MB, gitignored): see `scripts/download_kg.py`

## Code touched
- `pipeline/kg_retrieval.py` — `KGRetrieval` class: per (pert, gene) returns pathways, shared pathways, shortest path
- `pipeline/celltype_guide.py` — static rules + score-based per-gene category tagging
- `pipeline/prompt_builder.py` — `_format_kg_block`, integrated Layer 2 + 3 into `build_prompt(..., use_kg=True)`
- `pipeline/runner.py` — `build_all_prompts(use_kg=True)` switch

## How to reproduce
```bash
# one-time downloads + index build
python scripts/download_kg.py
python attempts/03_kg_celltype/build_kg_index.py

# generate prompts
python -c "from pipeline.runner import build_all_prompts; \
           build_all_prompts(out_dir='attempts/03_kg_celltype/prompts', use_kg=True)"
```

Then on the LLM server:
```bash
python scripts/run_inference.py --model gpt-oss-120b --concurrency 8 \
    --out attempts/03_kg_celltype/outputs
```

Result and conclusions: see `result.md`.
