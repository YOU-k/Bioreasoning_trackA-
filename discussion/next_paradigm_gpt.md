# Next-paradigm discussion (user × GPT, 2026-06-09)

External read on what the field — and this competition — is moving toward.
Stored verbatim as a reference document. Use as input to the attempt-06
planning decision, not as authoritative; some claims need to be checked
against our own data.

---

## TL;DR (one paragraph)

The most likely-to-work paradigm next is NOT "let the LLM think harder" and
NOT VCWorld-style long mechanistic storytelling — it is **structured
evidence engineering + contrastive reasoning + metric-aware probabilistic
ranker**. The LLM should not be the "virtual cell simulator". It should be
an **evidence compiler / conflict resolver / calibrated ranker**: front-end
generates a compact evidence packet from retrieval + KG + public perturb-seq
+ gene/protein embeddings + signed pathways + context priors; the LLM
finally emits two **decoupled** quantities:

```
q = P(DE),   r = P(up | DE)
p_up   = q · r
p_down = q · (1 - r)
```

This matches the competition metric structure exactly: DE-AUROC sees only
`p_up + p_down`, DIR-AUROC sees only `p_up / (p_up + p_down)`. So
"whether DE" and "direction conditional on DE" are two separate tasks and
should not be mashed together via 3-class softmax or voting.

---

## 1. Established arguments

### 1.1 This is OOD gene-pair rank prediction, not 3-class classification

- Data: mouse BMDM CRISPRi Perturb-seq. Row = `(perturbation, target_gene)`.
- Labels come from FDR + |log2FC| thresholds AND organizer-side negative
  sampling per perturbation.
- Test split is **double-disjoint**: test perts and test readout genes both
  unseen in train. Row-level memorization, gene-specific train prior,
  pert-specific train prior — none transfer.
- `none ≈ 55%` in train is an **artifact of negative sampling**, not the
  true (pert, gene) matrix. The true matrix is vastly sparser.
- Bottom line: the task is *"on the sampled candidate pairs, rank whether
  the pair enters the top-DE set"* — it is not full-transcriptome DE
  prediction.

### 1.2 PerturbQA: LLMs help, but raw CoT / raw RAG aren't enough

- PerturbQA shows current ML / statistics / standard LLM-reasoning all
  underperform on unseen-perturbation DE + direction.
- A domain-informed summarize–retrieve–answer framework (Summer) matches or
  beats SOTA. Lesson: LLM value comes from organizing biology semantics +
  external knowledge + experimental context into **decision-ready evidence**,
  not from free-form reasoning.

### 1.3 Foundation cell models have NOT shown stable wins over simple baselines

- Nature Methods 2025 critical benchmark: 5 FMs + 2 DL models vs simple
  baselines for perturbation effect prediction → no FM stably beats baseline.
- PertEval-scFM: similar conclusion in zero-shot. Distribution shift +
  strong/atypical perturbations are especially hard.
- Implication for this competition: do not over-trust Geneformer / scGPT /
  scFoundation / GEARS by name. They can be feature providers or teachers,
  but should be treated as **weak evidence sources**, calibrated against
  each other.

### 1.4 GEARS / CPA / scGen: the lesson is structural factorization, not blind copying

- scGen: latent-vector arithmetic for cross-context generalization.
- CPA: compositional perturbation autoencoder (factorize pert / covariate /
  dose / cell type).
- GEARS: gene–gene KG for novel single/multi-gene perturbations.

Our own Fig6 framework already captures this:

```
Y(c, p) = B_c + G_c + S_p + I(p1, p2) + C(c, p) + ε
```

Cell type is fixed = BMDM, no combo perturbations, so:

```
Y(BMDM, p) ≈ B_BMDM + G_BMDM + S_p + ε
```

The hard distinction is between generic stress/inflammatory drift (`G_BMDM`)
and perturbation-specific response (`S_p`). PCC / MSE measures mostly the
drift, not the pert-specific signal; small-effect perts inflate PCC,
large-effect perts get variance-compressed.

### 1.5 VCWorld's failure mode = the "vote-example" problem we hit

