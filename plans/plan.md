# Plan — what's next

Forward-looking only. Historical decisions live in `progress.md`. Each entry is one candidate attempt with rationale, expected impact, and concrete deliverables.

## Strategic frame after attempt 11 (Hagai + hybrid runner)

A11 = first Track-A-compliant method to score above 0.55 on a test-mimic
probe. Combined 0.613 on probe60_rare_gene with single-call LLM +
runner-side Replogle direction blend.

Expected test Combined: **0.55-0.61** (probe60 signal-coverage distribution
matches test almost exactly: T0/T1/T3 share = 55/35/8% vs 54/37/9% on test).

Top-4 public LB band is 0.628-0.650. We are within 0.02-0.07 of LB on
a compliant architecture. Ship.

| Component | Status under this honesty correction |
|---|---|
| Two-prompt architecture (A04 / A05) | Probably also leakage; needs probe60 cross-check |
| Single-call architecture (A07) | Track-A compliant but scores 0.466 on test condition |
| analog + contrast retrieval | Works for popular genes; empty/weak for ~70% of test genes |
| BMDM context paragraph | Useful but only when gene IS in a known BMDM program |
| Replogle ortholog scalar | Helpful when ortholog exists (~ half of genes) |
| 3-seed logit fusion (runner) | Architecture is right; doesn't help if base preds are noise |

## Pending — in order

### P1 · Track-A submission with A11 pipeline (user-owned on LLM server)

A11 (single-call prompt with Hagai + Replogle, hybrid runner) is the
shippable Track-A method. Probe60 Combined = 0.613. Expected test 0.55-0.61.

- Inputs:
  - `pipeline/prompt_builder_v3.py:build_track_a_prompt` (Hagai block on)
  - `pipeline/runner.assemble_submission(..., apply_hybrid_direction=True)`
- Run: 1,813 test rows × 3 seeds (42 / 43 / 44) × 1 call = 5,439 GPT-OSS-120B calls.
- Aggregate via `pipeline/runner.assemble_submission()` (logit-fuse seeds, hybrid direction).
- Package per Track-A spec, submit.

### P2 · Submission format dry-run (do BEFORE P1)
- Pull `sample_submission_track_a.csv` from Kaggle Data tab.
- Diff column names / types against `pipeline/runner.assemble_submission()`.
- Test the zip on a one-row submission to confirm Kaggle accepts the format.
- Cost of skipping: 0-score submission, burns a daily quota slot.

### P3 · Additional Task3_data signal sources (~28% test rows still on prior)

A11 hybrid leaves 28% of test rows (no Replogle full + no Hagai) on the
prior 0.62 floor. Look at:
- `Tahoe100_sub10.h5ad` (human drug perturb-seq, VCWorld dataset)
- `Kang.h5ad` (human PBMC IFN response)
- `Perturb_KHP_sub10.h5ad` / `Perturb_cmo_V1_sub10.h5ad` (Perturb-seq variants)

If any provides usable per-pert or per-gene direction priors, surface in
the prompt (like Hagai is) or use in the runner blend. Each new signal
source covering the remaining 28% gap could lift Combined another 0.02-0.05.

### P4 · Hagai pert-side signal (cheap follow-up)

Currently Hagai is used only for the readout gene's response to LPS. Hagai
also has logFC for the PERT itself, which tells us whether the pert is an
LPS-responsive gene. This is a feature we don't use yet: KD of an
LPS-responsive gene might selectively dampen inflammatory targets.

- Add Hagai pert |logFC| as an input feature to a per-row "is this pert
  inflammatory-relevant" check.
- Expected lift: small (~0.01).

### P5 · CORE-style same-readout contrastive evidence (research lift)

If the LB number from P1 lands below ~0.55, pivot to GPT discussion §A:
restructure retrieval to surface same-readout pos/neg pert pairs from
external perturb-seq with signed pathway features. Major engineering lift.

## Deferred / closed

- **Runner-side direction-prior shrinkage** — closed. The probe60 result
  shows the underlying signal is noise; shrinkage can't repair noise.
- **Retrieval quality ablation (was P5)** — deferred. Tune nothing until
  P1/P2 give a probe number worth tuning against.
- **Attempt 03 single-prompt KG+celltype** — superseded. Do not run again.

## Closed historical context

| Attempt | Combined on eval60 (leakage) | Verdict |
|---|---|---|
| A01 cross-species Replogle pilot | 0.602 | superseded |
| A02 baseline prompts | n/a (no LLM run) | superseded |
| A03 single prompt + KG | 0.552 | DIR collapsed; superseded by A04 |
| A04 two prompts, random labels | 0.640 | Best eval60 number; leakage |
| A05 two prompts, real labels | 0.637 | Tied A04; leakage |
| A06 single call + prescriptive anchors | 0.585 | FAIL prompt design |
| A07 single call + tier ladders | 0.623 | Track-A compliant; but **0.466 on probe60** |
| A08 baseline audit | n/a | Identified eval60 gene-prior leakage |
| A09 rare-gene probe | n/a | Confirmed A07 fails on test-condition |
