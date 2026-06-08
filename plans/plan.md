# Plan — what's next

Forward-looking only. Historical decisions live in `progress.md`. Each entry is one candidate attempt with rationale, expected impact, and concrete deliverables.

## Current strategic frame

Attempt 04 (VCWorld-style two-prompt architecture) hit **Combined = 0.640** on the 60-row train probe (DeepSeek-Reasoner), clearing the attempt-01 baseline (0.602) and entering the top-4 Kaggle LB band (0.628 – 0.650). The architecture is validated. Remaining work is execution + iteration.

Architecture: per-question is **two independent calls** to the LLM.

| Layer | Purpose | Status |
|---|---|---|
| BMDM context paragraph | Lineage state, expressed vs silent programs | ✅ attempt 04 |
| Per-gene NCBI summary | Function context per pert + target | ✅ attempt 04 (87% coverage via human ortholog) |
| KG-similarity retrieval (K=10) | Both-anchor train exemplars, labels randomized | ✅ attempt 04 |
| DE prompt | Replogle scalar included, 5-step reasoning, integer P_DE out | ✅ attempt 04 |
| DIR prompt | Replogle scalar OMITTED, activator/repressor logic, integer P_up_given_DE out | ✅ attempt 04 |

## Pending — in order

### P1 · Full GPT run on attempt 04 prompts (user-owned)
Run the two-prompt pipeline against all 1,813 test rows × 3 seeds × {DE, DIR} =
10,878 GPT calls. Aggregate per-seed P_DE / P_up_given_DE through the existing
`pipeline/runner.assemble_submission()` to produce the Kaggle submission zip.

- Deliverable: `attempts/04_vcworld_port/outputs/{de,dir}/{seed}/{id}.txt`, then
  `attempts/04_vcworld_port/submission.zip`, then the real Kaggle Public LB score.
- Decision point: LB score tells us whether further iteration is worth it.

### P2 · Submission format dry-run (before P1)
- Pull `sample_submission_track_a.csv` from Kaggle Data tab
- Diff column names / types against `pipeline/runner.assemble_submission()`
- Test the zip on a one-row submission to confirm Kaggle accepts the format
- Cost of skipping: 0-score submission, burns a daily quota slot

### P3 · Retrieval-quality ablation (conditional on P1)
If LB lands ≤ 0.60, retrieval quality may be the bottleneck. Try:
- Increase budget from K=10 to K=20 (more analogues to reason from)
- Add weight to STRING edges (currently flat-scored): pathway shared > 1 weighted more
- Replace VCWorld randomized labels with real labels (test whether vote bias actually appears)

### P4 · DE-AUROC recovery (-0.053 vs attempt 03)
Attempt 04 traded a small DE-AUROC drop (0.654 → 0.601) for the big DIR win.
Worth recovering this:
- The 5-step reasoning may be making the model too conservative on DE
- Try giving the DE prompt a simpler 2-3-step structure to keep P_DE distribution wider

### P5 · Augment exemplars beyond Reactome+STRING
Genes with no Reactome mouse annotation (46% of test, especially Riken IDs,
lncRNAs, ribosomal/IFN genes) get weak retrieval. Add fallbacks:
- GO BP overlap (we already downloaded `mgi.gaf` in attempt 03)
- Co-expression neighbours (would need an external BMDM reference, e.g.,
  ImmGen — postpone unless retrieval ablation shows it's the limit)

## Deferred / closed

- **Attempt 03 (one prompt, KG + cell-type guide)** — superseded by attempt 04. Kept for reference; do not run again.
- **Layer 4 case-based exemplars (deferred vote-bias concern)** — closed. VCWorld's randomized-label trick resolves vote bias; we now use it.
- **Ortholog mapping improvements** — pilot showed saturation. Closed.
- **Public BMDM CRISPRi lookup** — Genentech-internal. Closed.
- **PubMed abstract retrieval** — too noisy; subsumed by NCBI gene summaries + BMDM context.
