# Reflections: first LB submission landed at 0.510 vs probe60 0.643

**Date**: 2026-06-12. Discovered through Kaggle API after user asked
"我kaggle账号是什么？在哪里" — found 4 submissions made that day, 1
accepted, score 0.510 (rank 31/34). Captures everything we learned in
that ~1-hour debugging window.

---

## 1. What happened (timeline)

| Time UTC | Event |
|---|---|
| 2026-06-11 07:59 | YOU-k creates branch `sync/a12-harmony`: wires `assemble_submission` to `prompt_builder_v3`, adds Harmony chat format, **reverts hybrid defaults to α=0.4, nf=0.62** (A11 era) |
| 2026-06-12 03:10 | Submission #1 (`submission_a15_local_vllm.zip`) → **REJECTED**: missing required column `prompt_tokens` |
| 2026-06-12 03:11 | Submission #2 (`submission.csv`) → REJECTED, same reason |
| 2026-06-12 03:18 | Submission #3 (`submission_a15_local_vllm_v2.zip`) → REJECTED: "Prompt-token limit exceeded: max 4,096, but submission reports 6,066" (prompt.txt too long) |
| 2026-06-12 03:26 | Submission #4 (`submission_a15_local_vllm_v3.zip`) → **ACCEPTED, public score 0.510** |
| 2026-06-12 03:40 | YOU-k creates branch `sync/a15-submit-v3` with the schema fix that made #4 accept (commit was AFTER the submission, presumably documenting the state) |
| 2026-06-12 04:00ish | User asks about their Kaggle account; I find the 0.510 score and dig into root causes |

## 2. Schema discrepancy — `project_info/overview.md` is wrong

`project_info/overview.md:83` documents the submission has a single
token column:

```
| tokens_used | int | 0 | Sum of input + output tokens across all 3 calls |
```

But Kaggle's actual validator requires **three token columns** (per
v3 submission that was accepted):

| Column | Semantics | Validated against |
|---|---|---|
| `prompt_tokens` | **per-call** prompt tokens (single prompt, not summed) | 4,096 cap |
| `completion_tokens` | per-call average completion tokens | not validated |
| `tokens_used` | sum of (prompt + completion) across all 3 seeds (legacy) | not validated |

**Lesson**: official competition docs in `project_info/` (pulled at repo
init) can be incomplete or stale. Trust submission errors as ground
truth. **The Kaggle API submission errors are the definitive schema
oracle**, not the human-readable rules page.

This caused **two follow-on errors I made on main**:
- I renamed `tokens_used` → `prompt_tokens` in `pipeline/runner.py`
  setting the value to *sum across seeds* (~7000). That would have
  failed Kaggle's 4,096 validation again on next submission.
- I shipped the change with green dry-run validation, false confidence.

Fix landed in this commit batch: 16-column schema with `prompt_tokens`
per-call, `completion_tokens` per-call avg, `tokens_used` as the
legacy sum.

## 3. prompt.txt token cap — different from per-row prompt cap

Track A's 4,096-token rule applies to **two things**:

1. **Per-row inference prompt** (the actual prompt you send to GPT-OSS).
   Our A15 SHIP runs at ~1,886-2,150 per row. Fine.
2. **The `prompt.txt` packaged in the submission zip**, validated against
   the same 4,096 cap. v2 was rejected because we packaged a fully-
   instantiated example prompt (~6,000 tokens with retrieval + priors).

Lesson: keep `prompt.txt` to the **static template skeleton** only —
header + rules + protocol + tier ladders + output format — using
`{pert}`/`{gene}` placeholders. That's ~1,475 tokens. Fixed in
`scripts/submission_dry_run.py:make_prompt_txt`.

## 4. Hybrid params regression — v3 used α=0.4 nf=0.62, not A15 SHIP

`sync/a12-harmony` (the base branch for v3) reverted
`hybrid_direction` defaults to A11-era values:

```diff
-                     replogle_prior, alpha: float = 0.45,
-                     non_full_default: float = 0.58) -> tuple[float, str]:
+                     replogle_prior, alpha: float = 0.4,
+                     non_full_default: float = 0.62) -> tuple[float, str]:
```

`sync/a15-submit-v3` then removed the `non_full_default` keyword from
the `assemble_submission` → `hybrid_direction` call site:

```diff
                 r_final, _src = hybrid_direction(
                     r_llm_final, row['pert'], row['gene'],
-                    assemble_submission._prior,
-                    alpha=hybrid_alpha,
-                    non_full_default=hybrid_non_full_default)
+                    assemble_submission._prior, alpha=hybrid_alpha)
```

So v3 ran with:
- `α = 0.4` (LLM weight in full-tier blend)
- `nf = 0.62` (non-full direction fallback)

A15 SHIP (what we tuned on probe60) was:
- `α = 0.45`
- `nf = 0.58`

Expected probe60 lift from A15 over A11: ~+0.018 Combined. Real on LB:
not directly measurable without re-submitting. But this is part of the
gap.

**Lesson**: branch divergence on the LLM server reverted main's tuning.
Need a tighter sync protocol or a single shared config file. Recommend:
factor hybrid params into a `config.py` constant block that all runners
import — eliminates accidental revert across branches.

## 5. The big mystery — LB 0.510 vs probe60 0.643 (-0.133)

The A15→A11 hybrid regression accounts for at most ~0.02. That leaves
~0.11 unexplained. Working hypotheses:

