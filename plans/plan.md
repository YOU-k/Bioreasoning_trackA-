# Plan — what's next

Forward-looking only. Historical decisions live in `progress.md`. Each entry is one candidate attempt with rationale, expected impact, and concrete deliverables.

## Current strategic frame

Attempts 04 (random labels) and 05 (paper-faithful, real labels) score **0.640 vs 0.637 Combined** on the 60-row train probe — a tie within sampling noise. Both clear the attempt-01 baseline (0.602) and sit in the top-4 Kaggle LB band (0.628 – 0.650). The retrieval-rich architecture is validated; the label-rendering choice does not measurably change the metric here.

**Compliance update (2026-06-09)**: Track A wording is safest to interpret as
**3 total calls per question** (one call each for seeds 42 / 43 / 44). That
means attempts 04/05 as currently written — **two prompts per seed** (DE + DIR)
— are useful research probes and local validation surfaces, but should NOT be
treated as the final submission path without collapsing them back to one call
per seed.

**Going forward**: keep **attempt 05 retrieval + context ideas**, but compress
them into a single-call prompt that emits both `P_DE` and `P_up_given_DE`.

| Layer | Purpose | Status |
|---|---|---|
| BMDM context paragraph | Lineage state, expressed vs silent programs | ✅ attempts 04 + 05 |
| Per-gene NCBI summary | Function context per pert + target | ✅ attempts 04 + 05 (87% coverage via human ortholog) |
| Analog + contrast retrieval (k_a=5 + k_c=5) | Paper §3.4.2 — label-conditioned pools, real labels in prompt | ✅ attempt 05 |
| DE prompt | Replogle scalar included, 5-step reasoning, integer P_DE out | ✅ research surface |
| DIR prompt | Replogle scalar OMITTED, activator/repressor logic, integer P_up_given_DE out | ✅ research surface |
| Single-call Track-A prompt | One call per seed, emits both integers | ⏳ required before final submission |

## Strategic frame after the 2026-06-09 baseline audit

The audit (`attempts/08_audit_baselines/result.md`) showed:

- **DE is real**: attempt 07 beats gene-only DE-AUROC by +0.60. Reasoning is
  doing real work; we should protect it.
- **DIR was contaminated**: attempt 07 DIR-AUROC (0.645) loses to a 5-line
  gene-only baseline (0.746) on eval60, AND collapses to 0.438 on the
  low-gene-prior subset that matches test-set conditions.
- **The 0.014 Combined gap between A04 / A05 / A07 is leakage noise**, not
  real ranking signal. Stop optimizing it.
- **eval60 is not a faithful test surrogate.** Test rows have zero same-gene
  neighbors in train; eval60 rows have many.

So the priority queue is rewritten.

## Pending — in order

### P1 · Build a true double-disjoint validation probe (BLOCKER for any LB-relevant claim)

Sample 60 train rows where:
- the row's `pert` does NOT appear in the rest of train, AND
- the row's `gene` does NOT appear in the rest of train.

This mimics the test-set's double-disjoint structure. Re-evaluate attempts
04 / 05 / 06 / 07 on this probe. The numbers from THIS probe are the only
ones that translate to Track-A LB. eval60 numbers are leakage-contaminated.

If true double-disjoint rows are too few in train (≤ 20), relax to
single-disjoint (pert OR gene unseen) and report both numbers.

- Deliverable: `attempts/09_double_disjoint_probe/{README,result}.md` plus
  re-runs of A04 / A05 / A06 / A07 on the new probe.
- Cost: 60 rows × N attempts × DeepSeek ≈ $0.30 per attempt.

### P2 · Address the DIR bottleneck on unseen genes

DIR is where we lose. Mechanism reasoning over unseen genes is sub-random
(0.438). Options to try, in increasing cost:

- **a) Surface Replogle direction more aggressively** in the prompt. It IS
  the only gene-typical-direction signal we have for unseen genes (via
  ortholog). Currently used as "scalar context"; could be promoted to a
  primary anchor.
- **b) Add gene functional category** at retrieval time (TF / kinase /
  chaperone / inducible-stress / ribosomal / …) so the LLM can borrow
  "this gene class typically goes up under stress".
