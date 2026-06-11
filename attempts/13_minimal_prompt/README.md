# Attempt 13 — Probe whether Decision rules and Reasoning protocol are also boilerplate

## Why

A12 showed the 723-token `## Cell context (BMDM)` paragraph was actively
hurting. Two more hand-written blocks remain in the prompt:

- **Decision rules R1-R5** (~470 tokens): "R1 plausibility ≠ prediction",
  "R2 BMDM context", "R3 Hagai magnitude only", "R4 Replogle direction
  transfer", "R5 two integers independent".
- **Reasoning protocol A1-B2** (~290 tokens): "Step A1 mechanism class",
  "Step A2 BMDM relevance", ... "Step B2 direction call".

Both are static across queries. Are they earning their tokens?

## Method

Three new probe60_rare_gene runs (seed=789), comparing to A12 SHIP:

| Variant | rules | protocol | tokens (typ.) |
|---|---|---|---|
| A12 SHIP (C-only) | ✓ | ✓ | 1886 |
| no Decision rules | ✗ | ✓ | 1417 |
| no Reasoning protocol | ✓ | ✗ | 1593 |
| no rules + no protocol | ✗ | ✗ | 1124 |

## Results

| Variant | Pure LLM | + hybrid runner |
|---|---|---|
| **A12 SHIP** | **DE 0.644 / DIR 0.540 / Combined 0.592** | **0.644 / 0.605 / 0.625** |
| no Decision rules | 0.553 / 0.467 / 0.510 | 0.553 / 0.591 / 0.572 |
| no Reasoning protocol | 0.549 / 0.395 / 0.472 | 0.549 / 0.587 / 0.568 |
| no rules + no protocol | 0.502 / 0.487 / 0.495 | 0.502 / 0.627 / 0.564 |

### Effect sizes

- Drop Decision rules: **-0.082 Combined** (LLM-only), **-0.053** (+ hybrid)
- Drop Reasoning protocol: **-0.120 Combined** (LLM-only), **-0.057** (+ hybrid)
- Drop both: -0.097 / -0.061

Both ablations exceed the ~0.04 sampling-noise band on 60 rows.

The hybrid runner cushions the loss somewhat (because the Replogle blend
contributes most of DIR's signal, so a worse LLM DIR call has less impact).
But even with hybrid, the LLM-only DE collapse (0.644 → 0.549 / 0.553) drags
Combined down 0.05-0.06.

## Verdict

**KEEP both Decision rules and Reasoning protocol.** Neither is passive
noise — both are load-bearing for LLM reasoning quality.

A12 SHIP remains the recommended config: rules + protocol ON, BMDM context
paragraph OFF, hybrid runner ON.

## Design heuristic

| Boilerplate type | Effect | Example |
|---|---|---|
| Passive knowledge dump | Net negative | BMDM context paragraph |
| Active reasoning instruction | Net positive | Decision rules R1-R5 |
| Active output structure | Net positive | Reasoning protocol A1-B2 |

Future prompt edits: prefer instructions that change HOW the LLM thinks,
not facts the LLM should know. The LLM has its own knowledge; what it
needs from us is process guidance.

## Inputs / outputs

- `pipeline/prompt_builder_v3.py`: `include_decision_rules: bool = True`
  and `include_reasoning_protocol: bool = True` flags (both default True).
- `scripts/eval_metric_v4.py`: `--no-decision-rules` and
  `--no-reasoning-protocol` ablation flags.
- `scripts/compare_a13_variants.py`: 4-way comparison utility.
- `attempts/13_minimal_prompt/outputs/probe60_{no_rules,no_proto,no_both}_log.txt`
- `attempts/13_minimal_prompt/outputs/comparison.txt`
- `attempts/13_minimal_prompt/prompts/example_Tlr4_Cd14_*.txt` — 4 variants for inspection