- VCWorld claims white-box mechanistic reasoning, but in practice LLMs find
  a plausible story for *almost any* pair → **"plausibility is not
  prediction"**.
- A negative label is not "no mechanism", it is "did not cross the DE
  cutoff in this specific cell context".
- Aggregate AUROC/AUPRC can be confounded by **gene response frequency**:
  a gene-prior voting baseline that ignores perturbation identity can win
  on overall metric but be ~chance on per-gene discrimination.
- Fix: replace "find a plausible mechanism" with **same-gene contrastive
  evidence organization** — for the same readout gene G, show similar perts
  that did change G AND similar perts that did not, and force the model to
  compare.

---

## 2. Candidate next-generation paradigms

### Paradigm A — CORE-style contrastive evidence reasoner *(main bet)*

Instead of asking "does pert A KD affect gene B?", build a structured
evidence packet:

```
Query:
- Perturbation P (KD in mouse BMDM)
- Readout G

Gene cards:
- P: function, pathway, regulator type, BMDM relevance
- G: function, pathway, response program, BMDM expression prior

Same-readout contrast:
- Positive supports: perts similar to P that changed G (or G's ortholog)
- Negative supports: perts similar to P that did NOT change G
- Matched controls: perts in same pathway with no G response

Mechanistic paths:
- signed KG paths P -> ... -> G, sign + confidence
- macrophage-specific context adjustment

Decision:
- q = P(DE), r = P(up|DE), final p_up, p_down
```

**Critical**: positive and negative examples must be *paired*, each with
similarity weight and context weight. Otherwise we collapse back into
gene-prior voting. CORE paper claim: gene-prior voting macro-per-gene AUROC
≈ 0.500 on PerturbQA K562 DE; CORE-Voting hits 0.711. The lift comes from
**same-gene perturbation-specific discrimination**, not from voting.

Name this:

> **same-gene, perturbation-conditioned contrastive reasoning**

Higher chance of working than VCWorld because it compresses LLM
free-storytelling space into "compare evidence".

### Paradigm B — Signed causal-pathway ranker (for direction)

Cast direction as a signed-path problem:

- P normally activates G  → P-KD → G **down**
- P normally represses G  → P-KD → G **up**
- P is upstream inhibitor → flip
- P and G share broad pathway only, no signed path → q mid, r near 0.5
- G is IFN / NF-κB / stress / antigen / metabolic / ribosomal → separate
  generic inflammatory drift from pert-specific response

Borrow GEARS' gene-gene KG concept, but don't predict a full expression
vector — only the two ranking scalars. KG produces **signed features**,
LLM does semantic arbitration, validation calibrator produces final q/r.

Feature suggestions:

| Feature group | For q | For r |
|---|---|---|
| P/G same pathway / PPI / TF-target / Reactome | strong | mid |
| signed regulatory path parity | mid | strong |
| path length / edge evidence / cell context | strong | strong |
| G is BMDM-expressed / macrophage-program | strong | mid |
| P functional class (TF / chromatin / signaling / ribosome / ...) | strong | mid |
| external perturb-seq same-gene contrast | strong | strong |
| generic stress / IFN / apoptosis confound | strong (penalize) | mid |

Suits Track B (tools can dynamically pull signed paths). For Track A,
compress top 2–4 paths into the 4k-token prompt.

### Paradigm C — Metric-aware two-head LLM ranker *(infra requirement, all tracks)*

The metric is two AUROCs:
- DE-AUROC ranks by `p_up + p_down`
- DIR-AUROC ranks by `p_up / (p_up + p_down)`

So **never** output 3-class softmax or vote labels. Output:

```
q_DE        = P(target is significantly DE)
r_UP|DE     = P(direction is up | DE)
p_up        = q_DE * r_UP|DE
p_down      = q_DE * (1 - r_UP|DE)
```

AUROC cares about **ranking**, not absolute calibration. So apply per-head
monotonic calibration / isotonic / logit stretching on validation; as long
as ranking is preserved you can stretch freely.

**Most counter-intuitive point**: high direction confidence ≠ high DE
confidence. "If it is DE, it must go up" ⇒ r ≈ 0.9, but q can still be
low. Many LLM failures are exactly this confusion.

