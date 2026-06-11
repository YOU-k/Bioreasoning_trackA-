# Literature synthesis — perturbation prediction SOTA + VCC winners

Synthesized 2026-06-11 from three parallel research subagents. Goal: understand
where our 0.643 sits in the field, what the bottleneck is, and what winning
teams in adjacent competitions actually did.

## Headline findings

1. **MLGenX Bioreasoning Challenge results NOT yet public.** Workshop is at
   ICLR 2026; no Kaggle leaderboard scrape, no team writeups, no winner
   blog posts findable. We cannot benchmark against the actual competition
   winners; we have to compare against published SOTA on the closest task
   (PerturbQA-style direction prediction).

2. **Our 0.643 Combined sits at SUMMER-band SOTA**, ~0.05 below SynthPert's
   best cell line. The field-wide ceiling for unseen-pert + unseen-readout
   direction-prediction looks like 0.65-0.73 AUROC. We are within striking
   distance of the ceiling, not far behind.

3. **Direction (up/down) is the hardest sub-task** across every recent
   benchmark. Aligns with our experience: DIR-AUROC has been the harder
   axis throughout our attempts.

4. **The "CORE" paper referenced in our `next_paradigm_gpt.md` doesn't
   exist** — GPT-fabricated. Don't cite it.

## Arc Virtual Cell Challenge 2025 winners (published)

Cell wrap-up paper: `S0092-8674(25)00675-0`. Dataset: 300K H1 hESC cells
× 300 CRISPRi perturbations. Metrics: PDS (2×) + DES + MAE.

| Place | Team | Method | Key tricks |
|---|---|---|---|
| 1st ($100k) | BioMap (BM_xTVC) | **xTrimoSCPerturb** | Improved scFoundation encoder; protein-model embeddings; disentangled cross-attention decoder; fused PDS+DES+MAE loss; pseudo-bulk training |
| 2nd ($50k) | XLearning Lab | "X" | Conditional generation, pseudo-bulk, FCN, ESM-2 embeddings, **residual learning of deltas**, metric-weighted loss |
| 3rd ($25k) | Outlier (UChicago/Dartmouth/HKU) | **TransPert** | **NO DEEP MODEL.** Pseudo-bulk + Wilcoxon DE + similarity-aware aggregation across reference cell lines + global linear scaling tuned on val. **TOPPED THE PDS LEADERBOARD.** |
| Generalist ($100k) | Altos Labs | **go-with-the-flow** | Flow-matching generative model, custom U-Net in gene-expression space, pretrained on ~7M cells, fine-tuned on H1 |

**Arc director's headline lesson (Hani Goodarzi, NeurIPS 2025)**:
> "Pure end-to-end neural networks have yet to outperform hybrid models."

A purely statistical baseline (TransPert) took the PDS crown. scGPT /
scFoundation / GEARS failed to beat linear baselines on key metrics.
Data quality and curated 300K cells beat scale.

## Published SOTA on PerturbQA-style direction prediction

Most directly comparable to Track A. Reported AUROCs across 4 cell lines:

| Method | Citation | K562 | RPE1 | HepG2 | Jurkat |
|---|---|---|---|---|---|
| SUMMER | Wu et al. ICLR 2025 | 0.62 | 0.64 | 0.65 | 0.66 |
| **SynthPert** (SOTA Sep 2025) | arXiv 2509.25346 | 0.65 | **0.73** | 0.72 | 0.65 |
| **rBio (CZI)** | bioRxiv 2025.08.18.670981 | SOTA on all four (cell-resolved numbers paywalled) |
| PBio-Agent | arXiv 2602.07408 | 0.64 | 0.60 | 0.67 | 0.68 |
| VCWorld (our paper-of-record) | arXiv 2512.00306 | F1 ~0.63 avg, AUROC not directly reported |

**Our probe60 Combined = 0.643** is squarely in SUMMER territory. Closing
to SynthPert's best (RPE1 0.73) on Track A is the realistic upper bound.

## Field-wide ceiling

Multiple independent benchmarks converge on **AUROC ~0.65-0.73 for
double-disjoint direction prediction**:

