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

## Pending — in order

### P1 · Full Track-A GPT-OSS-120B run with attempt 07 prompts (user-owned)

Attempt 07 cleared the validation gate (Combined = 0.623, ACCEPTABLE band).
`pipeline/prompt_builder_v3.py` is the Track-A submission prompt.

Run: 1,813 test rows × 3 seeds (42 / 43 / 44) × 1 call each = 5,439 LLM calls.
Aggregate with `pipeline/runner.assemble_submission()` (uses `fuse_q_r_logit`
for 3-seed q/r fusion). Package the zip per Track-A spec. Submit.

- Deliverable: `attempts/07_no_anchors/outputs/{seed}/{id}.txt` and `.json`,
  then `submission.zip`, then the real Kaggle Public LB score.
- Compliance budget: 3 calls per question ✓. Max prompt tokens 4096 ✓
  (attempt 07 prompts are 2280-2360 tokens).
- Decision point: LB score tells us whether further iteration is worth it.

### P2 · Submission format dry-run (before P1)
- Pull `sample_submission_track_a.csv` from Kaggle Data tab
- Diff column names / types against `pipeline/runner.assemble_submission()`
- Test the zip on a one-row submission to confirm Kaggle accepts the format
- Cost of skipping: 0-score submission, burns a daily quota slot

### P3 · Macro-per-gene baseline audit (before claiming method validity)
Per `discussion/next_paradigm_gpt.md` §7: overall AUROC can be confounded
by gene response frequency (a gene-prior voting baseline can win on overall
AUROC while being chance on per-gene). Run on the same 60-row probe:

- target-only baseline: predict P_DE = global rate of `gene` going DE in
  rest of train, ignore pert
- pert-only baseline: same with pert
- attempt 07 prompts: stratify AUROC by gene class (silent vs inducible
  BMDM programs); compute macro-per-gene AUROC
- if attempt 07 ≈ gene-only on macro-per-gene, our gains are gene-prior

### P4 · Runner-side direction-prior shrinkage (recover the 0.014 to A05)
Attempt 07 still has 17/60 rows landing at P_up = 50 (ambiguous midpoint).
Try post-hoc shrinkage in `pipeline/runner.py`: when LLM emits `r ∈ [0.45,
0.55]`, pull toward 0.62 (the train prior). Cheap to test on attempt 07's
existing outputs without re-running the LLM.

### P5 · Retrieval-quality ablation (conditional on LB)
If LB lands ≤ 0.60, retrieval quality may be the bottleneck. Try:
- k_a=10 + k_c=10 (more analogues to reason from)
- Weight STRING edges by confidence band
- Tune the pos/neg balance — DIR contrast pool is often empty (e.g.,
  aaRS→ISR queries have 0 down-going analogues). Consider broader KG
  neighborhoods when contrast pool < 2.

### P6 · Augment exemplars beyond Reactome+STRING
Genes with no Reactome mouse annotation (46% of test) get weak retrieval. Add:
- GO BP overlap (`mgi.gaf` already downloaded in attempt 03)
- Co-expression neighbours (ImmGen — postpone unless retrieval ablation
  shows it's the limit)

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
