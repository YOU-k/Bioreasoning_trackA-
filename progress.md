# Progress log

Append-only. One block per completed attempt. Newest at the top.

---

## 2026-06-11 (after A16) · attempt 17 · Inject "balanced dataset" framing into R1 → counter-intuitive FAIL

User asked: why is LLM in "conservative mode" (P_DE mean 0.241 vs train
0.447) and can we use the distribution info from `discussion/analysis.md`
(train base rate 45% DE, up:down ≈ 2.2:1)?

**Hypothesis**: tell the LLM the dataset is intentionally balanced (~45%
DE per-pert sampling) so its biological prior of ~1-5% natural DE doesn't
bias it toward `none`. Reframe low P_DE band as needing "active
counter-evidence", not absence-of-evidence. NO prescriptive numerical
defaults (A06/A16 lesson respected).

**Result on probe60** (seed=789):

Distribution shift worked exactly as intended:
- P_DE mean: 0.241 → 0.411 (close to train 0.447)
- Rows at P_DE = 20: 22 → 11 (cluster halved)
- Top-5 P_DE values: spread across 20/55/40/35/60 (not just 20/15/25/35/10)

But AUROC went DOWN:

| Metric | A12 SHIP | A17 |
|---|---|---|
| DE-AUROC | 0.644 | 0.548 (-0.096) |
| Combined LLM-only | 0.592 | 0.508 (-0.084) |
| Combined hybrid | 0.643 | 0.577 (-0.066) |

**Counter-intuitive lesson**: Calibration ≠ AUROC improvement.

Why distribution-matching hurt:
- A12 SHIP's "conservative bias at 20" was actually preserving rank info.
  22 rows at P_DE=20 was a tied cluster, but they were mostly true `none`
  + uncertain rows that LLM correctly biased low.
- High-confidence DE rows ranked CLEANLY above this 20-cluster (70+).
- After spreading uncertain rows to the 35-60 middle band, true DE and
  true `none` rows MIXED in the new middle. High-confidence DE still
  ranked above (unchanged), but middle-band noise dragged AUROC down.

The compressed LLM output was BETTER for ranking even though worse for
calibration. AUROC only cares about ranking; monotonic shifts to match
calibration can introduce noise into the middle and hurt AUROC.

**Verdict**: revert R1 to A12 SHIP language. A15 SHIP stands.

**Latent use of train distribution info**: still potentially valuable
for downstream stacking / ensembling (where calibration matters) or as a
sanity check on submission output. Not directly usable in the prompt
without hurting AUROC.

See `attempts/17_balanced_framing/result.md`.

---

## 2026-06-11 (after A15) · attempt 16 · C: strong Replogle anchoring (FAIL) + D: Hagai DIR signal (no help)

User question: "is the runner hybrid post-processing of LLM output? Is
that fair under Track A?"

Rules check (`project_info/overview.md`):
- Line 87: "Final prediction_up/prediction_down ... exact aggregation rule is whatever your sample submission encodes"
- Line 96: "Allowed to train auxiliary models on any publicly available perturbation datasets"
- Line 111: "Allowed: retrieval from public data ... predictive models trained on public data"
- Line 112: "Not allowed: any LLM other than GPT-OSS-120B; training or fine-tuning ad-hoc models on the competition's own data"

The hybrid runner is compliant: Replogle is public, no ad-hoc model
trained on competition data. But user's spirit-of-the-rules instinct
prompts two alternatives:

### C: Strong R4 prompt anchoring with explicit logFC → P_up_given_DE mapping

| Variant | Pure LLM | + hybrid |
|---|---|---|
| **A12 SHIP (vague R4)** | **0.592** | **0.643** |
| A16 strong anchor | 0.560 (-0.032) | 0.596 (-0.047) |

**Failure mode**: A06 escape-hatch pattern, even worse:
- A12 SHIP: 29/60 rows at P_up=50 (48%)
- A16 strong anchor: 50/60 rows at P_up=50 (83%)

The conditional rule `logFC ∈ [-0.2, +0.2] → P_up ≈ 50` became the
LLM's blanket safe escape. DIR-AUROC LLM-only collapsed 0.540 → 0.478
due to AUROC tie penalty.

**Lesson reinforced** (3rd confirmation now: A06, A12-A, A16):
prescriptive numerical anchors in prompts ALWAYS become escape hatches,
even when conditional. R4 reverted to A12 SHIP wording.

### D: Hagai DIR signal in runner blend (3 variants on A12 SHIP outputs, no API)

| Variant | DE | DIR | Combined |
|---|---|---|---|
| **D0 baseline (A15 hybrid)** | 0.644 | 0.641 | **0.643** |
| D1: raw Hagai sign for non-full | 0.644 | 0.618 | 0.631 (-0.012) |
| D2: significant-Hagai-only sign | 0.644 | 0.607 | 0.625 (-0.018) |
| D3: lower α when Hagai strong | 0.644 | 0.641 | 0.643 (=) |

Confirms what the A11 audit already showed: **Hagai LPS direction does
NOT transfer to CRISPRi direction**. KD of inflammatory pathway
activators (Tlr4, Myd88) brings LPS-UP targets DOWN, flipping the sign.
Hagai stays as a DE-magnitude-only signal.

### Verdict

Neither C nor D improves on A15 SHIP. The hybrid runner remains the
correct post-processing — Track-A compliant + empirically better than
prompt-only anchoring on this probe.

