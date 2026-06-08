# Plan — what's next

Forward-looking only. Historical decisions live in `progress.md`. Each entry is one candidate attempt with rationale, expected impact, and concrete deliverables.

## Current strategic frame

Attempts 04 (random labels) and 05 (paper-faithful, real labels) score **0.640 vs 0.637 Combined** on the 60-row train probe — a tie within sampling noise. Both clear the attempt-01 baseline (0.602) and sit in the top-4 Kaggle LB band (0.628 – 0.650). The two-prompt architecture is validated; the label-rendering choice does not measurably change the metric here.

**Going forward**: use **attempt 05 prompts** (paper-faithful, real labels) — conceptually cleaner, single source of truth for "our method".

Architecture: per-question is **two independent calls** to the LLM.

| Layer | Purpose | Status |
|---|---|---|
| BMDM context paragraph | Lineage state, expressed vs silent programs | ✅ attempts 04 + 05 |
| Per-gene NCBI summary | Function context per pert + target | ✅ attempts 04 + 05 (87% coverage via human ortholog) |
| Analog + contrast retrieval (k_a=5 + k_c=5) | Paper §3.4.2 — label-conditioned pools, real labels in prompt | ✅ attempt 05 |
| DE prompt | Replogle scalar included, 5-step reasoning, integer P_DE out | ✅ attempts 04 + 05 |
| DIR prompt | Replogle scalar OMITTED, activator/repressor logic, integer P_up_given_DE out | ✅ attempts 04 + 05 |

## Pending — in order

### P1 · Full GPT run on attempt 05 prompts (user-owned)
Run the paper-faithful two-prompt pipeline against all 1,813 test rows × 3 seeds × {DE, DIR} = 10,878 GPT calls. Aggregate per-seed P_DE / P_up_given_DE through `pipeline/runner.assemble_submission()` to produce the Kaggle submission zip.

- Deliverable: `attempts/05_paper_faithful/outputs/{de,dir}/{seed}/{id}.txt`, then `attempts/05_paper_faithful/submission.zip`, then the real Kaggle Public LB score.
- Decision point: LB score tells us whether further iteration is worth it.

### P2 · Submission format dry-run (before P1)
- Pull `sample_submission_track_a.csv` from Kaggle Data tab
- Diff column names / types against `pipeline/runner.assemble_submission()`
- Test the zip on a one-row submission to confirm Kaggle accepts the format
- Cost of skipping: 0-score submission, burns a daily quota slot

### P3 · Retrieval-quality ablation (conditional on P1)
If LB lands ≤ 0.60, retrieval quality may be the bottleneck. Try:
- Increase budget from k_a=5+k_c=5 to k_a=10+k_c=10 (more analogues to reason from)
- Weight STRING edges by confidence band (currently linearly summed); pathway shared > 1 weighted more
- Tune the pos/neg balance — empirically for our data, DIR contrast pool is often empty (e.g., aaRS→ISR queries have 0 down-going analogues). Consider falling back to broader KG neighborhoods when contrast pool < 2.

### P4 · DE-AUROC recovery (-0.05 vs attempt 03)
Attempts 04 + 05 both trade DE-AUROC (~0.60) for the big DIR win (~0.67). Worth recovering this:
- The 5-step reasoning may be making the model too conservative on DE
- Try giving the DE prompt a simpler 2-3-step structure to keep P_DE distribution wider

### P5 · Augment exemplars beyond Reactome+STRING
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
