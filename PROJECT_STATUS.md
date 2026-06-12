# Project status — Bioreasoning Challenge Track A

**As of 2026-06-12.** Single document capturing everything a fresh
session needs to know without re-reading every `progress.md` entry.

---

## 0. URGENT — first LB submission landed (2026-06-12 03:26 UTC)

**LB v3 score = 0.510, rank 31/34** (account: `chloe9698`).
Probe60 estimate was 0.643. Gap = **-0.133**.

Three submissions failed before v3 succeeded:
| # | Time UTC | Error |
|---|---|---|
| 1 | 03:10 | "missing required column(s): `prompt_tokens`" |
| 2 | 03:11 | same |
| 3 | 03:18 | "Prompt-token limit exceeded: max 4,096, reports 6,066" (prompt.txt too long) |
| **4** | 03:26 | ✓ complete, score 0.510 |

**Critical schema discrepancies our docs got wrong:**
- `project_info/overview.md:83` documented `tokens_used` column, but Kaggle
  actually requires `prompt_tokens`. Our `pipeline/runner.py` and
  `scripts/submission_dry_run.py` wrote `tokens_used` → would be rejected.
  **FIXED** in commit after the LB landed: all three files now write
  `prompt_tokens`.
- The packaged `prompt.txt` must fit under 4,096 tokens. Our previous
  `submission_dry_run.py` rendered a full per-query prompt (~6,000+ tokens)
  → would be rejected. **FIXED**: now renders only the static template
  skeleton (header + rules + protocol + tier ladders + output format =
  ~1,475 tokens).

**Unanswered: why 0.510 LB vs 0.643 probe60.** Hypotheses, in
likelihood order:
1. **GPT-OSS-120B output quality << DeepSeek-Reasoner** on this prompt.
   Our entire tuning ran on DeepSeek. The local vLLM GPT-OSS-120B may
   format-fail often → parser falls back to defaults (P_DE=0.45,
   P_up=0.5) → mass of identical predictions → AUROC near 0.5.
2. **Hybrid runner not applied** in v3 submission (would need to inspect
   the submitted CSV to confirm).
3. **Wrong hybrid params** in v3 (e.g. A11 era α=0.40 nf=0.62 instead of
   A15 tuned α=0.45 nf=0.58).
4. **Probe60 estimate was optimistic** despite signal-coverage match.

The submission CSV ref is `/submissions/53587655/53587655.raw` but Kaggle
doesn't allow re-downloading own submissions for inspection.

---

## 1. The competition (one paragraph)

MLGenX@ICLR 2026 Bioreasoning Challenge, Track A (prompt-only LLM).
Predict ternary CRISPRi response (`up` / `down` / `none`) for unseen
`(perturbation, target_gene)` pairs in mouse bone-marrow-derived
macrophages (BMDM). Train = 7,705 rows (482 perts × ≤9 top DEGs + ≤9
non-DE controls per pert). Test = 1,813 rows, **double-disjoint** (test
perts AND test readout genes both absent from train). Metric: average
of two AUROCs — DE-AUROC (binary `up∪down` vs `none`, score = `p_up + p_down`)
and DIR-AUROC (binary `up` vs `down` on true-DE rows only,
score = `p_up / (p_up + p_down)`). Track A rules: GPT-OSS-120B, 4,096
prompt tokens, 3 samples per question with seeds 42/43/44.

## 2. Current ship config — A15 SHIP + A12 prompt

### Code paths
- Prompt builder: `pipeline/prompt_builder_v3.py:build_track_a_prompt`
- Runner: `pipeline/runner.py:assemble_submission` (with `apply_hybrid_direction=True`)
- Eval (probe60): `scripts/eval_metric_v4.py`
- Submission zip: `scripts/submission_dry_run.py`
- Tests: `pipeline/tests/test_prompt_v3.py` (7/7 pass)

### Exact configuration

```python
build_track_a_prompt(pert, gene,
    k_a=5, k_c=5,                          # paper §3.4.2 analog + contrast retrieval
    include_bmdm_context=False,            # A12 finding: 723-token paragraph HURTS
    include_decision_rules=True,           # A13 confirms: load-bearing
    include_reasoning_protocol=True,       # A13 confirms: load-bearing
    enrich_examples=False,                 # A14 finding: per-example data HURTS
    hide_example_labels=False,             # A18 finding: labels worth ~0.04 AUROC
)

assemble_submission(...,
    apply_hybrid_direction=True,           # A11: necessary
    hybrid_alpha=0.45,                     # A15: tuned from 0.40
    hybrid_non_full_default=0.58,          # A15: tuned from 0.62
)
```