Ship A15 unchanged.

A + B deferred to plan P-future (logit-space blend + per-row adaptive α).

See `attempts/16_strong_anchor/result.md`.

---

## 2026-06-11 (much later) · attempt 15 · Hybrid α + nf_prior sweep (Task 7) and k_a/k_c retrieval budget (Task 5)

### Task 7: Hybrid runner alpha + non-full-prior sweep (no API spend)

Sweep on the A12 SHIP outputs to tune `hybrid_direction()` defaults.
Tight 2D grid revealed a robust local max at α ∈ [0.40, 0.50], nf_prior = 0.58:

```
alpha   nf=0.56  nf=0.58  nf=0.60  nf=0.61  nf=0.62
 0.30    0.625    0.632    0.632    0.623    0.623
 0.35    0.626    0.634    0.634    0.625    0.625
 0.40    0.626   *0.643*   0.625    0.625    0.625
 0.45    0.626   *0.643*   0.634    0.625    0.625
 0.50    0.626   *0.643*   0.634    0.634    0.625
 0.55    0.626    0.626    0.634    0.634    0.634
```

LOO cross-validation: in-sample 0.643, LOO mean 0.6427 ± 0.008.
+0.018 over the old (α=0.40, nf=0.62) at >2× LOO std → real signal.

Ship updated: `hybrid_direction(α=0.45, nf=0.58)`.

### Task 5: k_a / k_c retrieval budget ablation (2 new evals)

Inverted U-shape — both extremes hurt:

| Variant | DE | DIR (LLM) | Combined LLM | + hybrid |
|---|---|---|---|---|
| k=3+3 | 0.525 | 0.447 | 0.486 | 0.567 |
| **k=5+5 (SHIP)** | **0.644** | **0.540** | **0.592** | **0.643** |
| k=10+10 | 0.517 | 0.493 | 0.505 | 0.556 |

k=3+3 (-0.076 hybrid): too thin, not enough structural diversity.
k=10+10 (-0.087 hybrid): too many → attention dilution (A14 pattern).

**k=5+5 stays the ship default.**

### Cumulative improvement on probe60

| Stage | Combined |
|---|---|
| A07 baseline | 0.466 |
| A11 (+ Hagai prompt + hybrid runner α=0.4) | 0.613 |
| A12 SHIP (+ drop BMDM context) | 0.625 |
| **A15 SHIP (+ tuned hybrid α=0.45, nf=0.58)** | **0.643** |

Top-4 public LB band: 0.628 – 0.650. **probe60 estimate now inside the LB band.**

### Files

- `scripts/sweep_hybrid_alpha.py` (Task 7 sweep + LOO)
- `scripts/eval_metric_v4.py` (--k-a / --k-c flags)
- `pipeline/runner.py` (`hybrid_direction(α=0.45, nf=0.58)` defaults)
- `attempts/15_retrieval_budget/{README,result}.md`

---

## 2026-06-11 (still later) · attempt 14 · Per-example Hagai + Replogle enrichment — FAIL

Hypothesis from A12/A13 heuristic: adding active per-example data the LLM
can compare against the query should be net positive. Tested by enriching
each evidence case from plain `pert=X, target=Y. Result: Yes/No` to
`... → Yes/No. [Hagai pert |logFC|=A; Hagai target |logFC|=B; Replogle logFC=C]`.

Token cost was minimal (+62 tokens total).

**Result on probe60 (seed=789)**:

| Variant | DE | DIR | LLM Combined | + hybrid |
|---|---|---|---|---|
| **A12 SHIP (plain)** | **0.644** | 0.540 | **0.592** | **0.625** |
| A14 enriched | 0.534 | 0.542 | 0.538 (-0.054) | 0.605 (-0.020) |

DE-AUROC dropped 0.110. The likely failure mode is attention dilution:
10 bracket-annotated example lines with per-case Hagai/Replogle numbers
distract the LLM from the query's own Hagai + Replogle blocks downstream,
and may also induce in-context regression that miscalibrates the query
prediction.

**Updated design heuristic**:

| Boilerplate type | Effect | Example |
|---|---|---|
| Passive knowledge dump | net negative | BMDM context paragraph (A12) |
| Active reasoning instruction | net positive | Decision rules R1-R5 (A13) |
| Active output structure | net positive | Reasoning protocol A1-B2 (A13) |
| **Active per-example data** | **net negative** | Hagai/Replogle inline per case (A14) |

The signal-density vs attention tradeoff: more detail per context block
may dilute the LLM's attention to the query's own features. Keep examples
thin; surface priors via dedicated blocks downstream.

**Ship A12 SHIP unchanged.** `enrich_examples: bool = False` is the
default — flag retained for future negative-result reproducibility.

See `attempts/14_enriched_examples/result.md`.

---

## 2026-06-11 (later) · attempt 13 · Probe whether Decision rules + Reasoning protocol are also boilerplate

Continued user-prompted ablation of hand-written blocks in the prompt.
Two candidates left after A12:

- **Decision rules R1-R5** (~470 tokens): "plausibility ≠ prediction",
  "Hagai magnitude only", "Replogle direction transfer", etc.
- **Reasoning protocol A1-B2** (~290 tokens): forced step-by-step.

Three new probe60 runs:

| Variant | DE | DIR (LLM) | LLM Combined | + hybrid Combined |
|---|---|---|---|---|
| **A12 SHIP (rules + protocol)** | **0.644** | 0.540 | **0.592** | **0.625** |
| no Decision rules | 0.553 | 0.467 | 0.510 (-0.082) | 0.572 (-0.053) |
| no Reasoning protocol | 0.549 | 0.395 | 0.472 (-0.120) | 0.568 (-0.057) |
| no rules + no protocol | 0.502 | 0.487 | 0.495 (-0.097) | 0.564 (-0.061) |

**Both blocks are load-bearing**. Effect sizes (0.05-0.12 Combined) exceed
the ~0.04 sampling-noise band on 60 rows. Hybrid runner cushions the loss
on DIR (Replogle blend handles most of DIR signal) but DE-AUROC drops
0.644 → 0.55ish across all ablations and drags Combined down.

**Verdict**: keep both. A12 SHIP remains the recommended config.

**Design heuristic** from A12 + A13:

| Boilerplate type | Effect | Example |
|---|---|---|
| **Passive** knowledge dump | net negative | BMDM cell context paragraph |
| **Active** reasoning instruction | net positive | Decision rules R1-R5 |
| **Active** output structure | net positive | Reasoning protocol A1-B2 |

Prefer instructions that change HOW the LLM thinks. Drop facts the LLM
already knows. Default keep R1-R5 + A1-B2; drop hand-written backgrounders.

**Files**:
- `pipeline/prompt_builder_v3.py`: `include_decision_rules` and `include_reasoning_protocol` flags (both default True); `_TIER_LADDERS` split out from `_PROTOCOL` so the ladders are always included even when reasoning protocol is ablated.
- `scripts/eval_metric_v4.py`: `--no-decision-rules` and `--no-reasoning-protocol` ablation flags.
- `scripts/compare_a13_variants.py`: 4-way comparison utility.
- `attempts/13_minimal_prompt/{README,result}.md` + outputs/

See `attempts/13_minimal_prompt/result.md`.

---

## 2026-06-11 · attempt 12 · Drop the hand-written BMDM context paragraph

User audited the A11 prompt and flagged that much of the ~2630 tokens is
hand-written boilerplate, not query-specific. Two candidates for ablation:

- **A**: Hagai prompt block printed "→ UP (strong) under LPS" — but R3
  already says direction does NOT transfer to CRISPRi. Strip direction
  wording, show magnitude only?
- **C**: 723-token `## Cell context (BMDM)` paragraph in
  `pipeline/bmdm_context.py` is hand-written, identical every row. Does
  it actually help?

2×2 ablation on probe60_rare_gene (seed=789):

| Variant | DE | DIR (LLM-only) | Combined (LLM-only) | Combined (+ hybrid) |
|---|---|---|---|---|
| A11 baseline (BMDM yes, dir wording yes) | 0.599 | 0.480 | 0.539 | 0.613 |
| A only (BMDM yes, magnitude wording) | 0.522 | 0.507 | 0.515 | 0.574 |
| **C only (BMDM no, dir wording)** ✅ | **0.644** | **0.540** | **0.592** | **0.625** |
| A + C (BMDM no, magnitude wording) | 0.618 | 0.520 | 0.569 | 0.620 |

**Decomposition** (effects are roughly additive):
- A (Hagai magnitude wording): -0.022 to -0.039 Combined. The LLM was
  using the direction text as a DE feature; stripping it dropped
  DE-AUROC 0.599 → 0.522 (-0.077). Net negative.
- C (drop BMDM context): +0.012 to +0.053 Combined. 723 fewer prompt
  tokens lifts both DE and DIR on the LLM-alone surface.

**Ship C-only**: keep Hagai direction wording (R3 caveat already says don't
copy direction); drop the BMDM context paragraph. New numbers:

| Metric | A11 baseline | **A11 + C-only (SHIP)** | Δ |
|---|---|---|---|
| LLM-only Combined | 0.539 | **0.592** | +0.053 |
| LLM + hybrid Combined | 0.613 | **0.625** | +0.012 |
| Prompt tokens (typical) | 2629 | **1886** | -28% |

Changes shipped:
- `pipeline/prompt_builder_v3.py`: `include_bmdm_context: bool = False` (was True)
- `pipeline/tests/test_prompt_v3.py`: 7/7 pass (added `test_bmdm_context_paragraph_off_by_default`)
- `scripts/eval_metric_v4.py`: `--with-bmdm-context` opt-in flag (was `--no-bmdm-context` opt-out)
- `scripts/compare_a11_variants.py`: 4-way comparison utility

The 28% token savings unlock budget for future enrichment (Tahoe / Kang /
Perturb_KHP signals; richer evidence-case rendering). See
`attempts/12_cleaner_prompt/result.md`.

---

## 2026-06-09 (recovery) · attempt 11 · Hagai mouse-BMDM LPS prior + runner-side Replogle DIR blend

Combined the two missing pieces identified by attempts 08/09/10:
1. The prompt only surfaced **human cross-species** direction (Replogle), so the
   LLM kept overriding it with weak mechanism guesses.
2. The runner did not exploit the strongest direction signal we have on full-
   tier rows (Replogle direct ortholog logFC).

