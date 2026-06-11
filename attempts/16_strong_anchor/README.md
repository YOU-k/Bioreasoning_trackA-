# Attempt 16 — C: Strong Replogle anchoring + D: Hagai DIR signal

User asked: "is the hybrid runner post-processing of LLM output, and is
that fair?" Track-A rules (`project_info/overview.md` lines 87, 96, 111)
explicitly allow public-data-driven aggregation + retrieval, so it IS
compliant. But the spirit of "prompt-only LLM" is cleaner if the LLM
itself uses Replogle's direction. Two ablations:

- **C** (this attempt): strengthen R4 in the prompt with an explicit
  logFC-to-P_up_given_DE mapping, see if pure-LLM matches the hybrid.
- **D**: keep prompt as-is but explore Hagai DIR signal in the runner
  blend.

## C: Strong R4 prompt anchoring → FAIL

R4 was rewritten with explicit numerical mapping:
```
logFC ≥ +0.5  → P_up_given_DE ≈ 80
logFC ∈ [+0.2, +0.5) → P_up_given_DE ≈ 65
logFC ∈ [-0.2, +0.2] → P_up_given_DE ≈ 50
logFC ∈ (-0.5, -0.2] → P_up_given_DE ≈ 35
logFC ≤ -0.5  → P_up_given_DE ≈ 20
"Only override if target gene is in TLR/NLR/NF-κB/IFN-I/MHC-II program."
```

| Variant | Pure LLM Combined | + hybrid Combined |
|---|---|---|
| **A12 SHIP (vague R4)** | **0.592** | **0.643** |
| A16 strong anchor | 0.560 (-0.032) | 0.596 (-0.047) |

**Failure mode**: A06 escape-hatch pattern, even worse.

P_up = 50 frequency:
- A12 SHIP: 29/60 (48%)
- A16 strong anchor: **50/60 (83%)** — LLM clustered into the "ambiguous" prescribed value mechanically

The conditional rule "if logFC ∈ [-0.2, +0.2] → P_up ≈ 50" became the
LLM's blanket safe escape. DIR-AUROC LLM-only collapsed 0.540 → 0.478 due
to the AUROC tie penalty.

**Lesson reinforced** (now 3rd confirmation: A06, A12-A, A16):
prescriptive numerical anchors in prompts ALWAYS become escape hatches,
even when conditional. The LLM gravitates to the safest "I don't have
to commit" prescribed value rather than reasoning through the case.

**R4 reverted to A12 SHIP wording.**

## D: Hagai DIR signal in runner blend → all variants FAIL or neutral

Tested 3 variants on A12 SHIP LLM outputs (no API spend):

| Variant | DE | DIR | Combined |
|---|---|---|---|
| **D0 baseline (A15 hybrid)** | 0.644 | 0.641 | **0.643** |
| D1: raw Hagai sign for non-full rows | 0.644 | 0.618 | 0.631 (-0.012) |
| D2: significant-Hagai-only sign | 0.644 | 0.607 | 0.625 (-0.018) |
| D3: lower α when Hagai shows strong LPS regulation | 0.644 | 0.641 | 0.643 (=) |

D1/D2 confirm what A11 audit already showed: **Hagai LPS direction does
NOT transfer to CRISPRi direction**. KD of an inflammatory pathway
activator (Tlr4, Myd88) brings LPS-UP targets DOWN, flipping the sign.
KD of an inhibitor does the opposite. Without knowing which class the
pert belongs to, raw Hagai sign is misleading.

D3 (adaptive α) didn't move the needle on this 60-row sample.

**Hagai stays as a DE-magnitude-only signal**. No DIR contribution.

## Verdict

Neither C nor D improves on A15 SHIP. The hybrid runner remains the
right post-processing — it's Track-A compliant per rules, and empirically
beats prompt-only anchoring on this probe.

Ship A15 unchanged.

## Files

- `pipeline/prompt_builder_v3.py`: R4 reverted to vague version
- `scripts/explore_hagai_dir.py`: D variants (no API)
- `attempts/16_strong_anchor/outputs/probe60_log.txt`
- `attempts/16_strong_anchor/outputs/hagai_dir_variants.txt`
- `attempts/16_strong_anchor/prompts/example_{Aars_Atf4,Tlr4_Cd14,Cebpb_Hmox1}.txt`
  (the C-variant prompt that hurt)