- **c) Pre-compute signed-pathway features** in the KG (sign of P → ... → G).
  Heavier KG engineering.

Run these against P1's double-disjoint probe, not eval60.

### P3 · DE-AUROC headroom

DE is the asset (0.601 vs gene-only 0.000). Could it go to 0.65? 0.70?
We don't have evidence of a ceiling. Probably worth probing — but only
after P1 gives an honest baseline.

### P4 · Submission format dry-run

- Pull `sample_submission_track_a.csv` from Kaggle Data tab
- Diff column names / types against `pipeline/runner.assemble_submission()`
- Test the zip on a one-row submission to confirm Kaggle accepts the format
- Cost of skipping: 0-score submission, burns a daily quota slot

### P5 · Track-A submission (post P1 + P2)

ONLY after P1 + P2 show a real double-disjoint Combined > some threshold
we agree on (say 0.55 — conservative because of attempt 07's DIR risk).

Full GPT-OSS-120B run: 1,813 test rows × 3 seeds × 1 call (compliant).
Aggregate with `pipeline/runner.assemble_submission()` (uses fuse_q_r_logit).

## Deferred / closed

- **Runner-side direction-prior shrinkage** — closed. The audit showed DIR
  on unseen genes is sub-random; shrinkage won't fix that. Need real signal
  source change, not output post-processing.
- **Retrieval quality ablation (was P5)** — deferred. Don't tune until
  P1/P2 give a probe number worth tuning against.

### P2 · Submission format dry-run (before any real GPT spend)
- Pull `sample_submission_track_a.csv` from Kaggle Data tab
- Diff column names / types against `pipeline/runner.assemble_submission()`
- Test the zip on a one-row submission to confirm Kaggle accepts the format
- Cost of skipping: 0-score submission, burns a daily quota slot

### P3 · Full GPT run on compliant prompt (user-owned)
Run the final single-call prompt against all 1,813 test rows × 3 seeds.

- Deliverable: `attempts/<final>/outputs/{seed}/{id}.txt`, `submission.csv`, `submission.zip`, and the real Public LB score.

### P4 · Retrieval-quality ablation (conditional on P3)
If LB lands ≤ 0.60, retrieval quality may be the bottleneck. Try:
- Increase budget from k_a=5+k_c=5 to k_a=10+k_c=10 (more analogues to reason from)
- Weight STRING edges by confidence band (currently linearly summed); pathway shared > 1 weighted more
- Tune the pos/neg balance — empirically for our data, DIR contrast pool is often empty (e.g., aaRS→ISR queries have 0 down-going analogues). Consider falling back to broader KG neighborhoods when contrast pool < 2.

### P5 · DE-AUROC recovery (-0.05 vs attempt 03)
Attempts 04 + 05 both trade DE-AUROC (~0.60) for the big DIR win (~0.67). Worth recovering this:
- The 5-step reasoning may be making the model too conservative on DE
- Try giving the DE prompt a simpler 2-3-step structure to keep P_DE distribution wider

### P6 · Augment exemplars beyond Reactome+STRING
Genes with no Reactome mouse annotation (46% of test, especially Riken IDs, lncRNAs, ribosomal/IFN genes) get weak retrieval. Add fallbacks:
- GO BP overlap (`mgi.gaf` already downloaded in attempt 03)
- Co-expression neighbours (would need an external BMDM reference, e.g., ImmGen — postpone unless retrieval ablation shows it's the limit)

## Deferred / closed

- **Attempt 03 (one prompt, KG + cell-type guide)** — superseded. Kept for reference; do not run again.
- **Random-label rendering (attempt 04)** — closed. Empirically equal to real-label rendering on 60-row probe (0.640 vs 0.637). Paper-faithful real labels are cleaner; use attempt 05 forward.
- **Layer 4 case-based exemplars (deferred vote-bias concern)** — closed. Paper §3.4.2 analog+contrast retrieval defeats vote bias structurally by the forced pos/neg mix, not by destroying the label signal.
- **Ortholog mapping improvements** — pilot showed saturation. Closed.
- **Public BMDM CRISPRi lookup** — Genentech-internal. Closed.
- **PubMed abstract retrieval** — too noisy; subsumed by NCBI gene summaries + BMDM context.