**Added a new signal source** — `/data2/lanxiang/data/Task3_data/Hagai.h5ad`
(mouse BMDM stimulated with LPS for 6h vs ctrl, 15,053 mouse cells). Built
per-gene logFC + Bonferroni p_adj lookup, surfaced in the prompt as a
mouse-native primary prior.

**Added runner-side hybrid direction**:
```
r_full   = 0.4 * r_LLM + 0.6 * sigmoid(3 * Replogle.logfc)   # 55% of test rows
r_other  = 0.62                                              # train prior up:down ≈ 2.2:1
```

**Result on the same 60 rare-gene probe (seed=789)**:

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| A07 (no Hagai, no blend) | 0.449 | 0.482 | 0.466 |
| Pure Hagai+Replogle composite (no LLM) | 0.531 | 0.569 | 0.550 |
| A11 prompt only (no blend) | 0.599 | 0.480 | 0.539 |
| **A11 + hybrid runner** | **0.599** | **0.627** | **0.613** |

**+0.147 Combined over the previous Track-A compliant best.** Single-call
architecture preserved, Track-A compliant (3 calls per question).

Hagai in the prompt fixes DE (0.449 → 0.599); runner-side Replogle blend
fixes DIR (0.480 → 0.627). Both levers necessary; either alone underperforms.

**Sanity checks**:
- Hash-jitter on the 0.62 prior tested across 10 salts: mean Combined 0.616
  ± 0.018. Marginal lift over the constant 0.62 (+0.003). Not robust; not
  enabled.
- The same hybrid recipe applied to A07 eval60 outputs gives Combined 0.516,
  WORSE than pure A07's 0.623 on eval60. Confirms hybrid is a
  **test-condition lever** — eval60 had gene-prior leakage the LLM was riding,
  which the hybrid replaces; test data has no such leakage, so the hybrid
  is the right move.

**Expected Track-A LB**: probe60 signal-coverage distribution matches
test almost exactly (T0/T1/T3 share = 55/35/8% vs 54/37/9%). Expected test
Combined **≈ 0.55-0.61**, within 0.02-0.07 of the top-4 public LB band
(0.628-0.650) on a **Track-A-compliant single-call architecture**.

**Files added/changed**:
- `data/hagai_lps_prior.json` (6,619 mouse genes, built by `scripts/build_hagai_prior.py`)
- `pipeline/hagai_prior.py` (new loader module)
- `pipeline/prompt_builder_v3.py` (Hagai block added, R3/R4 rules rewritten)
- `pipeline/runner.py` (`hybrid_direction()` + integration in `assemble_submission`)
- `scripts/build_hagai_prior.py`
- `scripts/ablate_replogle_blend.py`
- `attempts/11_hagai_in_prompt/{README,result}.md` + outputs/

**Recommendation**: ship `pipeline/prompt_builder_v3.py` + `runner.assemble_submission()` (with `apply_hybrid_direction=True`, default) as the Track-A submission pipeline.

See `attempts/11_hagai_in_prompt/result.md`.

---

## 2026-06-09 (definitive) · attempt 09 · Rare-gene probe confirms: attempt 07 fails on test condition

Followed up the eval60-leakage finding with a real test-mimic probe: 60
train rows where the readout gene appears 2-4× in train (vs 4-10+ in
eval60), stratified to match eval60's label distribution (23 up / 12 down
/ 25 none, seed=789).

**Result on probe60_rare_gene with attempt 07 single-call prompt**

| Metric | eval60 (popular genes) | **probe60 (rare genes, test-like)** | Δ |
|---|---|---|---|
| DE-AUROC | 0.601 | **0.449** | -0.152 |
| DIR-AUROC | 0.645 | **0.482** | -0.163 |
| **Combined** | **0.623** | **0.466** | **-0.157** |

Combined = **0.466 is below random (0.500)**. Attempt 07 actively
mis-ranks these rows.

Baselines on the same probe60 (for context):
- Gene-only (cheats via same-gene rows): DE=0.117 DIR=0.623 Combined=0.370
- Pert-only (cheats via same-pert rows): DE=0.143 DIR=0.766 Combined=0.455
- Random: 0.500

Attempt 07 ≈ pert-only baseline on this probe — but pert-only cheats with
~19 same-pert neighbors per row that DON'T exist on test (test perts also
unseen). So attempt 07's expected test Combined is likely **0.46-0.50**,
not the 0.62 eval60 number suggested.

**This confirms the user's intuition from 2026-06-09**: "不要关注这个小的
gap了，这是之前误打误撞的，有可能是误差". The 0.014 Combined gaps between
A04 / A05 / A07 on eval60 were 100% leakage band noise. None of the
previous attempts have been shown to actually beat random on test
conditions.

**Failure mode**: P_DE collapses into [15, 25] and P_up into [45, 60] for
the majority of rows. When the gene is obscure (Riken IDs, lncRNAs, no
ortholog, no KG pathway), the prompt has no signal to anchor on and the
LLM produces a default-band guess. This is exactly GPT discussion §1.5's
"plausibility is not prediction" failure mode.

**Strategic implication for Track A**: do NOT submit attempt 07. Expected
LB ≈ 0.47-0.50. Need paradigm change before any GPT-OSS-120B spend.

**Three honest next moves** (in plan.md):
1. Cheap: verify A04 / A05 also fail on probe60 (rule out reviving them).
2. Cheap: two-tier prediction — LLM on high-info rows, training prior on
   low-info rows. The 0.5 floor on Tier B can lift Combined from 0.466.