### Paradigm D — Synthetic reasoning-trace distillation (Track C only)

- SynthPert route: frontier model generates reasoning traces from
  `(input + outcome)`; critic filters; LoRA-SFT to 8B reasoner.
- Naive `(P, G) → label` SFT is materially worse than SynthPert.
- On PerturbQA DE: RPE1 0.58 → 0.78, Jurkat 0.58 → 0.79.

For Track C: don't SFT `P, G → up/down/none`. SFT this instead:

```
P card; G card; context gate; same-gene positive evidence;
same-gene negative evidence; signed path; q/r decision
```

Hard constraint: Track C inference has **no tools, no external retrieval**.
All biology knowledge must be in weights. Big risk under <10B.

### Paradigm E — Simulator-as-teacher, not simulator-as-answer

Trend (CZI's rBio direction, BioReason): use virtual-cell models /
co-expression / GRNs to *train* reasoners, not to be the final black box.
Distill simulators into features / counterfactuals / reasoning traces /
uncertainty, not into a single label.

### Paradigm F — Causal / counterfactual evaluation paradigm

Predictive accuracy alone rewards pattern matching, not intervention
validity. For each prediction ask: "if P is swapped for another pert in
the same pathway, does G still go DE?" If the answer barely changes, the
model is using gene-prior, not pert-specific reasoning.

This is exactly our Fig6 framework's spirit.

---

## 3. Track-level win-rate guess

| Setting | Estimated ranking |
|---|---|
| Naive implementation | B > A > C |
| Strong offline evidence engineering (A) vs naive B | A ≈ B |
| Strong synthetic-trace C vs naive A | B > C ≳ A |
| Single-track ROI | A is the right starter |
| Highest absolute ceiling (with engineering) | B |
| Most-paper-friendly | A + B + C with controls |

Caveat for B: don't let the agent freely call tools per row. Build **batch
tools** that return evidence packets for many rows at once. 250 total tool
calls will not survive a per-row multi-step agent over 1,813 rows.

---

## 4. Recommended Track-A pipeline

### Step 1 — Strict double-disjoint validation

No row split. Always hold out both perts and readout genes (mimic test
exactly). Baselines to beat:

1. random / class prior
2. gene-annotation-only
3. pert-annotation-only
4. KG distance only
5. same-gene external voting
6. **same-gene contrastive evidence**
7. LLM zero-shot
8. LLM + evidence packet
9. LLM + q/r decomposition
10. evidence model + LLM arbitration

If 8/9/10 cannot beat 2/3/5, the evidence packet is contaminated by
vote-bias / gene-prior.

### Step 2 — Compressed evidence packet per row (instead of long prompt)

4k tokens is enough if extremely compressed:

```
Task:
Predict response of readout gene G after CRISPRi knockdown of P in mouse BMDM.
Output q=P(DE), r=P(up|DE), p_up, p_down.

Decision rules:
- Plausibility alone is insufficient for DE.
- q estimates whether G crosses DE threshold in this context.
- r estimates direction only conditional on DE.
- Same-gene pos/neg contrast outranks generic pathway stories.
- Penalize generic stress / broad inflammatory drift unless P-specific evidence exists.

Query: P = {pert}; G = {gene}

P card: {function; regulator type; pathways; BMDM relevance; expr prior}
G card: {function; program; BMDM expression; known inducible/stable status}

Evidence:
1. Direct / ortholog: {top 1-2}
2. Same-G contrast:
   Positive: {matched perts, similarity, context}
   Negative: {matched perts, similarity, context}
3. Signed paths: {P -> ... -> G; sign; evidence; context}
4. Confound check: {generic stress? IFN/TNF? housekeeping? low expr?}

Return:
q_DE = ...
r_UP_given_DE = ...
p_up = ...
p_down = ...
```

### Step 3 — Three-seed fusion via logit averaging on q and r separately

```
q_final = sigmoid(mean(logit(q_seed)))
r_final = sigmoid(mean(logit(r_seed)))
p_up   = q_final * r_final
p_down = q_final * (1 - r_final)
```

NOT plain p_up/p_down averaging — that pollutes DE and DIR with a single
extreme seed simultaneously.

### Step 4 — Treat "none" as an explicit positive judgment, not a fallback

Bake into the prompt:

- "no direct evidence" ≠ none
- "plausible pathway" ≠ DE
- `none` should be reached when:
  - G is low / stable in BMDM
  - P/G have only broad pathway relation, no signed path
  - same-G matched negatives outnumber matched positives
  - query P has low similarity to positive supports
  - supports are from unrelated cell lines
  - reasoning only invokes generic stress / IFN / apoptosis without
    P-specific mechanism

### Step 5 — Direction prior is NOT 0.5

Train DE distribution is `up : down ≈ 2.2 : 1`. Without direction evidence,
default `r ≈ 0.62 – 0.70`. This only nudges DIR ranking; it must NOT raise q.

---

## 5. Track B suggestion: deterministic batch evidence engine + LLM judge

Tools (6–8, all batch):

| Tool | In | Out |
|---|---|---|
| `batch_gene_cards(ids)` | many (P, G) | annotation, ortholog, pathway, BMDM prior |
| `batch_signed_paths(ids)` | many (P, G) | top signed KG paths, sign, confidence |
| `batch_external_perturb_evidence(ids)` | many (P, G) | public perturb-seq same-G pos/neg supports |
| `batch_similarity(ids)` | many (P, G) | P-to-supports similarity, G program class |
| `batch_predictor_features(ids)` | many (P, G) | non-LLM q/r priors + uncertainty |
| `batch_calibrator(ids)` | feature table | calibrated q/r suggestions |

LLM final role: detect evidence conflicts, refuse gene-prior voting, emit
q/r, produce trace.

Avoid per-row free agents — 250-call cap kills it.

---

## 6. Track C suggestion

Two paths:

- **Naive SFT on (P, G) → label**: weakest. Probably below Track A.
- **SynthPert-style synthetic-trace distillation**: high ceiling, high
  engineering cost, high private-LB variance.

If doing the second:

- Train on `(P card, G card, context gate, same-G contrast, signed path,
  DE evidence, direction evidence, q/r)`, not on raw labels.
- Allow "I don't know / weak evidence" in synthesized traces.
- Loss = SFT explanation + **pairwise ranking on q** + **pairwise ranking
  on r (DE rows only)**.
- Predistill public biology QA into the model (otherwise the model has
  no idea what mouse gene symbols mean).

---

## 7. Ablations to run before believing any score

| Ablation | What it checks |
|---|---|
| Target-gene-only baseline | are we just predicting gene response frequency? |
| Perturbation-only baseline | are we just predicting pert potency? |
| Support-label shuffle | does evidence packet actually depend on matched evidence? |
| Pos-only vs pos + neg | does contrast matter? |
| Remove signed paths | does direction depend on causal sign? |
| Remove BMDM context | does it over-transfer K562/RPE1/HepG2? |
| q/r split vs direct p_up/p_down | does metric-aware decomp help? |
| Numeric vs 3-class vote | are AUROC ties from coarse output? |
| **Macro-per-gene validation** | are we secretly using gene-prior? |
| **Double-disjoint validation** | are we overfitting public LB? |

Macro-per-gene + double-disjoint are the most important. Overall AUROC
high + macro-per-gene flat = the model is gene-prior, not pert-specific.

---

## 8. One-line summary of the proposed next-gen paradigm

> "LLM-as-reasoner for perturbation response" moves from
> **plausible-CoT** → **contrastive evidence-grounded probabilistic ranking**:
> evidence packets, matched pos/neg supports, q/r two-head decomposition,
> macro-per-gene + counterfactual auditing, simulators as teachers (not
> answers), evidence engineering + calibration engineering.

Concrete bets per track:

- **Track A**: compressed contrastive evidence packet + q/r numeric output.
- **Track B**: batch tools that produce that same evidence packet; LLM
  only arbitrates.
- **Track C**: SynthPert-style synthetic traces + q/r pairwise ranking loss.
