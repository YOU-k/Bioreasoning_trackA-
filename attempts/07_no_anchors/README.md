# Attempt 07 — Single-call, no prescriptive anchors

## Why

Attempt 06's two "free levers" backfired:

- **R4** "default P_up ≈ 62" → 26/60 rows (43%) returned exactly 62 → AUROC
  ties killed DIR ranking.
- **R2** "lean P_DE toward 15-25 when evidence is weak" → P_DE compression
  at the low end killed DE ranking.

The single-call architecture itself was fine (60/60 parse, 4k token budget
respected). The lesson: **printed integers in the prompt act as escape
hatches**, not Bayesian priors.

## Change vs Attempt 06

| Component | Attempt 06 | Attempt 07 |
|---|---|---|
| Architecture | single call → P_DE + P_up_given_DE | **unchanged** |
| Retrieval | analog + contrast (k_a=5, k_c=5, paper §3.4.2) | **unchanged** |
| 3-seed fusion (runner) | logit-average q + r separately | **unchanged** |
| R1 plausibility ≠ prediction (qualitative) | present | **kept** |
| R3 BMDM context rule (qualitative) | present | **kept** |
| R5 Replogle direction transfer (qualitative) | present | **kept** |
| R6 two integers are independent (decoupling) | present | **kept** |
| R2 "lean P_DE toward 15-25" | present | **REMOVED** |
| R4 "default P_up ≈ 62" | present | **REMOVED** |
| DE tier ladder (90-100 / 70-89 / …) | absent | **restored from attempts 04/05** |
| DIR tier ladder (90-100 / 70-89 / …) | absent | **restored from attempts 04/05** |

The tier ladders describe **what evidence corresponds to each band**, not
where the model should default. The model has to locate itself on the
ladder — there's no printed default value to copy.

## Hypothesis

By replacing prescriptive defaults with descriptive tier anchors:

- The "I don't know" rows will spread across the middle bands instead of
  collapsing onto a single integer → fewer AUROC ties.
- The model's strong-signal calls (already 86% precision at P_DE ≥ 70 in
  attempt 06) should be preserved.
- DE-AUROC should recover toward attempt 04/05's 0.60 band; DIR-AUROC
  should approach attempt 04/05's 0.665 band.

## Validation gate (same as attempt 06)

| Outcome | Verdict |
|---|---|
| Combined ≥ 0.635 | **Pass** — single-call matches the two-prompt research surface. Ship as the Track-A submission path. |
| Combined ∈ [0.60, 0.634] | Acceptable. Single-call costs a small fraction relative to two-prompt; that's the price of compliance. |
| Combined < 0.60 | **Fail** — single-call is materially worse. Investigate before further iteration. |

## Inputs

Unchanged from attempt 06:
- `data/train.csv`, `data/test.csv`
- `data/replogle_de.pkl`, `data/mouse_to_human_ortholog.json`
- `data/kg_index/`, `data/gene_desc.json`
- `pipeline/{retrieve_examples,bmdm_context,gene_desc,replogle_prior,kg_retrieval}.py`

Modified:
- `pipeline/prompt_builder_v3.py` (R2 + R4 removed, tier ladders restored)
- `pipeline/tests/test_prompt_v3.py` (asserts tier ladders, not prescriptive anchors)
- `scripts/eval_metric_v4.py` (output dir switched to `attempts/07_no_anchors/`)

## Outputs

- `attempts/07_no_anchors/outputs/eval60/single/{id}.json` — 60 single-call responses
- `attempts/07_no_anchors/outputs/eval60_log.txt`
- `attempts/07_no_anchors/prompts/example_*.txt` — dry-run reference
- `attempts/07_no_anchors/result.md` — final numbers + verdict