3. Bigger: pivot to GPT discussion's CORE-style same-readout contrastive
   evidence + signed pathway features.

See `attempts/09_rare_gene_probe/result.md`.

---

## 2026-06-09 (final) · attempt 08 · Baseline audit — eval60 was leakage-contaminated

Ran gene-only, pert-only, and gene+pert baselines on the same 60-row probe
(seed=123). Two strategic findings that change the priority queue:

**DE is real, DIR is contaminated.**

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| Random | 0.409 | 0.583 | 0.496 |
| Gene-only baseline | 0.000 | **0.746** | 0.373 |
| Pert-only baseline | 0.255 | 0.683 | 0.469 |
| Gene+Pert hybrid | 0.123 | **0.817** | 0.470 |
| **Attempt 07** | **0.601** | 0.645 | 0.623 |

- **Attempt 07 DE-AUROC = 0.601** is real reasoning. Gene-only DE is 0.000
  (anti-correlated with label thanks to the competition's per-pert negative
  sampling). Disagreement audit: in 31/31 rows where attempt 07 and gene-only
  disagree on the DE call, attempt 07 is correct.
- **Attempt 07 DIR-AUROC = 0.645 LOSES to gene-only baseline (0.746)** and
  to gene+pert hybrid (0.817). The LLM is destroying information that a
  5-line lookup gives for free.

**eval60 has gene-prior leakage that test set does NOT have.**

Stratified DIR-AUROC by `n_same_gene_in_train` (excluding query pert):

| Bucket | n_rows | Attempt 07 DIR | Gene-only DIR |
|---|---|---|---|
| Low gene-prior (1-3 neighbors) | 9 | **0.438** | 0.625 |
| High gene-prior (≥11 neighbors) | 24 | 0.741 | 0.787 |

Test rows have **zero** same-gene neighbors (double-disjoint split).
The bucket that matches the test condition is "low gene-prior", where
attempt 07 DIR is sub-random (0.438). Estimated attempt-07 DIR-AUROC on
real test ≈ 0.45-0.50, NOT 0.645.

**The 0.014 Combined gap between A04 / A05 / A07 was inside the leakage
band on DIR**. Those attempts were not actually ranking better against
each other on the data structure that matters for test.

**Strategic shift**:

- Do NOT ship attempt 07 prompt as the Track-A submission until we have
  a double-disjoint validation number.
- DE reasoning is the asset to protect (0.601 is real, room to push higher).
- DIR is the bottleneck on unseen genes; mechanism reasoning alone doesn't
  beat gene-typical-direction lookup, and that lookup is unavailable at test.

See `attempts/08_audit_baselines/result.md`.

---

## 2026-06-09 (still later) · attempt 07 · Single-call without anchors — ACCEPTABLE, ship

Stripped attempt 06's two prescriptive numerical anchors (R2 "lean toward
15-25" and R4 "default 62") and restored attempt 04/05's tier-anchor
ladders (90-100 / 70-89 / …) for both P_DE and P_up_given_DE. Tiers
describe what evidence corresponds to each band; they don't tell the
model where to default. Architecture unchanged: single LLM call → both
integers; analog+contrast retrieval; logit-fused 3-seed runner.

**Result on the same 60 train rows (seed=123)**

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| Attempt 03 (one prompt) | 0.654 | 0.451 | 0.552 |
| Attempt 04 (two prompts, random labels) | 0.601 | 0.679 | **0.640** |
| Attempt 05 (two prompts, real labels) | 0.610 | 0.665 | 0.637 |
| Attempt 06 (single call + prescriptive anchors) | 0.559 | 0.611 | 0.585 |
| **Attempt 07 (single call + tier ladders)** | **0.601** | **0.645** | **0.623** |

Combined +0.038 vs attempt 06; -0.014 vs the best non-compliant attempt 05.
That 0.014 is the documented cost of Track-A compliance (3 calls per
question instead of 6).

**Per pre-registered gate**: 0.623 ∈ [0.60, 0.634] → ACCEPTABLE. Ship.

**Failure-mode reduction**: rows defaulting to a single P_up integer
dropped from 26/60 (A06, P_up=62) to 17/60 (A07, P_up=50). Still some
ambiguous-direction clustering at the band midpoint, but less severe.

**Remaining loss sources** (out of scope for shipping):
- ~17 rows tied at P_up=50 give up DIR ranking signal — could fix with
  post-hoc shrinkage in `runner.py` toward the train prior 0.62.
- A few high-confidence direction flips (`Dph3_Hmox1`, `Cct5_Tuba1c`)
  suggest single-LLM direction calls plateau here without external
  signed-pathway features.

**Recommendation**: ship `pipeline/prompt_builder_v3.py` as the Track-A
submission prompt with seeds 42/43/44 against all 1,813 test rows.

See `attempts/07_no_anchors/result.md`.

---

## 2026-06-09 (later) · attempt 06 · Single-call Track-A prompt — FAIL

Collapsed attempt-05's DE + DIR pair into a Track-A-compliant single-call
prompt that emits both `P_DE` and `P_up_given_DE` in one response. Added two
"free levers" suggested by `discussion/next_paradigm_gpt.md`: direction prior
(default P_up ≈ 62 from train up:down ≈ 2.2:1) and an anti-storytelling
guard ("lean P_DE toward 15-25 when evidence is weak"). Both backfired.

