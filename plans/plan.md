# Plan — what's next

Forward-looking only. Historical decisions live in `progress.md`. Each entry is one candidate attempt with rationale, expected impact, and concrete deliverables.

## Strategic frame after the 2026-06-09 probe60 result

A09 (rare-gene probe) showed attempt 07 scores Combined = **0.466 on
test-condition data, below random (0.5)**. All previous eval60 numbers
(0.55-0.64 range across A03-A07) were inside the leakage band — nothing
has been shown to actually beat random on the data structure that
matters for the test set.

This is the honest baseline. Everything below assumes we are starting
from "no working method yet", not "ship attempt 07 with small tuning".

| Component | Status under this honesty correction |
|---|---|
| Two-prompt architecture (A04 / A05) | Probably also leakage; needs probe60 cross-check |
| Single-call architecture (A07) | Track-A compliant but scores 0.466 on test condition |
| analog + contrast retrieval | Works for popular genes; empty/weak for ~70% of test genes |
| BMDM context paragraph | Useful but only when gene IS in a known BMDM program |
| Replogle ortholog scalar | Helpful when ortholog exists (~ half of genes) |
| 3-seed logit fusion (runner) | Architecture is right; doesn't help if base preds are noise |

## Pending — in order

### P1 · Probe60 cross-check on A04 / A05 (cheap, ~$0.30, 5 min)
Re-run A04 (two-prompt random labels) and A05 (two-prompt real labels)
on the same probe60 sample (seed=789). If either is materially better
than A07's 0.466, revive that architecture and prune accordingly.

- Deliverable: `attempts/09_rare_gene_probe/result.md` updated with the
  A04 / A05 numbers.
- Decision point: if all three score ≈ 0.5, the architecture is not the
  bottleneck; the data signal is.

### P2 · Two-tier prediction (cheap, ~30 min code, no API)
Build a runner-side decision that splits test rows into:

- **Tier A (high-info)**: gene has a Replogle ortholog OR has KG pathway
  neighbors OR has a NCBI/MGI description longer than N chars. Use
  attempt-07 LLM predictions for these rows.
- **Tier B (low-info)**: everything else (mostly Riken IDs and lncRNAs).
  Output **the training prior** with tie-breaking jitter:
  - `P_DE = 0.45` (train base rate of `none` ≈ 0.55, so `1 - 0.55 = 0.45`)
  - `P_up_given_DE = 0.62` (train up:down ≈ 2.2:1)
  - Add small deterministic jitter from `hash(row_id)` so AUROC isn't
    crushed by ties.

Test this hybrid on probe60 + eval60. Expected: Tier B floors AUROC at
≈ 0.5 instead of 0.45, lifting overall Combined from 0.466 toward 0.5+.

- Deliverable: `pipeline/runner.py` adds `predict_hybrid()` plus a config
  describing the high-info gate.
- Decision point: if probe60 lifts to ≥ 0.55, this is a viable
  Track-A submission floor.

### P3 · Detect what signal IS available on test (1-2 hr analysis, no API)
Audit how many test rows have:

- Replogle ortholog match → direct logFC available
- KG pathway neighbors for both pert and gene
- An NCBI/MGI description longer than the symbol itself

This tells us the proportion of test rows where a method has any chance
of beating random. Sets the realistic ceiling for any LLM-based approach.

- Deliverable: `attempts/10_test_signal_audit/result.md` with per-feature
  coverage on the 1,813 test rows.

### P4 · CORE-style same-readout contrastive evidence (research lift)
Per `discussion/next_paradigm_gpt.md` §A: for each (pert, gene), build
an evidence packet with:

- positive supports: similar perts in OTHER cell-line perturb-seq datasets
  that changed the same readout (or its ortholog)
- negative supports: similar perts that did NOT change the same readout
- signed regulatory paths from a KG with edge signs (Reactome / OmniPath)

This is the GPT discussion's main bet. Requires external data
(OmniPath signed, public BMDM perturb-seq, e.g. Hagai 2018 / ImmGen-pert)
and a real engineering lift.

- Deliverable: new `pipeline/evidence_packet.py` + a new prompt builder
  that consumes it.
- Decision point: only worth doing if P2/P3 confirm there's no cheap
  win on top of attempt 07.

### P5 · Submission format dry-run (independent of P1-P4)
- Pull `sample_submission_track_a.csv` from Kaggle Data tab
- Diff column names / types against `pipeline/runner.assemble_submission()`
- Test the zip on a one-row submission to confirm Kaggle accepts the format
- Cost of skipping: 0-score submission, burns a daily quota slot

### P6 · Real Track-A submission (post P1-P3 and a working method)
ONLY when probe60 Combined ≥ 0.55 with whatever method emerges from
P1-P4. Burning GPT-OSS-120B compute on a probe-overfit prompt is not
the right move.

- 1,813 test rows × 3 seeds × 1 call (compliant); aggregate via
  `pipeline/runner.assemble_submission()`.

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
