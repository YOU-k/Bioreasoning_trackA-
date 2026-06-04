# Files to sync manually between servers

`git push` only pushes tracked files. The items below are intentionally not in
git — either too large, competition-restricted, or trivially reproducible —
and need to be brought to a new server by hand or by script.

## Bring up the LLM server (one-time, ~5 minutes)

```bash
git clone git@github.com:YOU-k/Bioreasoning_trackA-.git
cd Bioreasoning_trackA-
pip install -r requirements.txt

# 1. Kaggle data (~263 KB total)
export KAGGLE_API_TOKEN=KGAT_xxxxxxxxxxxxxxxxxxxxxxxx
python scripts/download_data.py

# 2. Replogle prior (200 MB) — scp is fastest
scp THIS_SERVER:/data/yy_data/Bioreasoning_trackA/data/replogle_de.pkl data/

# 3. Generate prompts for both attempts
python -c "from pipeline.runner import build_all_prompts; \
           build_all_prompts(); \
           build_all_prompts(out_dir='attempts/03_kg_celltype/prompts', use_kg=True)"
```

After this, the LLM server has everything it needs to run inference.

## What's already in git (auto via `git pull`)

| Path | Size | Notes |
|---|---:|---|
| `pipeline/`, `scripts/`, `attempts/*/README.md` etc. | ~50 KB | All code and docs |
| `data/mouse_to_human_ortholog.json` | 41 KB | Mouse → human gene name map |
| `data/kg_index/string_edges.json` | 3.3 MB | High-confidence STRING PPI subgraph |
| `data/kg_index/gene_reactome.json` | 600 KB | Per-gene Reactome pathways |
| `data/kg_index/symbol_to_ensp.json` | 73 KB | Symbol → STRING ID |

Total committed payload: ~4 MB. No need to scp any of this.

## What's NOT in git

| File / dir | Size | Why excluded | How to obtain |
|---|---:|---|---|
| `data/train.csv` | 218 KB | Kaggle competition data; no redistribution | `scripts/download_data.py` (needs `KAGGLE_API_TOKEN`) |
| `data/test.csv` | 45 KB | Same | Same |
| `data/replogle_de.pkl` | 200 MB | Over GitHub's 100 MB hard cap | `scp` from this server, or regenerate (needs 15 GB Replogle h5ad) |
| `data/kg_raw/` | 600 MB | Pipeline uses the filtered index in `data/kg_index/`, not raw | `scripts/download_kg.py` — only needed if rebuilding `data/kg_index/` from scratch |
| `attempts/*/prompts/` | 4–7 MB each | Reproducible from `pipeline.runner.build_all_prompts` | Regenerate locally (see "Bring up" above) |
| `attempts/*/outputs/` | 10–30 MB after LLM run | Produced on LLM server, not source | `rsync` LLM server → this server after run |
| `*.zip`, `submission*.csv` | varies | Build artifacts | Produced by `scripts/make_submission.py` |
| `discussion/Fig6_decomposition_framework_writeup_中文版.pdf` | 1.4 MB | Private reference material | Only `scp` if needed for reading context (not required to run anything) |

## Regenerating `replogle_de.pkl` (if you don't want to scp 200 MB)

Needs the Replogle 2022 normalized h5ad files locally:
```
P007_ReplogleWeissman2022_K562_essential.h5ad   (~8.5 GB)
P007_ReplogleWeissman2022_rpe1.h5ad             (~6.6 GB)
```
plus the gene index file `gene_name_list_with_index.csv`.
Update the paths at the top of `attempts/01_cross_species_pilot/pilot_run.py` to match the local filesystem, then:
```bash
python attempts/01_cross_species_pilot/build_ortholog.py
python attempts/01_cross_species_pilot/pilot_run.py
```

The output `data/mouse_to_human_ortholog.json` is already in git; the rebuild
will overwrite it with identical content. The 200 MB `data/replogle_de.pkl`
is the part you actually need.

## Regenerating `data/kg_index/` from scratch (rarely needed)

Only needed if you change filtering rules in `attempts/03_kg_celltype/build_kg_index.py`.

```bash
python scripts/download_kg.py        # ~600 MB, takes ~25 minutes
python attempts/03_kg_celltype/build_kg_index.py   # ~15 seconds
```

## Sync direction: LLM server → this server (after inference)

```bash
# from this machine:
SERVER=your-llm-server
REPO=~/Bioreasoning_trackA-

rsync -avz \
    $SERVER:$REPO/attempts/02_baseline_prompts/outputs/ \
    ./attempts/02_baseline_prompts/outputs/

rsync -avz \
    $SERVER:$REPO/attempts/03_kg_celltype/outputs/ \
    ./attempts/03_kg_celltype/outputs/
```

After that, run `scripts/make_submission.py` on either side to assemble the
zip per Track A's format spec.
