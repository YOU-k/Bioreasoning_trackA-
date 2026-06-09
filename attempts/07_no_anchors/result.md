# Attempt 07 — result

**Date**: 2026-06-09
**Status**: **ACCEPTABLE** per the pre-registered validation gate
(Combined ∈ [0.60, 0.634]). Recommended Track-A submission path.

## Headline

On the same 60 random train rows (seed=123) used to grade attempts 03 / 04 / 05 / 06:

| Metric | A03 | A04 | A05 | A06 | **A07** | Δ vs A06 | vs A05 (best non-compliant) |
|---|---|---|---|---|---|---|---|
| DE-AUROC | 0.654 | 0.601 | 0.610 | 0.559 | **0.601** | **+0.042** | -0.009 |
| DIR-AUROC | 0.451 | 0.679 | 0.665 | 0.611 | **0.645** | **+0.034** | -0.020 |
| **Combined** | 0.552 | **0.640** | 0.637 | 0.585 | **0.623** | **+0.038** | -0.014 |

60 / 60 rows parsed cleanly (`parse_status == 'ok'` everywhere).

## What worked

- **Removing prescriptive anchors** recovered both heads:
  - DE-AUROC up 0.042 (back to the A04 plateau)
  - DIR-AUROC up 0.034
  - Combined up 0.038
- **Tier ladders alone are enough calibration scaffolding**. The model
  located itself across the full P_DE range (5, 10, 15, 20, 25, 30, 35,
  40, 55, 70, 80, 85, 90 all appeared), instead of collapsing into the
  15-25 bucket.
- **High-confidence cases stayed clean**: P_DE ≥ 70 hit 5/6 true DE; a
  perfect example is `Ifnar1_Irgm1` (P_DE=85, P_up=5, true=down) —
  strong DE detection AND correct direction.

## What still leaks signal

- ~17/60 rows landed at exactly P_up = 50 (the natural midpoint of the
  45-54 "ambiguous direction" band). Less severe than attempt 06's 26
  rows at 62, but still creating AUROC ties. This is genuinely
  "I don't know" behaviour by the model, which is honest but gives up
  ranking signal.
- Direction was flipped on a few high-confidence cases:
  `Dph3_Hmox1` (P_up=95, true=down), `Cct5_Tuba1c` (P_up=20, true=up).
  Same failure pattern as attempt 06; not a prompt-design issue, more
  a fundamental limit of single-LLM direction calls without external
  signed-pathway data.

## Cost of Track-A compliance

`A05 - A07 = 0.637 - 0.623 = 0.014 Combined`

That's the documented cost of going from two-prompt (non-compliant
6 calls per question) to single-call (compliant 3 calls). For the
final GPT-OSS-120B submission, this is the right trade.

## Recommendation

**Ship `pipeline/prompt_builder_v3.py` as the Track-A submission prompt.**

Run with seeds 42 / 43 / 44 against all 1,813 test rows, aggregate with
`pipeline/runner.assemble_submission()` (now using `fuse_q_r_logit` for
the 3-seed fusion), package the zip per Track-A spec, submit.

## Future improvements (out of scope for shipping)

If we want to recover the remaining 0.014 vs the non-compliant version:

1. **Runner-side direction-prior shrinkage**: pull r toward 0.62 when
   the LLM emits r ∈ [0.45, 0.55]. Tested in attempt 06 (as a prompt
   instruction) and backfired; might work as post-hoc shrinkage where
   the LLM never sees the number.
2. **Signed-pathway lookup at retrieval time**: pre-compute STRING/Reactome
   sign for each (pert, gene) edge and surface in the prompt as a hard
   feature. Would help cases like `Dph3_Hmox1` where direction reasoning
   alone fails.
3. **Macro-per-gene audit** (`discussion/next_paradigm_gpt.md` §7):
   check whether attempt 07's gains are gene-prior voting in disguise.
   Required before claiming method validity.

## Inputs

Unchanged from attempts 05-06:
- `data/{train,test}.csv`, `data/replogle_de.pkl`, `data/mouse_to_human_ortholog.json`
- `data/kg_index/`, `data/gene_desc.json`
- `pipeline/{retrieve_examples,bmdm_context,gene_desc,replogle_prior,kg_retrieval}.py`

Modified vs attempt 06:
- `pipeline/prompt_builder_v3.py` — R2 + R4 removed; tier ladders added
- `pipeline/tests/test_prompt_v3.py` — asserts tier ladders, not prescriptive anchors
- `scripts/eval_metric_v4.py` — parameterized `--out-attempt` so the same
  script serves attempt 06 and attempt 07

## Outputs

- `attempts/07_no_anchors/outputs/eval60/single/{id}.json` — 60 responses
- `attempts/07_no_anchors/outputs/eval60_log.txt`
- `attempts/07_no_anchors/prompts/example_*.txt` — dry-run reference (3 prompts)
