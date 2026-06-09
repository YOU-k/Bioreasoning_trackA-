# Attempt 08 — Audit: are our attempt-07 gains real?

## Why this audit (not another attempt)

The GPT 2026-06-09 discussion (`discussion/next_paradigm_gpt.md` §1.5,
§7) flags a critical confound in PerturbQA-style benchmarks:

> aggregate AUROC/AUPRC can be confounded by gene response frequency: a
> gene-prior voting baseline can win on overall metric but be ≈ chance
> on per-gene discrimination

If true here, then attempts 03-07 are essentially measuring how well the
LLM can guess "this readout gene class often responds vs rarely
responds", NOT "this specific perturbation affects this specific gene".
The differences between attempts 04 / 05 / 07 (0.640 / 0.637 / 0.623)
would mostly be noise on top of a gene-prior baseline.

Before spending GPT-OSS-120B compute on a full Track-A submission, we
need to know which world we're in:

- **World 1 (we're doing pert-specific reasoning)**: ship attempt 07 with
  confidence; the 0.014 gaps between attempts are real but small.
- **World 2 (we're doing gene-prior voting)**: every previous attempt's
  AUROC is dominated by gene-rate priors; the LLM is mostly window
  dressing; need a paradigm pivot (toward CORE-style same-readout
  contrastive evidence, GPT discussion §A).

## Method

On the **same 60 random train rows** (seed=123) used to grade attempts
03 / 04 / 05 / 06 / 07, compute three non-LLM baselines:

1. **Gene-only**:
   - For each `(pert*, gene*, label*)` row, look at all train rows
     containing `gene*` but NOT `pert*` (mimics `exclude_query=True`).
   - `P_DE_gene = n_DE / n_total` where `n_DE = |{up, down}|`,
     `n_total = |all rows containing gene*|`
   - `P_up_given_DE_gene = n_up / (n_up + n_down)` over those rows
     (default 0.5 if denominator is 0)

2. **Pert-only**: symmetrical, conditioning on `pert*` instead of `gene*`.

3. **Gene + Pert hybrid**: average of the two.

Compute DE-AUROC, DIR-AUROC, Combined for each baseline against the
true labels, and compare to attempt 07's numbers.

Additional diagnostics (where eval60 size allows):
- **Spearman correlation** between attempt-07's `P_DE` and the gene-only
  `P_DE`. High correlation (> 0.7) ⇒ attempt 07 is basically reproducing
  the gene-prior.
- **Disagreement audit**: count rows where attempt 07 and gene-only
  disagree on the DE call, and check which one is more often right.
  Evidence of real LLM reasoning shows up here.

## Decision rule

| Outcome | Verdict |
|---|---|
| Gene-only Combined ≤ 0.55 AND attempt-07 - gene-only ≥ 0.05 | World 1 — ship attempt 07 |
| Gene-only Combined in [0.56, 0.59] AND attempt-07 - gene-only ≥ 0.03 | Mixed — attempt 07 adds real signal but not dramatically; ship with caveats |
| Gene-only Combined ≥ 0.60 OR attempt-07 - gene-only < 0.02 | World 2 — pivot to CORE-style same-readout contrastive evidence before any GPT spend |

## Inputs

- `data/train.csv` — for computing the gene/pert priors
- `attempts/07_no_anchors/outputs/eval60/single/*.json` — attempt-07 per-row predictions
- Same 60 rows from `scripts/eval_metric_v4.py`'s `pick_random(60, seed=123)`

## Outputs

- `attempts/08_audit_baselines/result.md` — verdict + numbers
- `attempts/08_audit_baselines/audit.json` — raw per-row data for further analysis
