# Attempt 14 — Enrich evidence cases with per-example Hagai + Replogle priors

## Why

A12 + A13 ablations showed that **active reasoning instructions** (R1-R5
+ A1-B2) are load-bearing, while **passive knowledge dumps** (BMDM
context paragraph) are net negative. The Heuristic suggested next:

> Add ACTIVE per-example data the LLM can use to compare query to example.

The plain evidence case format renders:
```
Example 1: pert=`Cul1`, target=`Ecsit`. Result: No (not differentially expressed)
```

Enriched version adds per-example Hagai pert |logFC|, Hagai target
|logFC|, and Replogle direct logFC (if available):
```
Example 1: pert=`Cul1`, target=`Ecsit` → No (not DE). [Hagai pert |logFC|=0.07; Hagai target |logFC|=0.02; Replogle logFC=+0.03]
```

The hypothesis was that the LLM could now compare WHICH dimensions make
each example similar to the query, not just label.

Token cost: +62 tokens total (1948 vs A12 SHIP 1886). Very dense.

## Result on probe60_rare_gene (seed=789)

| Variant | DE | DIR | LLM Combined | + hybrid |
|---|---|---|---|---|
| **A12 SHIP (plain examples)** | **0.644** | 0.540 | **0.592** | **0.625** |
| A14 enriched examples | 0.534 | 0.542 | 0.538 | 0.605 |

**Negative result**: DE dropped -0.110, Combined -0.054 (LLM-only) /
-0.020 (hybrid). Enrichment HURT.

## Why this likely failed

Looking at the per-row predictions vs A12 SHIP, the LLM seems to be
distracted by the in-example numbers. A few candidate explanations:

1. **Attention dilution**: 10 lines of "[Hagai pert=X; Hagai target=Y;
   Replogle=Z]" creates noise. The LLM may be over-focusing on these
   per-example numbers instead of the query's own Hagai + Replogle
   block.
2. **Spurious pattern fitting**: with 10 examples annotated by Hagai
   magnitude + label, the LLM may learn the in-context regression
   "low Hagai magnitude → No DE" — which is correct in principle, but
   collapses its calibration for the query itself.
3. **Format confusion**: the bracket-style annotations may compete
   with the existing structured Hagai block downstream.

## Verdict

**Revert to A12 SHIP plain examples.** Don't enrich.

## Updated design heuristic

Combining A12 + A13 + A14:

| Boilerplate type | Effect | Example |
|---|---|---|
| Passive knowledge dump | net **negative** | BMDM context paragraph |
| Active reasoning instruction | net **positive** | Decision rules R1-R5 |
| Active output structure | net **positive** | Reasoning protocol A1-B2 |
| **Active per-example data** | **net negative** | Hagai/Replogle inline per case |

The signal-density vs attention tradeoff: more detailed information per
context block may dilute the LLM's ability to attend to the query's own
features. Keep examples thin.

## Inputs / outputs

- `pipeline/prompt_builder_v3.py`: `enrich_examples: bool = False` flag
  (default off after this attempt's negative result).
- `scripts/eval_metric_v4.py`: `--enrich-examples` opt-in.
- `attempts/14_enriched_examples/outputs/probe60/single/{id}.json`
- `attempts/14_enriched_examples/prompts/example_Tlr4_Cd14_enriched.txt`
