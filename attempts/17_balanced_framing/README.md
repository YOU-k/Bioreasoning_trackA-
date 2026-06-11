# Attempt 17 — Inject "balanced dataset" framing into R1 → FAIL (counter-intuitive)

## Why we tried this

User pointed out that the LLM is severely under-predicting DE:
- Train P(DE) = 0.447, LLM mean P_DE = 0.241 (-46%)
- 22/60 rows clustered at P_DE = 20 (LLM's conservative default)

Root cause hypothesis: prompt + LLM's pretraining prior assume natural
transcriptome (~1-5% DE), but the competition data is intentionally
balanced per-perturbation (~9 top DEGs + ~9 non-DE controls per pert, so
~45% of pairs in the dataset are DE).

The old R1 also actively biased the LLM toward low P_DE:
> "Absence of pert-specific evidence is itself evidence FOR `none`."

We modified R1 to inject the balanced-sampling framing **without** any
prescriptive numerical default (A06 lesson):
- Tell LLM the base rate is ~45% (factual, not "default to this")
- Reframe low P_DE band as requiring "active counter-evidence", not absence
- Frame the task as "RANK relative confidence among pre-selected candidates"

## Result on probe60 (seed=789)

The distribution shift worked **exactly as intended**:

| Metric | A12 SHIP | A17 balanced framing |
|---|---|---|
| P_DE mean | 0.241 | 0.411 (close to train 0.447) ✅ |
| P_DE median | 0.200 | 0.400 ✅ |
| P_DE std | 0.174 | 0.196 (wider) ✅ |
| Rows at P_DE = 20 | 22 | 11 (cluster halved) ✅ |
| Top-5 P_DE values | 20, 15, 25, 35, 10 | 20, 55, 40, 35, 60 ✅ |

But AUROC went **down**:

| Metric | A12 SHIP | A17 |
|---|---|---|
| **DE-AUROC** | **0.644** | 0.548 (-0.096) ❌ |
| DIR-AUROC LLM-only | 0.540 | 0.467 (-0.073) |
| Combined LLM-only | 0.592 | 0.508 (-0.084) |
| **Combined hybrid** | **0.643** | 0.577 (-0.066) |

## Why distribution-matching HURT AUROC

```
A12 SHIP P_DE distribution:
   70-95 band:  ~7 rows of high-confidence DE      (clean signal)
   ↑↑↑ separated cleanly by 50+ AUROC gap ↑↑↑
   15-25 band: 22 conservative-default rows       (mixed true DE + true none, but tied)

A17 spread:
   70-95 band:  ~7 rows of high-confidence DE      (same)
   ↕ middle band 35-60: 21 rows ↕                  (true DE + true none MIXED in middle)
   15-25 band: 11 counter-evidence rows            (still ties some)
```

The conservative-bias-at-20 was **actually preserving rank info**:
- True DE rows are mostly ranked high (70+) when LLM is confident
- True `none` rows + uncertain rows cluster at 20 (with some ties)
- Ranking: high-confidence DE > 20-cluster → DE-AUROC ~ 0.65

After spreading:
- High-confidence DE stays at 70+ (unchanged)
- Middle band now holds BOTH true DE and true `none` that LLM is unsure
  about — these mix in the new ranking middle
- Ranking is noisier in the middle → DE-AUROC drops

## Counter-intuitive lesson

> Calibration ≠ AUROC improvement.

AUROC only cares about RANKING. Compressed LLM output that biases
"uncertain" toward the majority class (`none`) can rank better than a
properly-calibrated output that spreads uncertain rows into the middle.

Distribution matching with the training base rate **adds noise to the
middle of the ranking** without improving the high-confidence rank
separation that drives DE-AUROC.

## Verdict

**Revert R1 to A12 SHIP language.** Ship A15 stays.

The user's distribution information is real, but using it for direct
calibration in the prompt does not help. Other potential uses:

- **As a calibration target for downstream stacking / ensemble** (when we
  ship multiple seeds or models)
- **As a sanity check on test submission output** (if Combined LB is too
  high or too low, calibration drift might explain part of it)
- **As a target for isotonic regression** post-hoc — but again,
  monotonic transforms don't change AUROC

## Files

- `pipeline/prompt_builder_v3.py`: R1 reverted to A12 SHIP wording
- `attempts/17_balanced_framing/outputs/probe60_log.txt`
- `attempts/17_balanced_framing/prompts/example_*.txt`