### Hypothesis A: GPT-OSS-120B output quality ≪ DeepSeek-Reasoner
- All our 20+ attempts were tuned on DeepSeek-Reasoner via API
- We never ran probe60 with GPT-OSS-120B locally to calibrate
- The Harmony chat format ("Reasoning: low", "Do not reveal scratch
  work, drafts, or chain-of-thought") may make GPT-OSS skip the
  structured A1-B2 reasoning protocol that DeepSeek follows reliably
- Result: parser hits fallback path more often → P_DE=0.45, P_up=0.50
  defaults → mass ties → AUROC near 0.5

### Hypothesis B: format failures specifically
- v3 inference output JSONs are on the LLM server; we don't have them locally
- Need to inspect parse_status distribution on a representative sample
- If "failed" rate is >30%, that alone could explain the gap

### Hypothesis C: probe60 was over-fitted
- 60 rows is small; α=0.45 nf=0.58 tuning had LOO std 0.008
- The +0.018 we attributed to the tuning may have been partly noise
- The 0.643 probe60 number itself may be a peak of a noisy estimator
- The true expected LB even with everything correct may be more like
  0.58-0.60

### Hypothesis D: Hagai prior actively hurts on real test
- We added Hagai based on probe60 evidence
- Probe60 may have correlated Hagai-covered rows with easy rows
- True test may have Hagai info on a different (less informative)
  subset
- A subset-specific issue we couldn't see on probe60

### What would disambiguate (in order of cost)
1. Get the v3 inference output JSONs from LLM server → check parse_status distribution. **Cheapest.**
2. Re-submit with the corrected main config (α=0.45, nf=0.58, fixed
   schema) → see how much of the gap closes.
3. Run probe60 locally with GPT-OSS-120B (need access to the model) → directly measure DeepSeek vs GPT-OSS gap on identical inputs.
4. Try a no-LLM TransPert-style baseline on the actual test set → set a floor.

## 6. Process lessons (for future projects)

1. **Don't trust documented schemas blindly.** Run a real submission
   early — even a baseline "all 0.5" submission — to validate the
   schema before investing weeks in modeling. We should have done this
   on day 1.

2. **Branch divergence is silent damage.** YOU-k's sync branches
   modified shipping defaults without main being notified. We need
   either:
   - A shared `config.py` for all hyperparams (single source of truth)
   - A required `python -c "from pipeline.runner import ASSEMBLE_CONFIG; print(ASSEMBLE_CONFIG)"` in the
     submission staging script that prints the actual config used.

3. **Tuning on a proxy LLM is risky.** All our 20 attempts used
   DeepSeek-Reasoner because it had API access. The actual submitting
   LLM is GPT-OSS-120B locally. Format adherence may differ
   dramatically. **Should have run an A15 SHIP smoke test with
   GPT-OSS-120B on 60 rows before claiming probe60 = 0.643 transfers.**

4. **Two-machine workflows multiply schema risks.** This machine
   (DeepSeek + dev) and the LLM server (GPT-OSS + inference) diverged
   on:
   - Submission schema (`tokens_used` vs `prompt_tokens` + `completion_tokens`)
   - Hybrid hyperparams (α 0.45 vs 0.4)
   - Prompt.txt size limit handling
   Each divergence cost a real submission slot or a 0.02 of LB.

5. **AUROC is rank-only — but real LLM systems are not.** Probe60 said
   0.643. The submission says 0.510. Both are honest measurements; they
   just measured different things (DeepSeek-Reasoner vs GPT-OSS-120B,
   probe60 distribution vs test distribution, α=0.45 vs α=0.4). When
   they disagree, the LB number is the truth for the competition.

## 7. Immediate action items (recorded for accountability)

- [x] Discover the LB 0.510 result
- [x] Identify the schema discrepancy (3 token columns, not 1)
- [x] Identify the hybrid param regression (v3 used A11 defaults)
- [x] Fix `pipeline/runner.py` to emit the 16-column schema
- [x] Fix `scripts/submission_dry_run.py` to validate against the
      16-column schema
- [x] Cap `prompt.txt` to template-only (under 4,096)
- [x] Restore A15 hybrid defaults (α=0.45, nf=0.58) on main
- [x] Write this reflections doc
- [x] Update `PROJECT_STATUS.md` with the LB landing finding
- [ ] User to coordinate next submission attempt on LLM server (using main's fixed pipeline + A15 hybrid params)
- [ ] Inspect v3 inference output JSONs for parse_status distribution
- [ ] If parse_status mostly OK → likely Hagai or GPT-OSS calibration issue → diagnostic round
- [ ] If parse_status mostly failed → fix the prompt template for GPT-OSS Harmony format adherence

## 8. What the literature says about this scenario

From `discussion/literature_synthesis_2026-06-11.md` §3:

> SUMMER (PerturbQA baseline): DE 0.58-0.65, DIR 0.62-0.66

LB 0.510 with parser failures is BELOW the SUMMER baseline — meaning the
problem is more likely **inference-pipeline failure** than **algorithm
ceiling**. A SUMMER-style baseline run with GPT-OSS-120B should land
around 0.60. Our 0.510 is 0.09 below that, suggesting something specific
to our pipeline (parser? prompt format? Hagai?) is hurting.

The good news: this is fixable engineering, not a fundamental ceiling.

---

**TL;DR**: LB 0.510 is below where it should be by ~0.10. Three causal
suspects: (a) GPT-OSS Harmony format breaking our prompt's A1-B2
structure, causing parser fallbacks; (b) v3 used regressed hybrid params
(α=0.4 not 0.45); (c) probe60 may have been a noisy estimator we
over-trusted. The cheapest next diagnostic is to inspect v3's inference
outputs for parse_status rates. The cheapest next remedial action is to
re-submit with the main-branch fix that restores A15 hybrid params and
emits the correct 16-column schema. User will coordinate from the LLM
server side.
