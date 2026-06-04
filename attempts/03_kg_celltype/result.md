# Attempt 03 — Result (offline build)

LLM inference not yet run. This file records what we built and the coverage
statistics on the test set; LB score will be appended once attempt 03 has
been scored.

## Output
- **1,813 prompts** in `prompts/{id}.txt`.
- Token estimates: **min 1,365, median 1,540, max 1,628** (budget 4,096).
- Headroom remaining: ~60% of the budget unused.

## Coverage on test set

| Signal | Rows / genes | % |
|---|---:|---:|
| Replogle full prior (attempt 02) | 994 / 1,813 | 55% |
| Replogle pert_only (attempt 02) | 149 / 1,813 | 8% |
| KG pathway for pert | 65 / 96 perts | 68% |
| KG pathway for target | 326 / 636 genes | 51% |
| KG category tag for pert | 45 / 96 perts | 47% |
| KG category tag for target | 152 / 636 genes | 24% |
| PPI path ≤3 hops between pert and gene | 595 / 1,813 | 33% |
| Direct (1-hop) PPI partner | 16 / 1,813 | 1% |
| **ANY KG signal (path or tag)** | **1,240 / 1,813** | **68%** |

KG fills the gap left by Replogle. The two sources are complementary —
Replogle drives the DIR-AUROC channel, KG grounds the LLM's mechanistic
reasoning that drives the DE-AUROC channel.

Known gaps:
- 53% of test rows still have **no KG-based PPI bridge** within 3 hops.
- 46% of GOI genes (~1,200 of 2,623) have **no Reactome mouse pathway**
  annotation. Notable losses: Atf4, Stat1, Aars, Mki67, Lyz1, Eef1a1, Ifit1 —
  all biologically important. These remain UNTAGGED; LLM is told to use
  mechanistic knowledge directly. A GO BP fallback (mgi.gaf.gz already
  downloaded) would close most of this gap and is the natural next move
  if attempt 03 doesn't lift the score enough.

## Sanity checks
- Cebpb → Acsl1 prompt contains the actual biological bridge: PPI
  `Cebpb -> Pparg -> Acsl1` (Cebpb upregulates PPARγ which transactivates
  ACSL1 — the textbook lipid metabolism cascade).
- Stat1 → Irf1 prompt correctly shows DIRECT (1-hop) PPI (the canonical
  IFN axis: STAT1 directly transactivates IRF1).
- Nfkb1 → Tnf prompt categorizes both as TLR_NLR / IMMUNE_EFFECTOR, advising
  "context-dependent → reason BMDM-specifically" (correct — Nfkb1 → Tnf is
  the central LPS-responsive cascade in BMDM that K562 doesn't run).
- All 19 pipeline tests pass.

## Verdict (pending LB score)
Pipeline behaviour matches design. Real value only confirmable after
inference. Two scenarios:

| If attempt 03 LB > attempt 02 by | Interpretation | Next action |
|---|---|---|
| ≥ 0.03 | Layer 2 + 3 add meaningful signal | Investigate Layer 4 (case-based exemplars) carefully |
| 0.01 – 0.03 | Partial value; some categories help, others don't | Add GO BP fallback for the UNTAGGED 46% |
| < 0.01 | LLM can't use the structured KG context | Re-examine prompt phrasing; consider auxiliary DE classifier (P3) instead |