### Probe60 score
**Combined = 0.643** on probe60_rare_gene (60 train rows where the
readout gene appears 2-4× in train, mimicking the test set's gene-
disjoint structure). Top-4 public LB band is 0.628-0.650.

### Signal sources
| Source | File | Coverage on test | Role |
|---|---|---|---|
| Replogle K562+RPE1 CRISPRi | `data/replogle_de.pkl` | 55% full-tier | Direction + magnitude scalar |
| Hagai mouse BMDM LPS6h | `data/hagai_lps_prior.json` | 64% (pert or gene) | Magnitude only (LPS sign ≠ CRISPRi sign) |
| STRING + Reactome KG | `data/kg_index/` | 98% pert / 81% gene | Analog/contrast retrieval |
| NCBI/MGI descriptions | `data/gene_desc.json` | 89% genes | Per-gene context in prompt |
| Train up:down ratio (2.2:1) | runner constant | 45% non-full-tier rows | DIR fallback = 0.58 |

## 3. The improvement journey (A07 → A15)

| Attempt | Combined | Δ | Key change |
|---|---|---|---|
| A07 baseline (single-call, no Hagai, no hybrid) | 0.466 | — | Track-A compliant starting point |
| A11 (+ Hagai mouse prior in prompt + hybrid runner α=0.4) | 0.613 | +0.147 | Hagai = the missing mouse-native signal |
| A12 SHIP (+ drop hand-written BMDM context paragraph) | 0.625 | +0.012 | Drop passive knowledge dumps |
| **A15 SHIP (+ tuned hybrid α=0.45, nf=0.58)** | **0.643** | **+0.018** | LOO-validated 2D sweep |

## 4. Validated negative results (don't redo)

Each row below was tested and **HURT or did not help** at α-LOO-significant
level. Listed so future iterations don't repeat them.

| # | Lever tested | Outcome on probe60 | Lesson |
|---|---|---|---|
| A06, A12-A, A16 | **Prescriptive numerical anchors in prompt** (default P_up=62; logFC→band mapping) | Up to -0.10 Combined. 50-83% rows cluster at the prescribed value | LLM uses any printed number as an escape hatch. Never prescribe a specific value to default to, even conditionally. |
| A14 | Per-example enrichment (Hagai + Replogle inline per case) | DE-AUROC 0.644 → 0.534 (-0.110) | Attention dilution. SynthPert independently found pathway-RAG HURT 0.07 AUROC. Don't add per-example info. |
| A13 | Drop Decision rules R1-R5 | -0.082 LLM-only | Active reasoning instructions are load-bearing |
| A13 | Drop Reasoning protocol A1-B2 | -0.120 LLM-only | Active output structure is load-bearing |
| A15 | k=3+3 or k=10+10 retrieval | -0.076 / -0.087 hybrid | Inverted-U around k=5+5 (paper §3.4.2 default is right) |
| A16-C | Strong R4 anchoring "MUST copy Replogle sign" | -0.047 hybrid. 50/60 rows at P_up=50 | 3rd confirmation of the A06 escape-hatch pattern |
| A16-D | Hagai DIR signal in runner blend (3 variants) | -0.012 to -0.018 or neutral | LPS direction ≠ CRISPRi direction (sign flips depending on pert role) |
| A17 | "Balanced dataset" framing in R1 (no numbers, just description) | -0.066 hybrid even though P_DE distribution shifted exactly as intended | **Calibration ≠ AUROC.** Compressed LLM output that ties true `none` at the low band was preserving rank structure; spreading uncertain rows into the middle band introduced noise. |
| A18 | Remove example labels entirely | -0.021 hybrid | Labels carry ~0.04 of signal; not catastrophic to remove but not free |
| A19 | Imbalanced example ratios (7+3, 3+7) | -0.087 to -0.10 hybrid | Imbalance is uniform/non-row-specific shift = pure noise for AUROC |
| A+B (deferred sweep) | Logit-space blend in hybrid | 0.643 (identical to linear) | Logit ≈ linear in our r range (away from 0/1 extremes) |
| A+B (deferred sweep) | Per-row adaptive α based on \|Replogle logFC\| | -0.018 hybrid | Even when Replogle is confident, LLM's contribution has BMDM-specific value |

## 5. Validated **prompt-design heuristic** (from A12-A14)