- **Kedzierska et al., Nature Methods 2025** ("Deep-learning-based gene
  perturbation effect prediction does not yet outperform simple linear
  baselines"). 5 FMs + 2 DL models vs additive baseline + mean baseline:
  none consistently wins. Quote: "increased focus on performance metrics
  and benchmarking will be instrumental."
- **PertEval-scFM** (Wenteler et al., NeurIPS 2024): "scFM embeddings do
  not provide consistent improvements over baseline models, especially
  under distribution shift."
- **Systema (Nat. Biotech 2025, s41587-025-02777-8)**: benchmark scores
  are dominated by **systematic confounder variation**, not perturbation-
  specific signal. Perturbed-mean baseline beats every method on unseen
  one-gene perturbations.
- **Virtual Cell Challenge (Cell 2025)**: 1,200+ teams. Conclusion:
  "perturbation prediction models are not yet consistently outperforming
  naive baselines."
- **Benchmarking virtual cell models in-the-wild (arXiv 2604.27646)**:
  under unseen contexts AND unseen perts (== our setup), "performance
  drops markedly" and "models fail to recover fine-grained perturbation-
  specific effects."

## Recognized bottlenecks in the field

1. **Direction (up/down) is the hardest sub-task.** Multiple papers note
   "models make numerous errors in the direction of changes."
2. **Shared transcriptional programs collapse the problem.** Thousands of
   perturbations produce similar transcriptional effects → average-over-
   training-perts predictor is hard to beat.
3. **Metric calibration confound**: MSE/Pearson can rank null predictors
   above informative ones. AUROC over balanced ternary is honest, which
   is what our competition uses.
4. **Cross-cell-type transfer is brittle.**
5. **Sampling confounds** (e.g., the per-perturbation negative sampling
   in our train set creates a different prior than natural transcriptome).

## Method-by-method specifics relevant to us

### SynthPert (arXiv 2509.25346)
- DeepSeek-R1 distill 8B + LoRA SFT
- Teacher = o4-mini generates mechanistic CoT traces from `(P, G, label)`,
  critic filters to "excellent" (~14k traces, 2% of data)
- **Predicts 3-class directly, REJECTS q/r decomposition.**
- **Pathway-RAG (EnrichR) HURT by -0.07 AUROC** in their ablation —
  consistent with our A14 finding that enrichment hurts.
- Claim: "reasoning structure matters more than factual accuracy."

### rBio (bioRxiv 2025.08.18.670981, OpenReview F63ARIi43t)
- Qwen2.5-3B + GRPO post-training
- **Soft verifiers as RL reward**: TranscriptFormer PMI, GO via ROUGE,
  MLP world-model, plus optional experimental data
- Two paradigms: RLEMF (model-feedback) and RLPK (prior-knowledge)
- Beats SUMMER, GEARS, Qwen2.5 baseline on PerturbQA DE
- This is the closest published analog to our hybrid_direction — they use
  verifier scores as REWARDS for training; we use them as POST-HOC blend
- Code: https://github.com/czi-ai/rbio

### PBio-Agent (arXiv 2602.07408)
- Multi-agent: Context / Mechanism / Network scientist + Judge ensemble
- Beats SUMMER only on HepG2/Jurkat (not K562/RPE1)
- **Names four failure modes**:
  1. Hallucinated pathways
  2. Context-agnostic prediction
  3. Functional-vs-regulatory conflation (DUSP6 example)
  4. Shallow-CoT noise

### Uncalibrated Reasoning (arXiv 2508.11800)
- GRPO induces **over-confidence on stochastic outcomes**
- Relevant: rBio uses GRPO → its probabilities may need calibration
- Reinforces the isotonic-on-validation calibration plan

### TransPert (VCC 3rd, no published preprint as of search)
- **No deep model.** Just:
  - Pseudo-bulk aggregation per perturbation
  - Wilcoxon DE between perturbed and control pseudo-bulks
  - Similarity-aware aggregation across reference cell lines
  - Global linear scaling tuned on validation
- Topped the PDS leaderboard. Strong implicit critique of deep models'
  marginal value on this kind of task.

## What this means for our Track A submission

### We are at SOTA band
Our 0.643 probe60 Combined is at SUMMER level. The gap to SynthPert's
best (0.73 RPE1) is real but the field-wide ceiling is ~0.70-0.73 — we
are within reach, not far behind.

### What's likely to lift us further (Track A constraints respected)
1. **Replogle-as-soft-verifier in prompt** (rBio mindset): instead of
   post-hoc α=0.45 blend, inject Replogle logFC magnitude+sign as an
   external rater line and let the LLM emit q/r conditional. We've tried
   strong anchoring (A16) and it failed via A06 escape-hatch. But a
   subtler "the verifier says X" framing might work where prescriptive
   numerical anchors didn't.
2. **3-class direct prediction** (SynthPert's approach): worth A/B'ing
   q/r decomposition vs direct ternary output on probe60. SynthPert beat
   their own q/r baseline with direct ternary.
3. **TransPert-style pure-statistical baseline as an upper-bound check**:
   compute pseudo-bulk-like aggregation on our train + Replogle + Hagai
   data as a no-LLM baseline. If this beats 0.643 with no LLM, we know
   the LLM is buying us nothing.

### What's unlikely to help (field-wide signal)
- More retrieval / context (SynthPert's EnrichR ablation: -0.07; our A14: -0.054)
- More prescriptive prompt anchoring (A06/A16: A06 escape hatch)
- Distribution calibration to train (our A17: hurts AUROC)
- Different LLM (Track A binds us to GPT-OSS-120B)

### What requires moving to Track C
- Synthetic CoT distillation (SynthPert): not Track A
- RL with soft verifiers (rBio): not Track A
- Fine-tuning of any kind: not Track A

## Concrete next experiments worth trying

| Experiment | Cost | Risk | Expected lift |
|---|---|---|---|
| **TransPert-style no-LLM baseline** on probe60 | 30 min code, 0 API | low | might match or beat 0.643 — diagnostic value |
| **3-class direct output** A/B vs q/r | $0.15, 5 min | medium (might break parser) | possible +0.02 per SynthPert |
| **Replogle as "external rater" line** (softer than A16 anchoring) | $0.15, 5 min | medium (A16 risk) | uncertain |
| Test set submission with A15 SHIP | ~$80 GPT-OSS-120B compute | none (we know it's compliant) | reveals true LB position |

## Key URLs (full bibliography)

| Paper | URL |
|---|---|
| MLGenX BRChallenge workshop | https://mlgenx.github.io/ |
| MLGenX proposal (OpenReview) | https://openreview.net/pdf?id=ZFg50rffJP |
| PerturbQA/SUMMER (ICLR 2025) | https://arxiv.org/abs/2502.21290 |
| SynthPert (Sep 2025) | https://arxiv.org/abs/2509.25346 |
| rBio (CZI, Aug 2025) | https://www.biorxiv.org/content/10.1101/2025.08.18.670981v2 |
| rBio code | https://github.com/czi-ai/rbio |
| BioReason (NeurIPS 2025) | https://arxiv.org/abs/2505.23579 |
| PBio-Agent | https://arxiv.org/abs/2602.07408 |
| VCWorld (ICLR 2026) | https://arxiv.org/abs/2512.00306 |
| Nature Methods 2025 FM benchmark | https://www.nature.com/articles/s41592-025-02772-6 |
| PertEval-scFM | https://www.biorxiv.org/content/10.1101/2024.10.02.616248v1 |
| Systema (Nat. Biotech 2025) | https://www.nature.com/articles/s41587-025-02777-8 |
| Virtual Cell Challenge (Cell 2025) | https://www.cell.com/cell/fulltext/S0092-8674(25)00675-0 |
| VCC wrap-up | https://arcinstitute.org/news/virtual-cell-challenge-2025-wrap-up |
| Benchmarking VCM in-the-wild (2026) | https://arxiv.org/abs/2604.27646 |
| Diversity-by-Design (metrics) | https://arxiv.org/html/2506.22641v1 |
| Tahoe-100M | https://www.biorxiv.org/content/10.1101/2025.02.20.639398v1 |
| Uncalibrated GRPO reasoning | https://arxiv.org/abs/2508.11800 |
| LLM4Cell survey | https://arxiv.org/abs/2510.07793 |
