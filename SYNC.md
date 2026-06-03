# Files to sync manually between servers

These files are intentionally not in git — either too large, competition-restricted, or trivially reproducible. Sync them by hand when bringing up a new server.

## From this server → LLM server (one-time)

| File | Size | Why not in git | Easiest path |
|---|---:|---|---|
| `data/train.csv` | 218 KB | Kaggle competition data — should not be redistributed | `KAGGLE_API_TOKEN=... python scripts/download_data.py` |
| `data/test.csv` | 45 KB | Kaggle competition data | (same as above — fetches both) |
| `data/replogle_de.pkl` | **200 MB** | Too big for GitHub (>100 MB limit) | `scp` from this server, OR regenerate (see below) |
| `attempts/02_baseline_prompts/prompts/` | ~4 MB across 1,813 files | Fully reproducible artifact | `python -c "from pipeline.runner import build_all_prompts; build_all_prompts()"` after `replogle_de.pkl` is present |
| `discussion/Fig6_decomposition_framework_writeup_中文版.pdf` | 1.4 MB | Private reference material | Only `scp` if you want the reading context on the LLM server (not required to run anything) |

### Recommended sync command (this server → LLM server)

```bash
# from this machine:
SERVER=your-llm-server
scp data/replogle_de.pkl $SERVER:~/Bioreasoning_trackA-/data/
# the rest are regenerated on the LLM side
```

### If you want to regenerate `replogle_de.pkl` on the LLM server instead

Needs the Replogle 2022 normalized h5ad files locally:
```
P007_ReplogleWeissman2022_K562_essential.h5ad   (~8.5 GB)
P007_ReplogleWeissman2022_rpe1.h5ad             (~6.6 GB)
```
plus the gene index file `gene_name_list_with_index.csv`.
Update the paths at the top of `attempts/01_cross_species_pilot/pilot_run.py` to match the LLM server's filesystem, then:
```bash
python attempts/01_cross_species_pilot/build_ortholog.py
python attempts/01_cross_species_pilot/pilot_run.py
```
Output: `data/mouse_to_human_ortholog.json` (already in git, will be overwritten — same content) and `data/replogle_de.pkl` (~200 MB).

## From LLM server → this server (after inference)

| File | Size | Sync path |
|---|---:|---|
| `attempts/02_baseline_prompts/outputs/{seed}/{id}.txt` | ~5,439 files, ~10–30 MB | `rsync` or `scp -r`. They're `.gitignore`d but can be force-added with `git add -f` if you want them in git |
| `attempts/02_baseline_prompts/outputs/tokens/{id}.json` | 1,813 small files | (same) |
| Final `submission.zip` | ~5–10 MB | `scp` back if you submit from here |

### Recommended sync command (LLM server → this server)

```bash
# from this machine:
rsync -avz --include='*/' --include='*.txt' --include='*.json' --exclude='*' \
    $SERVER:~/Bioreasoning_trackA-/attempts/02_baseline_prompts/outputs/ \
    ./attempts/02_baseline_prompts/outputs/
```

## Files NOT to commit (already in `.gitignore`)

For reference, these are excluded by `.gitignore` and should stay excluded:
- `data/train.csv`, `data/test.csv` — competition redistribution
- `data/replogle_de.pkl` — too big
- `attempts/*/prompts/`, `attempts/*/outputs/` — reproducible / large
- `*.zip`, `submission*.csv` — build artifacts
- `discussion/Fig6_decomposition_framework_writeup_中文版.pdf` — private
- `__pycache__/`, `.venv/`, `.claude/settings.local.json`, etc.

If you ever need to commit an output file (e.g. an inference run you want to checkpoint), use `git add -f <path>`.
