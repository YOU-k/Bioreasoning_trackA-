# Attempt 02 — Baseline Track A prompt scaffold

## Goal
Build the core Track A pipeline that, for every test row, produces a
question-specific prompt under the 4,096-token Track A budget, encoding:

- The cross-species Replogle prior (when applicable).
- A double-AUROC parameterization (`P_DE` and `P_up_given_DE` as separate
  integer outputs in 0–100).
- A mandatory disconfirming-check step to fight the "any function = useful"
  LLM optimism bias.
- An anchor scale that forces the model to use the full 0–100 range
  (avoiding variance compression).

## Inputs
- `data/test.csv`
- `data/replogle_de.pkl` (from attempt 01)
- `data/mouse_to_human_ortholog.json` (from attempt 01)

## Outputs
- `prompts/{test_id}.txt` — 1,813 prompts, one per row of `test.csv`.
- `prompts/_summary.json` — per-row metadata: pert, gene, tier, token estimate.

## Code touched
- `pipeline/replogle_prior.py` — `ReplogPrior` class: load Replogle DE, expose
  `has_pair`, `get_pair_logfc`, `get_top_responders`, `tier`.
- `pipeline/prompt_builder.py` — `build_prompt(pert, gene, prior)` returns the
  per-question prompt string.
- `pipeline/output_parser.py` — `parse(raw_llm_output) → ParsedOutput` with
  `p_de`, `p_up_given_de`, `p_up`, `p_down`.
- `pipeline/runner.py` — `build_all_prompts()` and `assemble_submission()`.

## How to reproduce
```bash
python3 -c "from pipeline.runner import build_all_prompts; build_all_prompts()"
```

Result and conclusions: see `result.md`.
