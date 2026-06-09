# Attempt 06 — Track-A compliant single-call q/r prompt

## Why

Track-A rule (`project_info/overview.md:64,98,104`): submission allows
**3 total calls per question** (one per seed × seeds 42/43/44). Attempts
04 and 05 use 2 prompts per seed × 3 seeds = 6 calls per question →
**non-compliant**.

This attempt collapses the DE + DIR research surface into one prompt
that emits both `P_DE` and `P_up_given_DE` from a single LLM call.

## Hypothesis

Three independent levers should be folded into the merge:

1. **Single-call output of two integers (q, r)** — required by Track A
   rule and matches the GPT 2026-06-09 discussion (`discussion/next_paradigm_gpt.md`)
   recommendation to decouple `q=P(DE)` and `r=P(up|DE)` rather than
   3-class softmax.
2. **Direction prior 62, not 50** — train DE distribution has up:down ≈
   2.2:1 (4154 evaluable rows). The DIR prompt currently defaults to 50
   when evidence is weak, which is biased against the true base rate.
   Bake "default `P_up ≈ 62` when direction evidence is weak" into the
   reasoning protocol.
3. **Anti-storytelling guard** — explicit prompt language:
   "plausibility ≠ prediction; treat absence of pert-specific evidence
   as evidence FOR `none`, not as fallback to a plausible mechanism".
   Pre-empts the VCWorld failure mode where LLMs find a mechanism for
   almost any pair.

## Architecture diff vs attempt 05

| Component | Attempt 05 | Attempt 06 |
|---|---|---|
| LLM calls per query | 2 (DE prompt + DIR prompt) | **1** (combined) |
| Output | one integer per call | **two** integers per call |
| Retrieval | analog + contrast (k_a=5, k_c=5, paper §3.4.2) | same |
| BMDM context paragraph | full | trimmed to the load-bearing parts (cuts ~200 tokens) |
| Reasoning protocol | 5 steps × 2 prompts = 10 | **6 steps in one prompt** (3 for DE, 3 for DIR) |
| Direction prior | implicit 0.5 | **explicit 0.62** in step 6 |
| Anti-storytelling guard | none | **explicit rule line** at top of protocol |
| 3-seed fusion (runner) | mean of p_up, p_down | **logit-average of q and r separately**, then p_up=qr, p_down=q(1-r) |

## Inputs (reproducibility)

Unchanged from attempt 05:
- `data/train.csv`, `data/test.csv`
- `data/replogle_de.pkl`, `data/mouse_to_human_ortholog.json`
- `data/kg_index/`, `data/gene_desc.json`
- `pipeline/{retrieve_examples,bmdm_context,gene_desc,replogle_prior,kg_retrieval}.py`

New / modified:
- `pipeline/prompt_builder_v3.py` (new, single-call builder)
- `pipeline/runner.py` (logit-average 3-seed fusion)
- `pipeline/tests/test_prompt_v3.py` (new tests)
- `scripts/eval_metric_v4.py` (new eval runner)

## Outputs

- `attempts/06_track_a_single_call/outputs/eval60/single/{id}.json` — 60 single-call responses
- `attempts/06_track_a_single_call/result.md` — final numbers + verdict

## Validation gate

On the same 60 random train rows (seed=123) used to grade attempts 03 / 04 / 05:

| Outcome | Verdict |
|---|---|
| Combined ≥ 0.635 | **Pass** — single-call is competitive; ship as the Track-A submission path |
| Combined ∈ [0.60, 0.634] | Tie. Single-call sacrifices a bit for compliance — acceptable since two-prompt isn't submittable. |
| Combined < 0.60 | **Fail** — single-call materially worse. Either prompt design needs more work, or the cost of compliance is higher than expected. Consider partial fallback (e.g., one prompt with explicit Yes/No softmax + direction). |

The DE-AUROC specifically: 0.61 → if we hit ≥ 0.62, the direction prior +
anti-storytelling guard are doing real work; if we slip back to 0.55, the
single-call format is too tight for proper DE reasoning.
