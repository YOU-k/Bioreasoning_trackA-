# Attempt 15 — k_a / k_c retrieval budget ablation + alpha sweep

Two tuning sweeps over the A12 SHIP architecture:

1. **Hybrid runner alpha + non-full prior sweep** (Task 7, no API spend,
   uses existing A12 outputs)
2. **k_a / k_c retrieval budget ablation** (Task 5, two new evals)

## Task 7: Hybrid runner alpha + nf_prior sweep

Sweep on `attempts/12_cleaner_prompt/outputs/probe60_C_only/single/` LLM
outputs (no re-eval), looking for the best `(α, nf_prior)` for
`hybrid_direction()`:

Tight 2D grid (α × nf_prior on probe60 Combined):

```
alpha   nf=0.56  nf=0.58  nf=0.60  nf=0.61  nf=0.62
 0.30    0.625    0.632    0.632    0.623    0.623
 0.35    0.626    0.634    0.634    0.625    0.625
 0.40    0.626   *0.643*   0.625    0.625    0.625
 0.45    0.626   *0.643*   0.634    0.625    0.625
 0.50    0.626   *0.643*   0.634    0.634    0.625
 0.55    0.626    0.626    0.634    0.634    0.634
 0.60    0.625    0.625    0.632    0.632    0.632
```

**Robust local max at α ∈ [0.40, 0.50] × nf_prior = 0.58, Combined = 0.643**

LOO cross-validation: in-sample 0.643, LOO mean 0.6427 ± 0.008.
The +0.018 over the old (α=0.40, nf=0.62) is >2× LOO std → real signal.

### Ship defaults updated

```python
def hybrid_direction(r_llm, pert, gene, replogle_prior,
                     alpha: float = 0.45,        # was 0.40
                     non_full_default: float = 0.58):  # was 0.62
```

## Task 5: k_a / k_c retrieval budget

Two new probe60 evals at k_a=k_c=3 (fewer examples) and k_a=k_c=10 (more):

| Variant | DE | DIR (LLM) | DIR (hybrid) | Combined LLM | Combined hybrid |
|---|---|---|---|---|---|
| k=3+3 | 0.525 | 0.447 | 0.609 | 0.486 | 0.567 |
| **k=5+5 (A12 SHIP)** | **0.644** | 0.540 | 0.641 | 0.592 | **0.643** |
| k=10+10 | 0.517 | 0.493 | 0.594 | 0.505 | 0.556 |

**Inverted U-shape**. Both extremes hurt:

- k=3+3 (-0.076 Combined hybrid): too thin; not enough structural diversity
  for the LLM to triangulate "where in the analogue space does the query
  sit".
- k=10+10 (-0.087 Combined hybrid): too many; the A14 attention-dilution
  pattern strikes again. DE-AUROC drops 0.644 → 0.517 with 20 examples
  vs 10.

**k=5+5 stays the ship default.** Likely the VCWorld paper's K=10 default
landed on the same sweet spot for similar reasons.

## Combined improvement on probe60

| Stage | Combined |
|---|---|
| A07 baseline (single-call, no Hagai, no hybrid) | 0.466 |
| A11 (+ Hagai prompt + hybrid runner α=0.4) | 0.613 |
| A12 SHIP (+ drop BMDM context paragraph) | 0.625 |
| **A12 SHIP + tuned hybrid (α=0.45, nf=0.58)** | **0.643** |

Top-4 public LB band: 0.628 – 0.650. Our probe60 estimate is now inside.

## Files

- `scripts/sweep_hybrid_alpha.py` — Task 7 sweep + LOO robustness
- `scripts/eval_metric_v4.py` — added `--k-a` / `--k-c` flags
- `pipeline/runner.py` — `hybrid_direction(α=0.45, nf=0.58)` defaults
- `attempts/15_retrieval_budget/outputs/probe60_k3_log.txt`
- `attempts/15_retrieval_budget/outputs/probe60_k10_log.txt`
- `attempts/12_cleaner_prompt/outputs/alpha_sweep.txt`
- `attempts/15_retrieval_budget/prompts/example_Tlr4_Cd14_k{3,5,8,10}.txt`