**Result on the same 60 train rows (seed=123)**

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| Attempt 03 (one prompt) | 0.654 | 0.451 | 0.552 |
| Attempt 04 (two prompts, random labels) | 0.601 | 0.679 | **0.640** |
| Attempt 05 (two prompts, real labels) | 0.610 | 0.665 | 0.637 |
| **Attempt 06 (single call + prescriptive anchors)** | **0.559** | **0.611** | **0.585** |

**Failure mode**: prescriptive numerical anchors became escape hatches.
- 26/60 rows (43%) returned exactly P_up = 62 — the printed default value —
  killing DIR-AUROC via AUROC ties.
- True DE and true `none` both piled into P_DE ∈ {15, 18, 20, 25} under
  the "lean toward 15-25" rule — relative ranking between them collapsed.
- 60/60 parsed cleanly; pipeline is fine, prompt is wrong.

**What survives**
- Single-call architecture is Track-A compliant and the parser handles two
  integers cleanly. The shape of the change is right.
- High-P_DE rows (≥70) were 6/7 true DE → the model can identify strong
  signal; it was the anchor that made mid-strength signal collapse.
- `pipeline/runner.py:fuse_q_r_logit` (3-seed logit-average of q and r
  separately) is prompt-independent and stays.

**Lesson**: encode priors as runner-side calibration or as qualitative
prompt wording, **never as a printed integer** the LLM can copy.

**Next** (attempt 07): same single-call architecture, strip R2 + R4
numerical anchors; either revert to attempt 04/05's tier-anchor wording
(90-100 / 70-89 / …) where the tiers describe *what each band means* but
don't tell the model where to default, or push the direction prior into
post-hoc shrinkage in `runner.py`. Validation gate same as attempt 06.

See `attempts/06_track_a_single_call/result.md`.

---

## 2026-06-09 · infra · Track-A compliance note + local GPT-OSS batch harness

Validated the local GPT-OSS path for attempt-05-style prompts and recorded the
current Track-A compliance interpretation.

**Compliance note**
- Kaggle Track A is safest to read as **3 total calls per question**: one call
  each for seeds 42 / 43 / 44.
- Therefore the current attempt-04/05 research surface (separate DE prompt +
  DIR prompt per seed) is useful for ablation and local validation, but should
  not be treated as the final submission path without collapsing it back to one
  prompt per seed.

**Infra / code changes**
- Fixed repo-root path assumptions in `pipeline/{replogle_prior,kg_retrieval,gene_desc,retrieve_examples,runner}.py` so the current workspace data layout works.
- Added task-specific parsers in `pipeline/output_parser.py`:
  `extract_p_de(...)` and `extract_p_up_given_de(...)`.
- Added `scripts/make_submission_v2.py` for DE/DIR split-output schema checks.
- Added `scripts/test_gptoss_attempt05_local.py` (single-pair local GPT-OSS smoke test).
- Added `scripts/run_inference_v2_local.py` (local batch runner for attempt-05 DE/DIR outputs).

**Retrieval fix**
- `pipeline/retrieve_examples.py` now falls back from BOTH-anchor retrieval to
  SINGLE-anchor retrieval when one side has no KG neighborhood.
- On the first 300 test rows, empty retrieval rates dropped from:
  - DE: 121 -> 9
  - DIR: 129 -> 9
  - both empty: 121 -> 9

**Local GPT-OSS findings**
- Single-pair smoke test (`Aars -> Atf4`): DIR prompt reached
  `P_up_given_DE: 95`; DE prompt often leaked `P_DE` mid-output but still
  tended to overrun the output budget.
- Dual-GPU batch (`limit=10`, seed 42) completed successfully with
  `tensor_parallel_size=2`.
- Output quality is still weak: DE extraction ok on 4/10 rows, DIR extraction
  ok on 1/10 rows; most rows hit the 1200-token output cap.

**Submission assembly**
- Built a schema-check zip containing `submission.csv` + `prompt.txt` to verify
  packaging only. It is not a real final submission because the staged run
  mirrors seed 42 into seeds 43/44 and uses the non-compliant DE/DIR split
  research surface.

---

## 2026-06-08 (later) · attempt 05 · Paper-faithful VCWorld port (real labels)

Re-read the actual paper (Wei et al., ICLR 2026 — `discussion/vcworld_paper.txt`)
and discovered attempt 04 was built on a misreading of VCWorld. The randomized-
label rendering we used came from `src/cli_pipeline/stages/prompt.py:61`
(`random.choice(choices)`), but **paper §3.4.2 + Appendix D** retrieve **analogue
+ contrast subsets with real labels**, ranked by similarity within each pool.
Structural pos/neg mix defeats vote bias without destroying empirical signal.

**Implementation**
- `pipeline/retrieve_examples.py`: added `retrieve_analog_contrast(pert, gene, task='de'|'dir', k_a, k_c)` and `format_block_analog_contrast(...)`. Removed `format_block_random_labels`.
- `pipeline/prompt_builder_v2.py`: `build_de_prompt` and `build_dir_prompt` now use analog+contrast retrieval with real labels (k_a=5 + k_c=5, total budget unchanged).
- `pipeline/tests/test_retrieve_analog_contrast.py`: 5 new tests; 29/29 pipeline tests green.
- `scripts/eval_metric_v3.py`: eval runner pointing to `attempts/05_paper_faithful/outputs/eval60/`.