| Boilerplate type | Effect | Example |
|---|---|---|
| **Passive** knowledge dump | net **negative** (drop it) | BMDM cell-state paragraph (A12) |
| **Active** reasoning instruction | net **positive** (keep) | Decision rules R1-R5 (A13) |
| **Active** output structure | net **positive** (keep) | Reasoning protocol A1-B2 (A13) |
| **Active per-example data** | net **negative** (don't enrich) | Hagai/Replogle inline per case (A14) |

> Heuristic: prefer instructions that change HOW the LLM thinks; drop
> facts the LLM already knows. LLM has its own biology knowledge; what
> it needs from us is process guidance, not facts dump.

## 6. Where we sit vs the field (from `discussion/literature_synthesis_2026-06-11.md`)

| Method | DE-AUROC | DIR-AUROC | Citation |
|---|---|---|---|
| SUMMER (PerturbQA baseline) | 0.58-0.65 | 0.62-0.66 | Wu et al., ICLR 2025 |
| **Our A15 SHIP probe60** | **0.644** | **0.641** | this project |
| SynthPert (SOTA Sep 2025) | 0.65-0.79 | 0.65-0.73 | arXiv 2509.25346 |
| rBio (CZI, SOTA all 4 cell lines) | not directly numeric | not directly numeric | bioRxiv 2025.08.18.670981 |
| VCWorld | F1 ~0.63 | not directly | arXiv 2512.00306 |

**We are at SUMMER-band SOTA.** Gap to SynthPert (best 0.73 RPE1) is
real but ≤0.10. **Field-wide ceiling for unseen-pert + unseen-readout
direction prediction is 0.65-0.73** (multiple independent benchmarks
converge: Nature Methods 2025, Systema, PertEval-scFM, Virtual Cell
Challenge 2025).

### Field-recognized bottlenecks that align with our experience
- Direction (up/down) is harder than DE detection
- Pathway-RAG enrichment HURTS (SynthPert -0.07; our A14 -0.054)
- Foundation models don't beat additive baselines on this task shape
- Cross-cell-type transfer is brittle
- Sampling/sampling-design confounds dominate metric scores

### Arc Virtual Cell Challenge 2025 winners (related but distinct task)
1. BioMap **xTrimoSCPerturb** — scFoundation + ESM-2 + cross-attention
2. XLearning Lab **"X"** — residual delta learning + ESM-2
3. **Outlier TransPert** — **no deep model**, just pseudo-bulk + Wilcoxon
   + similarity aggregation + linear scaling — **topped the PDS LB**
4. (Generalist) Altos **go-with-the-flow** — flow-matching U-Net

Arc director Hani Goodarzi at NeurIPS 2025: *"Pure end-to-end neural
networks have yet to outperform hybrid models."* A no-LLM purely-
statistical method beat all deep models on PDS.

## 7. What's left to try (in Track A constraints)

| Experiment | Cost | Risk | Realistic lift |
|---|---|---|---|
| **TransPert-style no-LLM baseline** on probe60 | 30 min, 0 API | low | diagnostic: if ≥ 0.643, LLM contribution is zero |
| **3-class direct output** vs q/r A/B | $0.15 | medium (parser) | possibly +0.02 (SynthPert rejected q/r in their setup) |
| **Replogle as "external rater" line** in prompt (softer than A16) | $0.15 | medium (A16 risk) | uncertain |
| **Other Task3_data datasets** (Tahoe / Kang / Perturb_KHP) as additional priors | half-day | low-medium | covers the 28% of test on prior fallback |
| **Pre-submission**: diff against `sample_submission_track_a.csv` from Kaggle | 15 min | none | catches BOM/precision/line-ending quirks |
| **Ship A15 SHIP** end-to-end via GPT-OSS-120B on LLM server | ~$80 compute | none (P2 validated zip) | reveals true LB position |

### What's out of scope (Track A binds us)
- Synthetic CoT distillation (SynthPert): requires fine-tuning → Track C
- RL with soft verifiers (rBio): requires post-training → Track C
- Different LLM than GPT-OSS-120B: rule violation

## 8. P2 dry-run status (✓ done, 2026-06-11)

`scripts/submission_dry_run.py` validates the end-to-end pipeline with
synthetic LLM responses across all 1,813 test rows:

```
[1/4] 1813 rows × 3 seeds = 5439 synthetic response files written
[2/4] submission.csv assembled (1.5 MB)
[3/4] 14 columns in exact spec order; floats in [0,1]; no nulls; ✓
[4/4] submission_dryrun.zip = [submission.csv, prompt.txt] only; 130 KB
```

Pipeline is submission-ready. Drop real GPT-OSS-120B outputs into the
same `outputs/{seed}/{id}.txt` layout and re-run the script to produce
the actual submission zip.

## 9. Data sync to LLM server

User confirmed (2026-06-11) the following files were rsynced to
`root@aipaas.miracle.ac.cn:/workspace/volume/data/yy/Bioreasoning_trackA/data/`:
- `data/train.csv` (220 KB)
- `data/test.csv` (48 KB)
- `data/replogle_de.pkl` (196 MB)

Everything else (`hagai_lps_prior.json`, `gene_desc.json`,
`mouse_to_human_ortholog.json`, `kg_index/*.json`) is in git and arrives
via `git pull` on the remote.

## 10. Recommended next step

**Ship A15 SHIP.** Reasoning:

1. We are at SUMMER-band SOTA. Further prompt ablations have diminishing
   returns — 5 consecutive attempts (A14, A16, A17, A18, A19) found
   no improvement.
2. The literature confirms the field-wide ceiling is 0.65-0.73 for our
   task shape. We are within reach.
3. The 0.643 probe60 estimate has been LOO-validated; signal coverage
   distribution matches test (T0/T1/T3 = 55/35/8% on probe60 vs 54/37/9%
   on test).
4. P2 dry-run is green. P1 just needs the LLM server run.
5. The true LB number — not more probe60 grid search — is the next piece
   of decision-relevant information.

If LB lands ≥ 0.55, ship cycle is complete. If LB lands < 0.55 or
unexpectedly low, the diagnostic experiments above (TransPert baseline,
3-class output, additional Task3 data) become priority.

## 11. File / directory map (concise)

```
pipeline/
  prompt_builder_v3.py      ← single-call Track-A prompt (A15 SHIP)
  retrieve_examples.py      ← analog + contrast retrieval (k=5+5)
  hagai_prior.py            ← Hagai mouse-BMDM LPS lookup
  replogle_prior.py         ← Replogle K562+RPE1 ortholog logFC
  kg_retrieval.py           ← STRING + Reactome KG
  gene_desc.py              ← NCBI/MGI gene descriptions
  bmdm_context.py           ← (kept for reproducibility; not in current ship)
  runner.py                 ← assemble_submission + hybrid_direction + fuse_q_r_logit
  output_parser.py          ← extract P_DE, P_up_given_DE
  tests/                    ← 30/30 unit tests passing

scripts/
  build_hagai_prior.py      ← one-time Hagai DE table
  audit_baselines.py        ← gene-only, pert-only baselines
  audit_test_signal.py      ← test signal coverage by tier
  audit_baselines_rare.py   ← same on probe60_rare_gene
  ablate_replogle_blend.py  ← α sweep (A11)
  sweep_hybrid_alpha.py     ← 2D α × nf sweep (A15)
  explore_hagai_dir.py      ← D variants (A16-D)
  explore_ab_runner.py      ← logit-space blend + adaptive α (A+B)
  compare_a11_variants.py   ← A12 ablation comparison
  compare_a13_variants.py   ← A13 ablation comparison
  eval_metric_v4.py         ← probe60 single-call eval with all flags
  eval_metric_v3.py         ← probe60 two-prompt eval (A04/A05)
  submission_dry_run.py     ← P2 end-to-end validator

attempts/  (NN_short_name/{README,result}.md; outputs/ gitignored)
  01..09  cross-species pilot, baseline, KG, VCWorld port, paper-faithful,
          single-call, anchored→tiered, baseline audit, probe60_rare_gene
  10      test signal coverage audit
  11      Hagai prior + hybrid runner (the inflection point)
  12      drop BMDM context (SHIP candidate)
  13      decision rules + reasoning protocol ablation (confirm keep)
  14      enriched examples (FAIL, attention dilution)
  15      α/nf hybrid tuning + k_a/k_c retrieval budget (final A15 SHIP)
  16      strong R4 anchoring + Hagai DIR (both FAIL)
  17      balanced dataset framing (FAIL, calibration ≠ AUROC)
  18      hide example labels (mild loss, ~0.04 AUROC of label signal)
  19      example ratio sensitivity (imbalance HURTS uniformly)
  20      submission format dry-run (✓ green)

discussion/
  analysis.md                       ← original four-layer plan
  tricks.md                         ← brainstorm of leverage points
  vcworld_paper.txt                 ← cited paper, searchable
  next_paradigm_gpt.md              ← GPT brainstorm (some refs fabricated)
  literature_synthesis_2026-06-11.md← full field synthesis (NEW)
  Fig6_decomposition_framework_writeup_中文版.pdf  ← gitignored reference

plans/plan.md                       ← live forward-looking queue
progress.md                         ← append-only history (full chronology)
PROJECT_STATUS.md                   ← THIS document (single source of truth)
```
