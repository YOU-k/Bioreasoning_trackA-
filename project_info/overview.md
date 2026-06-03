# MLGenX Bioreasoning Challenge — Track A

Source: <https://www.kaggle.com/competitions/ml-gen-x-bioreasoning-challenge-track-a>

## Competition metadata
| Field | Value |
|---|---|
| Title | MLGenX Bioreasoning Challenge - Track A |
| Competition ID | 139738 |
| Tagline | Use LLMs to predict the response of genetic perturbations in cellular behavior. |
| Category | Community |
| Reward | 2,000 USD |
| Max team size | 10 |
| Max daily submissions | 5 |
| Tags | custom metric |
| Enabled | 2026-04-27 |
| Deadline / merger deadline | 2026-07-22 07:00 UTC |
| Teams (at fetch time) | 24 |

## Biological context
- Source data: a genome-wide **CRISPRi Perturb-seq screen in mouse bone marrow-derived macrophages (BMDMs)**, processed through the **CropFlow** differential-expression pipeline.
- Each row is a `(perturbation, target_gene)` pair. Task = ternary classification: when `perturbation` is knocked down, does the `target_gene` go **up**, **down**, or stay **none** (not significantly DE)?
- Sampling: for each perturbation, up to 9 of the top DEGs are added (labeled `up`/`down` by sign of logFC), plus a similar number of non-DE genes via negative sampling (labeled `none`). **482 perturbations** with ≥9 DEGs are retained in total.
- Gene names follow **mouse nomenclature** (e.g. `Aars`, `Actb`, `Stat1`).
- Fold-changes are **shrunken log2 fold-changes**, not raw.
- Format is inspired by **PerturbQA** (Wu et al., ICLR 2025).

### Label definitions
| Label | Rule |
|---|---|
| `up`   | FDR < 5% **and** logFC ≥ log2(1.5) |
| `down` | FDR < 5% **and** logFC ≤ -log2(1.5) |
| `none` | Does not meet either criterion above |

## Splits
Disjoint on **both** axes:

| Axis | Train / Val / Test ratio |
|---|---|
| Perturbation | 80 / 10 / 10 |
| Gene | 60 / 20 / 20 |

Every `(pert, gene)` belongs to exactly one split, no perturbation crosses splits, and no gene crosses splits.

| Split | Perturbations | Total rows |
|---|---:|---:|
| Train | 386 | 7,705 |
| Test (Public + Private) | 96 | 1,813 |

Kaggle randomly partitions `test.csv` into a Public (live) and Private (final) leaderboard; the Private board determines final ranking.

## Evaluation metric
```
score = (micro_AUROC_DE + micro_AUROC_DIR) / 2
```
- **DE AUROC (differential expression).** Binary label: `1` if true class is `up` or `down`, else `0`. Model score per row = `prediction_up + prediction_down` (one scalar in [0, 1]).
- **DIR AUROC (direction).** Restricted to rows whose true label is `up` or `down`. Binary label: `1` if `up`, `0` if `down`. Model score per row = `prediction_up / (prediction_up + prediction_down)` — i.e. conditional `P(up | DE)`.
- Random baseline ≈ 0.5; perfect = 1.0.

Secondary, **non-ranking** leaderboard columns:
- `Total tokens used` (all tracks) = sum of `tokens_used` over all rows.
- `Total tool calls` (Track B only) = sum of `num_tool_calls` over all rows.

## Track-A submission spec (prompt-only LLM, 3 calls × seeds 42/43/44)
Upload a **zip** containing `submission.csv` + `prompt.txt` (the prompt template you used).

`submission.csv` columns (must match every `id` in `test.csv`, no nulls):

| Column | Type | Default | Notes |
|---|---|---|---|
| `id` | string | — | Must match every `test.csv` id |
| `prediction_up` | float | 0.5 | Final up score (used for scoring) |
| `prediction_down` | float | 0.5 | Final down score (used for scoring) |
| `prediction_up_seed42` | float | 0.5 | |
| `prediction_down_seed42` | float | 0.5 | |
| `prediction_up_seed43` | float | 0.5 | |
| `prediction_down_seed43` | float | 0.5 | |
| `prediction_up_seed44` | float | 0.5 | |
| `prediction_down_seed44` | float | 0.5 | |
| `reasoning_trace_seed42` | string | `""` | Full LLM output for seed 42 (use `"none"` if empty) |
| `reasoning_trace_seed43` | string | `""` | Full LLM output for seed 43 |
| `reasoning_trace_seed44` | string | `""` | Full LLM output for seed 44 |
| `tokens_used` | int | 0 | Sum of input + output tokens across all 3 calls |
| `model_name` | string | `""` | Model identifier |

Notes:
- Final `prediction_up` / `prediction_down` are typically the **average across the three seeds** (the exact aggregation rule is whatever your sample submission encodes).
- **No null values** — fill empty reasoning with the string `"none"` and missing token counts with `0`.
- Missing metadata columns → submission scored 0.

## Competition rules

### Cross-track rules
- Good-faith cheating policy — organizer discretion.
- Every submission must include: reasoning traces, final answers, token usage, tool usage (if applicable), and model size/type.
- Allowed to train auxiliary models on **any publicly available** perturbation datasets (PerturbQA and other public resources).

### Track A — Prompt-only, single call (binding)
- **Base LLM is fixed to `GPT-OSS-120B`**; no fine-tuning.
- Sampling is enforced: `temperature = 1.0`, `top_p = 1.0`.
- Task format: `Question-Specific Prompt + input question → output`.
- **Max prompt tokens: 4,096** (per the rules, this is intentionally tight — designed to prevent "dumping info into the prompt" and force creativity).
- The prompt **cannot directly contain the expected outputs**.
- **3 samples per question** with seeds 42, 43, 44.

### Track B — (Multi-)agentic tool-use
- Base LLM fixed to `GPT-OSS-120B`, no fine-tuning. `temperature=1.0`, `top_p=1.0`.
- Task format: `General Prompt + tool file + input question → output`.
- Max distinct tools: **100**. Max total tool calls: **250**. Max prompt tokens: **16,384**.
- Traces must be shared for auditability.
- Allowed: retrieval from public data (GRN queries, GO/pathway lookup, model access), predictive models trained on public data, multi-agent design.
- Not allowed: any LLM other than `GPT-OSS-120B`; training or fine-tuning ad-hoc models on the competition's own data.

### Track C — Fine-tuning (reasoning, no tools)
- Start from an open-source LLM with **< 10B parameters** (example: `Qwen3-4B-Thinking-2507`).
- Any fine-tuning technique allowed (SFT, LoRA, RL, etc.).
- Task format: `General Prompt + input question → output`.
- Max new tokens during inference: **16,000**.
- Inference-time bans: no tools, no web, no external models.

### Track URLs
- <https://www.kaggle.com/competitions/ml-gen-x-bioreasoning-challenge-track-a> (this folder)
- <https://www.kaggle.com/competitions/ml-gen-x-bioreasoning-challenge-track-b>
- <https://www.kaggle.com/competitions/ml-gen-x-bioreasoning-challenge-track-c>