**Result on the same 60 train rows (seed=123)** — **TIE with attempt 04**

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| Attempt 03 (one prompt) | 0.654 | 0.451 | 0.552 |
| Attempt 04 (random labels) | 0.601 | 0.679 | **0.640** |
| **Attempt 05 (real labels, paper)** | **0.610** | 0.665 | **0.637** |

DE +0.009, DIR -0.014, Combined -0.003. Within 60-row sampling noise.

**Implication**: the random-label trick was **not** the active ingredient
in attempt 04's DIR-AUROC jump from 0.451 → 0.679. The real ingredients
were the architecture changes (two prompts, DIR drops Replogle, BMDM context,
per-gene descriptions). Random vs real label rendering moves the metric by
0.003 here.

**Recommendation**: use attempt 05 prompts for the full GPT run — same score
within noise, but conceptually cleaner and matches the published method.

**Corrections**: added `## Correction` notices to `attempts/04_vcworld_port/{README,result}.md` flagging the wrong VCWorld attribution. The attempt-04 numbers remain valid; only the causal story is corrected.

See `attempts/05_paper_faithful/result.md`.

---

## 2026-06-08 · attempt 04 (validated on DeepSeek 60-row probe) · VCWorld-style port

Pivoted to two-prompt VCWorld architecture after attempt 03 evaluation
revealed DIR-AUROC = 0.451 (below random) on 60 random train rows. Root cause:
forcing a single prompt to emit both P_DE and P_up_given_DE made the LLM
override Replogle direction with weak mechanism reasoning.

**Result on same 60 train rows (seed=123)**

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| Random | 0.500 | 0.500 | 0.500 |
| Replogle alone (apples-to-apples) | 0.531 | 0.471 | 0.501 |
| **Attempt 03** (one prompt KG+celltype) | 0.654 | **0.451** | 0.552 |
| **Attempt 04** (two prompts, VCWorld port) | 0.601 | **0.679** | **0.640** |
| Reference: attempt 01 whole-train Replogle | 0.541 | 0.663 | 0.602 |
| Reference: top-4 Kaggle LB band | — | — | 0.628 – 0.650 |

**Build artifacts (committed)**
- `pipeline/bmdm_context.py` — rich BMDM cell-state paragraph
- `pipeline/gene_desc.py` + `data/gene_desc.json` — NCBI/MGI summaries, 87% coverage via human-ortholog backfill
- `pipeline/retrieve_examples.py` — KG-similarity retrieval of K=10 train (pert', gene') pairs with randomized labels (vote-bias defense)
- `pipeline/prompt_builder_v2.py` — `build_de_prompt`, `build_dir_prompt`
- `scripts/build_gene_desc.py` + `scripts/extend_gene_desc.py` — one-time desc cache
- `scripts/eval_metric_v2.py` — eval runner (async, configurable concurrency)
- 19 / 19 existing pipeline tests still pass

**Architecture choices that mattered**
- DE and DIR are two independent prompts; DIR omits Replogle scalar
- Retrieval uses STRING + Reactome co-membership (existing KG index from attempt 03)
- Exemplar labels are RANDOMIZED in-prompt — proves question is well-defined
- BMDM context paragraph includes lineage-silent programs (cell cycle, adaptive immunity)
  so the model can reject genes that are biologically inert in BMDM

**Cost so far (DeepSeek probes)**: ~$1.5 total across all evaluation rounds.

**Next**: user runs full 1,813 rows × 2 prompts × 3 seeds on GPT to get a real LB score. See `attempts/04_vcworld_port/result.md`.

---

## 2026-06-04 · attempt 03 (offline build) · KG + cell-type guidance prompts

Built Layer 2 (mouse KG mechanism) + Layer 3 (cross-cell-type transfer guide) and
regenerated 1,813 prompts. LLM inference still pending.

- **Data**: downloaded STRING mouse PPI v12.0, STRING aliases, Reactome
  Ensembl2Reactome (all species, filtered to ENSMUSG), GO mgi.gaf (reserved for
  attempt 04 fallback). Filtered KG index in `data/kg_index/` is ~4 MB, committed.
- **Coverage**: 68% of test rows now have *some* KG signal (PPI path or category
  tag). 33% have a STRING shortest path ≤3 hops between pert and gene.
- **Code**: `pipeline/{kg_retrieval, celltype_guide}.py` + extended
  `prompt_builder.py` with `use_kg=True` switch.
- **Prompts**: median 1,540 tokens (was 1,018), still well under 4,096 budget.
- **Tests**: 19 / 19 passing (added 8 tests in `test_kg.py`).
- **Known gap**: 46% of genes have no Reactome mouse annotation (Atf4, Stat1,
  Aars, Mki67, Lyz1, Eef1a1, Ifit1, …). GO BP fallback is the natural attempt 04
  if attempt 03 doesn't move the score.

**Next**: run GPT-OSS-120B × 3 seeds × 1,813 prompts on LLM server; compare
attempt 03 LB score to attempt 02. Update this entry with the score.

See `attempts/03_kg_celltype/result.md`.

---

## 2026-06-03 · strategy · Four-layer prompt architecture decided

Articulated the current pipeline's limitation: attempt 02's prompts give the LLM a Replogle scalar without mechanism context or cell-type translation guidance. The LLM is being asked to extrapolate K562/RPE1 → BMDM without being taught how.

