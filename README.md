# MLGenX Bioreasoning Challenge — Track A

Submission pipeline for the [MLGenX BRChallenge Track A](https://www.kaggle.com/competitions/ml-gen-x-bioreasoning-challenge-track-a) (ICLR 2026 MLGenX workshop). Predicts ternary perturbation response (`up` / `down` / `none`) for unseen `(perturbed_gene, target_gene)` pairs in mouse BMDM CRISPRi using GPT-OSS-120B with question-specific prompts.

## Approach in one paragraph

The competition metric decomposes into `(DE-AUROC + DIR-AUROC) / 2`, with `p_up + p_down` driving DE and `p_up / (p_up + p_down)` driving DIR. We treat these as two **independent** binary problems: each prompt asks the LLM to emit two integers `P_DE` and `P_up_given_DE` on a calibrated 0–100 scale, then we combine. A cross-species CRISPRi prior from Replogle K562 + RPE1 fills the `P_up_given_DE` channel for ~55% of test rows (combined AUROC 0.602 on the subset where applicable, with DIR-AUROC = 0.66 doing most of the work). The remaining 45% of rows — typically BMDM-relevant transcription factors not present in human essential-gene screens — rely on the LLM's mechanistic reasoning together with a mandatory disconfirming-check step designed to fight the "any function = useful" optimism bias.

See `discussion/analysis.md` and `discussion/tricks.md` for the full reasoning, and `progress.md` for what has been tried so far.

## Quick start

```bash
# 1. Install dependencies (Python 3.10+)
pip install -r requirements.txt

# 2. Download competition data
#    Get a Kaggle API token from https://www.kaggle.com/settings/account
export KAGGLE_API_TOKEN=KGAT_xxxxxxxxxxxxxxxxxxxxxxxx
python scripts/download_data.py
# -> data/train.csv, data/test.csv

# 3. Build the cross-species Replogle prior (one-time, ~1 minute)
#    Needs the Replogle 2022 h5ad files locally; see attempts/01_cross_species_pilot/README.md
python attempts/01_cross_species_pilot/build_ortholog.py     # mouse -> human ortholog
python attempts/01_cross_species_pilot/pilot_run.py          # pseudobulk DE on K562 + RPE1
# -> data/mouse_to_human_ortholog.json, data/replogle_de.pkl

# 4. Sanity tests (must pass before changing pipeline code)
python -m pipeline.tests.test_prior
python -m pipeline.tests.test_prompt
python -m pipeline.tests.test_parser

# 5. Generate per-question prompts for all 1813 test rows
python -c "from pipeline.runner import build_all_prompts; build_all_prompts()"
# -> attempts/02_baseline_prompts/prompts/{id}.txt

# 6. Run GPT-OSS-120B × 3 seeds (on the LLM server)
export LLM_BASE_URL=http://your-vllm-server:8000/v1
export LLM_API_KEY=anything
python scripts/run_inference.py --model gpt-oss-120b --concurrency 8
# -> attempts/02_baseline_prompts/outputs/{seed}/{id}.txt

# 7. Assemble submission zip
python scripts/make_submission.py \
    --outputs attempts/02_baseline_prompts/outputs \
    --prompt-template attempts/02_baseline_prompts/PROMPT_TEMPLATE.txt \
    --out attempts/02_baseline_prompts/submission.zip \
    --model gpt-oss-120b
```

## Repository layout

| Path | Purpose |
|---|---|
| `data/` | Raw inputs (`train.csv`, `test.csv` — not committed) and computed priors |
| `project_info/` | Competition spec, data schema, rules — fixed reference |
| `discussion/` | Reasoning notes and analytical frameworks |
| `plans/` | Plans for the next attempts |
| `pipeline/` | Shared infrastructure: prior loading, prompt building, output parsing, submission assembly |
| `pipeline/tests/` | Sanity tests (run in <5 s, must pass before pipeline changes) |
| `attempts/NN_short_name/` | One experiment per folder, each with `README.md` and `result.md` |
| `scripts/` | One-shot utilities: data download, LLM inference, submission packaging |
| `progress.md` | Append-only running log of attempts and conclusions |
| `CLAUDE.md` | Internal conventions for AI-assisted development |

## Status

- **Cross-species transfer pilot done** (attempt 01). Replogle K562+RPE1 averaged → combined AUROC 0.602; DE-AUROC 0.54, DIR-AUROC 0.66.
- **Prompt scaffold built** (attempt 02). 1,813 question-specific prompts, median 1,018 input tokens. 55% have full Replogle prior, 8% partial, 37% none.
- **Inference not yet run** — GPT-OSS-120B deployment access required.
- **Leaderboard reference**: top public score ≈ 0.65, top-4 cluster in 0.628–0.650.

See `progress.md` for the full history.
