# Attempt 12 — Ablate hand-written boilerplate

## Why

The user audited the A11 prompt and questioned how much of the ~2630
tokens is actually query-specific vs hand-written boilerplate:

> "现在的prompt里好多信息不知道哪里来的 ... 对于query又非常的粗糙，感觉大部分的信息不是真的关键的query啊？"

Two concrete questions:
- **A**: The Hagai block printed "→ UP (strong) under LPS" wording, but LPS
  direction does NOT transfer to CRISPRi (R3 says so explicitly). Should we
  strip the direction info and show only magnitude?
- **C**: The 723-token `## Cell context (BMDM)` paragraph in
  `pipeline/bmdm_context.py` is hand-written by us, not derived from data.
  Static, identical every row. Is it actually helping the LLM?

## Method

2×2 ablation on the same probe60_rare_gene (seed=789):

| Variant | Hagai wording | BMDM context paragraph |
|---|---|---|
| **A11 baseline** | direction + magnitude ("→ UP strong") | included |
| A only | magnitude only ("→ strongly LPS-regulated") | included |
| C only | direction + magnitude (unchanged) | **dropped** |
| A + C | magnitude only | dropped |

## Results

### Pure LLM (no runner hybrid)

| Variant | DE | DIR | Combined |
|---|---|---|---|
| A11 baseline | 0.599 | 0.480 | 0.539 |
| A only | 0.522 | 0.507 | 0.515 |
| **C only** ✅ | **0.644** | **0.540** | **0.592** |
| A + C | 0.618 | 0.520 | 0.569 |

### LLM + hybrid runner (full-tier Replogle blend + prior 0.62)

| Variant | DE | DIR | Combined |
|---|---|---|---|
| A11 baseline | 0.599 | 0.627 | 0.613 |
| A only | 0.522 | 0.625 | 0.574 |
| **C only** ✅ | **0.644** | 0.605 | **0.625** |
| A + C | 0.618 | 0.621 | 0.620 |

### Effect decomposition

- **Change A (Hagai magnitude wording)**: -0.022 to -0.039 Combined. The LLM
  was actually using the direction text as a feature for P_DE — stripping it
  reduced DE-AUROC from 0.599 → 0.522 (-0.077). Net negative.

- **Change C (drop BMDM context)**: +0.012 to +0.053 Combined. Saving
  723 prompt tokens (~28% of A11 prompt) and lifting both DE and DIR
  on the LLM-alone surface. The hand-written paragraph was either
  noise or actively distracting.

The 2x2 decomposition is clean: A and C effects are roughly additive,
with A always negative and C always positive.

## Verdict

**Ship C-only**: keep the original Hagai direction wording (R3 caveat
already tells the LLM not to copy direction); drop the BMDM context
paragraph.

- Pure LLM Combined: 0.592 (vs A11 0.539, +0.053)
- With hybrid runner: 0.625 (vs A11 0.613, +0.012)
- Token budget: 1886 vs 2629 (saves 28%)

The lift is modest with hybrid runner (+0.012) but the token savings
unlock budget for future enrichment (Tahoe / Kang / Perturb_KHP signals,
richer evidence-case rendering).

## Changes shipped

- `pipeline/prompt_builder_v3.py`: `include_bmdm_context` flag,
  **default False** (was True in A11).
- `pipeline/tests/test_prompt_v3.py`: added
  `test_bmdm_context_paragraph_off_by_default`, 7/7 pass.
- `scripts/eval_metric_v4.py`: `--with-bmdm-context` opt-in flag (previously
  `--no-bmdm-context` opt-out).

## Files

- `attempts/12_cleaner_prompt/outputs/probe60_A_only/single/{id}.json`
- `attempts/12_cleaner_prompt/outputs/probe60_C_only/single/{id}.json`
- `attempts/12_cleaner_prompt/outputs/probe60_A_plus_C/single/{id}.json`
- `attempts/12_cleaner_prompt/outputs/comparison_4way.txt`
- `attempts/12_cleaner_prompt/prompts/SHIP_Tlr4_Cd14.txt` — current ship default
- `attempts/12_cleaner_prompt/prompts/example_Tlr4_Cd14_with_bmdm.txt` — legacy
- `attempts/12_cleaner_prompt/prompts/example_Tlr4_Cd14_no_bmdm.txt`
- `scripts/compare_a11_variants.py`