**Decision**: build each question's prompt as four conceptual layers.

1. Replogle scalar (existing, attempt 02)
2. KG mechanism context — STRING shortest path, Reactome pathway membership, GO overlap
3. Cell-type translation guide — static rules for what transfers across cell types
4. Case-based exemplars — deferred due to user's prior observation that example label distribution dominates LLM decisions (vote bias)

**Implementation = attempt 03**: layers 2 + 3 only. Layer 4 deferred until 02 vs 03 comparison is done.

**Closes the "should we be like VCWorld?" question**: architecturally yes (same offline-KG → retrieval → structured-prompt pattern, same DE/DIR output structure), but specifics differ. We need mouse BMDM context (VCWorld is human + drug), 4k input-token cap (VCWorld has none), and the double-AUROC parameterization is enforced via separate `P_DE` and `P_up_given_DE` integers.

See `plans/plan.md` for the current pending list.

---

## 2026-06-03 · infra · Convention: keep plan / progress / git in sync

Added explicit requirement to `CLAUDE.md`: after any meaningful work, update `progress.md` AND `plans/plan.md` AND commit + push. The two-server workflow needs the remote current.

---

## 2026-06-03 · infra · Repo initialized for two-server workflow

Made the project a git repo so the LLM-server side can pull and run inference.

- `README.md` documents the full workflow (download data → build prior → build prompts → run LLM → assemble submission).
- `scripts/run_inference.py` works with any OpenAI-compatible endpoint (vLLM, TGI). Reads from `LLM_BASE_URL` and `LLM_API_KEY` env vars. Concurrency, resume, and per-seed token tracking built in.
- `scripts/make_submission.py` packages the zip per Track A spec (`submission.csv` + `prompt.txt`).
- `scripts/download_data.py` pulls competition data via Kaggle API token.
- `.gitignore` excludes competition data, large priors, generated prompts, inference outputs, and the internal Fig6 PDF — all reproducible from committed scripts.
- Final aggregation in `pipeline/runner.py` updated to match the Track A spec wording (final `prediction_up` = mean of per-seed `prediction_up_seedXX`, same for down).
- 29 files committed in initial commit `8edb0cf`.

**Next on this server**: add KG retrieval signal for the 670 `none`-tier rows.
**Next on the LLM server**: pull, run `scripts/run_inference.py`, push outputs back.

---

## 2026-06-03 · attempt 02 · Baseline Track A prompt scaffold

Built `pipeline/` infrastructure and generated 1,813 per-question prompts for Track A.

- **Code**: `pipeline/{replogle_prior,prompt_builder,output_parser,runner}.py`
- **Output**: `attempts/02_baseline_prompts/prompts/{test_id}.txt`
- **Prompt budget**: median 1,018 tokens (cap 4,096 by rules).
- **Test coverage**: full 994 (55%) · pert_only 149 (8%) · none 670 (37%).
- **Parser**: round-trip validated (P_DE 22, P_up_given_DE 35 → p_up 0.077, p_down 0.143).

**Next**: (a) run `GPT-OSS-120B × 3 seeds × 1,813 prompts` once GPU is available;
(b) add KG retrieval signal for the 37% `none`-tier rows (BMDM-relevant TFs);
(c) train auxiliary LightGBM DE classifier.

See `attempts/02_baseline_prompts/result.md`.

---

## 2026-06-03 · attempt 01 · Cross-species transfer pilot (Replogle K562 + RPE1)

Tested whether human CRISPRi (Replogle K562/RPE1) gives a useful prior for mouse BMDM CRISPRi.

- **Best variant**: K562 + RPE1 averaged · combined AUROC **0.602** on 4,154 evaluable train rows.
- **Decomposition**: DE-AUROC 0.541 (≈ random) · DIR-AUROC 0.663 (real signal).
- **Reading**: Cell-type-specific `G_c` (universal drift) dominates DE detection across species,
  but the **direction** of effect is moderately conserved. Replogle is a DIR prior, not a DE detector.
- **Variants tried**: K562 alone (0.574), RPE1 alone (0.586), union avg (0.602), intersection (0.609),
  top-50 thresholded (0.533, hurts), top-200 thresholded (0.542, hurts), mygene ortholog vs uppercase
  fallback (≤ 0.001 difference).
- **Conclusion**: ortholog mapping is saturated. DE channel must come from non-Replogle signals
  (KG retrieval, mechanistic reasoning, auxiliary classifier).

See `attempts/01_cross_species_pilot/result.md`.

---

## 2026-06-03 · context · Source dataset search (no attempt artifact)

Searched for the competition's underlying BMDM CRISPRi data so it could be used for direct lookup.

- Competition identified as the inaugural BRChallenge at **MLGenX@ICLR 2026**.
- Organizers include Aviv Regev and Tommaso Biancalani (both Genentech), plus Fabian Theis.
- "CropFlow" pipeline name has no public footprint.
- Surveyed: scPerturb, X-Atlas/Orion, VIPerturb-seq, Hagai 2018, Sankaran macrophage CRISPR.
  None match the 482-pert mouse BMDM CRISPRi profile.

**Conclusion**: source data is almost certainly Genentech-internal. **No direct lookup possible.**
All progress must go through indirect signal (cross-species, KG, LLM mechanistic).

See `discussion/analysis.md` and `discussion/tricks.md`.
