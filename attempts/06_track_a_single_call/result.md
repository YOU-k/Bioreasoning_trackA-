# Attempt 06 — result

**Date**: 2026-06-09
**Status**: **FAIL** per the pre-registered validation gate (Combined < 0.60).

## Headline

On the same 60 random train rows (seed=123) used to grade attempts 03 / 04 / 05,
DeepSeek-Reasoner with the single-call Track-A-compliant prompt:

| Metric | Attempt 03 | Attempt 04 | Attempt 05 | **Attempt 06** | Δ vs 05 |
|---|---|---|---|---|---|
| DE-AUROC | 0.654 | 0.601 | 0.610 | **0.559** | **-0.051** |
| DIR-AUROC | 0.451 | 0.679 | 0.665 | **0.611** | -0.054 |
| **Combined** | 0.552 | **0.640** | 0.637 | **0.585** | **-0.052** |

60 / 60 rows parsed cleanly (`parse_status == 'ok'` everywhere). Pipeline
not broken — the prompt itself is the issue.

## What went wrong

The two "free levers" we added on top of the architectural pivot both
backfired:

### R4 "default P_up_given_DE ≈ 62" → tied predictions kill DIR-AUROC

Roughly **26/60 rows (43%) returned exactly P_up = 62**. Track-A-compliant
LLMs treated the prior as a *lazy escape* rather than a soft Bayesian
default: when direction evidence wasn't strongly one-sided, the model
copied the printed number instead of producing a graded estimate. AUROC
gives no credit for ties, so the DIR signal collapsed in the up/down
rows that received the default value.

### R2 "lean P_DE toward 15-25 when evidence is weak" → compression at low end kills DE-AUROC

Nearly every "unclear" row landed at P_DE ∈ {15, 18, 20, 25}, regardless
of the true label. True `up` (e.g. `Becn1_Creg1`, `Myd88_Osbpl8`,
`Snx13_Syngr1`) and true `none` (e.g. `Plrg1_Dock10`, `Arpc2_Mrc1`) both
piled into the same bucket. Relative ranking between true DE and true
none vanished. DE-AUROC dropped 0.610 → 0.559.

### What still worked (the LLM is not the problem)

When the model went high (P_DE ≥ 70, 7 rows), **6/7 were true DE** (86%
precision at the top). The model can identify strong signal cleanly; it
was the prescriptive anchor language that turned mid-strength signal into
a defaulted value.

## Lesson

**Prescriptive numerical anchors in the prompt act as escape hatches, not
as Bayesian priors.** If we want to encode the train direction prior
(up:down ≈ 2.2:1) or anti-storytelling caution, it must happen **off-prompt**
— either as a calibration / shrinkage step in `pipeline/runner.py`, or as
qualitative rules without a specific integer the model can latch onto.

## What carries forward (still valid)

- **Single-call architecture is Track-A compliant** and the parser handles
  two integers in one response cleanly (60/60 parse success).
- **Anti-storytelling guard (R1)** — qualitative wording is fine; "plausibility
  ≠ prediction" doesn't hand the model a number to copy.
- **Decoupling rule (R6)** — telling the model the two integers are
  independent is good practice and didn't hurt.
- **Logit-fusion in `runner.py`** is the right shape for 3-seed aggregation
  and is independent of prompt design — keep it.

## Verdict

Single-call architecture is **viable** (parser + token budget all fine).
**Numerical defaults in the prompt are not.** Attempt 07 should keep
attempt 06's structure but strip out R2's "15-25" anchor and R4's "62"
default; either revert to attempt 04/05's tier-anchor wording (90-100,
70-89, …) where the anchors describe what each tier *means* but don't
prescribe where the model should land, or push the prior into runner-side
post-hoc shrinkage.

## Inputs

Unchanged from attempt 05 + new builder:
- `pipeline/prompt_builder_v3.py` — single-call builder (this attempt)
- `pipeline/runner.py` — added `fuse_q_r_logit()` (this attempt, still applicable)
- `scripts/eval_metric_v4.py`

## Outputs

- `attempts/06_track_a_single_call/outputs/eval60/single/{id}.json` — 60 responses
- `attempts/06_track_a_single_call/outputs/eval60_log.txt` — eval log
- `attempts/06_track_a_single_call/prompts/example_*.txt` — dry-run references
