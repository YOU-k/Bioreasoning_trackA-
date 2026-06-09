# Attempt 08 — Audit result

**Date**: 2026-06-09
**Status**: **Significant strategic findings.** eval60 was leakage-confounded
on the DIR axis; previous attempt-to-attempt gaps (A04 / A05 / A07: 0.640 /
0.637 / 0.623) are within the band of that contamination, not real
optimization signal.

## Verdict in one paragraph

`attempt 07` is doing **real perturbation-specific reasoning on DE**
(beats gene-only baseline by +0.60 on DE-AUROC; in 31/31 disagreements
attempt 07 is correct). It is **NOT doing real direction reasoning on
unseen genes** (sub-random DIR-AUROC 0.438 on the eval60 subset with
weak gene-prior signal). The DIR-AUROC of 0.645 on eval60 was inflated
by gene-prior leakage that **disappears on the actual test set**, where
test genes do not appear in train at all. Plan P1 (ship attempt 07) is
NOT ready until we re-validate on a true double-disjoint probe.

## Baseline comparison (eval60, same 60 train rows, seed=123)

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| Random | 0.409 | 0.583 | 0.496 |
| Gene-only baseline | 0.000 | **0.746** | 0.373 |
| Pert-only baseline | 0.255 | 0.683 | 0.469 |
| Gene+Pert hybrid | 0.123 | **0.817** | 0.470 |
| **Attempt 07** | **0.601** | 0.645 | 0.623 |

Two surprising findings:

1. **Gene-only DE-AUROC = 0.000**: rows where the gene is a frequent
   responder in train tend to be 'none' in eval60 (the negative-sampling
   design balances things at the *perturbation* level, not the *gene*
   level, so a frequent-responder gene gets sampled as 'none' for many
   perts). Attempt 07's DE = 0.601 cannot be gene-prior voting — the
   prior is **anti**-correlated with the label.

2. **Gene-only DIR-AUROC = 0.746**: knowing only the readout gene's typical
   direction in *other* train rows beats attempt 07's mechanistic reasoning
   (0.645). The model is **destroying** information that a 5-line lookup
   carries for free.

## Leakage-stratified DIR-AUROC

Same eval60, stratified by `n_same_gene_in_train` (excluding query pert):

| Bucket | n_rows (up/down) | Attempt 07 DIR | Gene-only DIR |
|---|---|---|---|
| Low gene-prior (1-3 neighbors) | 9 (8 up / 1 down) | **0.438** | 0.625 |
| High gene-prior (≥11 neighbors) | 24 (13 / 11) | 0.741 | 0.787 |

Test set is **double-disjoint** — test readout genes have **zero** train
neighbors. So the bucket relevant for test is "Low gene-prior", where
attempt 07 DIR is **sub-random (0.438)**.

**Estimated attempt-07 DIR-AUROC on real test ≈ 0.45-0.50**, NOT 0.645.

(DE is not stratified here because the leakage pattern was anti-correlated;
DE-AUROC is more likely a robust signal.)

## Cross-correlations (sanity)

| Variable pair | Spearman ρ |
|---|---|
| attempt 07 P_DE  vs gene-only P_DE | **-0.081** |
| attempt 07 P_DE  vs pert-only P_DE | -0.038 |
| attempt 07 P_up  vs gene-only P_up | -0.054 |
| attempt 07 P_up  vs pert-only P_up | +0.314 |

Near-zero correlations confirm attempt 07 is NOT just regurgitating the
prior on the DE axis. Pert-prior direction is mildly correlated with
attempt-07 direction (+0.314), but that's still mostly independent.

## What previous attempts actually demonstrated

The 0.014 Combined gap between A04 (0.640), A05 (0.637) and A07 (0.623)
was inside the leakage band on DIR. Those attempts were not actually
ranking better than each other on the data structure that matters for
the test set. The "ship-or-pivot" decision should be based on a
double-disjoint probe, not eval60.

The 0.04-0.05 gap between A06 (0.585) and A07 (0.623) likely IS real
(both are leakage-confounded the same way; the relative position
reflects prompt quality on the residual). But the absolute number 0.623
is not what attempt 07 will score on test.

## What's next (per discussion)

The audit changes the priority queue:

1. **P1' — Build a true double-disjoint validation probe.** Sample 60
   train rows where the query (pert, gene) has zero same-gene AND zero
   same-pert neighbors in the rest of train. Re-evaluate attempts 04 /
   05 / 06 / 07 against the same probe. The numbers from THAT probe are
   the true Track-A estimate.

2. **P1'' — Address the DIR bottleneck explicitly.** Attempt 07's DIR
   on unseen genes is the actual ceiling problem. Possible levers:
   - Surface Replogle direction more prominently (it's the only gene-typical-direction
     signal we have for unseen genes).
   - Add gene functional category (TF / kinase / chaperone / …) at retrieval
     time so the LLM can borrow "this gene class typically goes up".
   - Or: accept DIR is hard, focus on driving DE-AUROC up further (we have
     no evidence ceiling).

3. **Don't ship attempt 07 yet** — until we have a double-disjoint number,
   we don't actually know what Track A will score. Burning GPT-OSS-120B
   compute on a probe-overfit prompt is not the right move.

## Inputs

- `data/train.csv`
- `attempts/07_no_anchors/outputs/eval60/single/*.json`
- Same `pick_random(60, seed=123)` sample used everywhere else

## Outputs

- `attempts/08_audit_baselines/audit.json` — raw metrics + correlations + disagreement counts
- `attempts/08_audit_baselines/audit_log.txt` — script output
- `scripts/audit_baselines.py` — the audit code
