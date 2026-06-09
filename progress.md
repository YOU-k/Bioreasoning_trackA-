# Progress log

Append-only. One block per completed attempt. Newest at the top.

---

## 2026-06-09 · infra · Track-A compliance note + local GPT-OSS batch harness

Validated the local GPT-OSS path for attempt-05-style prompts and recorded the
current Track-A compliance interpretation.

**Compliance note**
- Kaggle Track A is safest to read as **3 total calls per question**: one call
  each for seeds 42 / 43 / 44.
- Therefore the current attempt-04/05 research surface (separate DE prompt +
  DIR prompt per seed) is useful for ablation and local validation, but should
  not be treated as the final submission path without collapsing it back to one
  prompt per seed.

**Infra / code changes**
- Fixed repo-root path assumptions in `pipeline/{replogle_prior,kg_retrieval,gene_desc,retrieve_examples,runner}.py` so the current workspace data layout works.
- Added task-specific parsers in `pipeline/output_parser.py`:
  `extract_p_de(...)` and `extract_p_up_given_de(...)`.
- Added `scripts/make_submission_v2.py` for DE/DIR split-output schema checks.
- Added `scripts/test_gptoss_attempt05_local.py` (single-pair local GPT-OSS smoke test).
- Added `scripts/run_inference_v2_local.py` (local batch runner for attempt-05 DE/DIR outputs).

**Retrieval fix**
- `pipeline/retrieve_examples.py` now falls back from BOTH-anchor retrieval to
  SINGLE-anchor retrieval when one side has no KG neighborhood.
- On the first 300 test rows, empty retrieval rates dropped from:
  - DE: 121 -> 9
  - DIR: 129 -> 9
  - both empty: 121 -> 9

**Local GPT-OSS findings**
- Single-pair smoke test (`Aars -> Atf4`): DIR prompt reached
  `P_up_given_DE: 95`; DE prompt often leaked `P_DE` mid-output but still
  tended to overrun the output budget.
- Dual-GPU batch (`limit=10`, seed 42) completed successfully with
  `tensor_parallel_size=2`.
- Output quality is still weak: DE extraction ok on 4/10 rows, DIR extraction
  ok on 1/10 rows; most rows hit the 1200-token output cap.

**Submission assembly**
- Built a schema-check zip containing `submission.csv` + `prompt.txt` to verify
  packaging only. It is not a real final submission because the staged run
  mirrors seed 42 into seeds 43/44 and uses the non-compliant DE/DIR split
  research surface.

---

## 2026-06-08 (later) · attempt 05 · Paper-faithful VCWorld port (real labels)

Re-read the actual paper (Wei et al., ICLR 2026 — `discussion/vcworld_paper.txt`)
and discovered attempt 04 was built on a misreading of VCWorld. The randomized-
label rendering we used came from `src/cli_pipeline/stages/prompt.py:61`
(`random.choice(choices)`), but **paper §3.4.2 + Appendix D** retrieve **analogue
+ contrast subsets with real labels**, ranked by similarity within each pool.
Structural pos/neg mix defeats vote bias without destroying empirical signal.

**Implementation**
- `pipeline/retrieve_examples.py`: added `retrieve_analog_contrast(pert, gene, task='de'|'dir', k_a, k_c)` and `format_block_analog_contrast(...)`. Removed `format_block_random_labels`.
- `pipeline/prompt_builder_v2.py`: `build_de_prompt` and `build_dir_prompt` now use analog+contrast retrieval with real labels (k_a=5 + k_c=5, total budget unchanged).
- `pipeline/tests/test_retrieve_analog_contrast.py`: 5 new tests; 29/29 pipeline tests green.
- `scripts/eval_metric_v3.py`: eval runner pointing to `attempts/05_paper_faithful/outputs/eval60/`.

**Result on the same 60 train rows (seed=123)** — **TIE with attempt 04**

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| Attempt 03 (one prompt) | 0.654 | 0.451 | 0.552 |
| Attempt 04 (random labels) | 0.601 | 0.679 | **0.640** |
| **Attempt 05 (real labels, paper)** | **0.610** | 0.665 | **0.637** |

DE +0.009, DIR -0.014, Combined -0.003. Within 60-row sampling noise.

**Implication**: the random-label trick was **not** the active ingredient
in attempt 04's DIR-AUROC jump from 0.451 → 0.679. The real ingredients
were the architecture changes (two prompts, DIR drops Replogle, BMDM context,
per-gene descriptions). Random vs real label rendering moves the metric by
0.003 here.

**Recommendation**: use attempt 05 prompts for the full GPT run — same score
within noise, but conceptually cleaner and matches the published method.

**Corrections**: added `## Correction` notices to `attempts/04_vcworld_port/{README,result}.md` flagging the wrong VCWorld attribution. The attempt-04 numbers remain valid; only the causal story is corrected.

See `attempts/05_paper_faithful/result.md`.

---

## 2026-06-08 · attempt 04 (validated on DeepSeek 60-row probe) · VCWorld-style port

Pivoted to two-prompt VCWorld architecture after attempt 03 evaluation
revealed DIR-AUROC = 0.451 (below random) on 60 random train rows. Root cause:
forcing a single prompt to emit both P_DE and P_up_given_DE made the LLM
override Replogle direction with weak mechanism reasoning.

**Result on same 60 train rows (seed=123)**

| Predictor | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| Random | 0.500 | 0.500 | 0.500 |
| Replogle alone (apples-to-apples) | 0.531 | 0.471 | 0.501 |
| **Attempt 03** (one prompt KG+celltype) | 0.654 | **0.451** | 0.552 |
| **Attempt 04** (two prompts, VCWorld port) | 0.601 | **0.679** | **0.640** |
| Reference: attempt 01 whole-train Replogle | 0.541 | 0.663 | 0.602 |
| Reference: top-4 Kaggle LB band | — | — | 0.628 – 0.650 |

**Build artifacts (committed)**
- `pipeline/bmdm_context.py` — rich BMDM cell-state paragraph
- `pipeline/gene_desc.py` + `data/gene_desc.json` — NCBI/MGI summaries, 87% coverage via human-ortholog backfill
- `pipeline/retrieve_examples.py` — KG-similarity retrieval of K=10 train (pert', gene') pairs with randomized labels (vote-bias defense)
- `pipeline/prompt_builder_v2.py` — `build_de_prompt`, `build_dir_prompt`
- `scripts/build_gene_desc.py` + `scripts/extend_gene_desc.py` — one-time desc cache
- `scripts/eval_metric_v2.py` — eval runner (async, configurable concurrency)
- 19 / 19 existing pipeline tests still pass

**Architecture choices that mattered**
- DE and DIR are two independent prompts; DIR omits Replogle scalar
- Retrieval uses STRING + Reactome co-membership (existing KG index from attempt 03)
- Exemplar labels are RANDOMIZED in-prompt — proves question is well-defined
- BMDM context paragraph includes lineage-silent programs (cell cycle, adaptive immunity)
  so the model can reject genes that are biologically inert in BMDM

**Cost so far (DeepSeek probes)**: ~$1.5 total across all evaluation rounds.

**Next**: user runs full 1,813 rows × 2 prompts × 3 seeds on GPT to get a real LB score. See `attempts/04_vcworld_port/result.md`.

---

## 2026-06-04 · attempt 03 (offline build) · KG + cell-type guidance prompts

Built Layer 2 (mouse KG mechanism) + Layer 3 (cross-cell-type transfer guide) and
regenerated 1,813 prompts. LLM inference still pending.

- **Data**: downloaded STRING mouse PPI v12.0, STRING aliases, Reactome
  Ensembl2Reactome (all species, filtered to ENSMUSG), GO mgi.gaf (reserved for
  attempt 04 fallback). Filtered KG index in `data/kg_index/` is ~4 MB, committed.
- **Coverage**: 68% of test rows now have *some* KG signal (PPI path or category
  tag). 33% have a STRING shortest path ≤3 hops between pert and gene.
- **Code**: `pipeline/{kg_retrieval, celltype_guide}.py` + extended
  `prompt_builder.py` with `use_kg=True` switch.
- **Prompts**: median 1,540 tokens (was 1,018), still well under 4,096 budget.
- **Tests**: 19 / 19 passing (added 8 tests in `test_kg.py`).
- **Known gap**: 46% of genes have no Reactome mouse annotation (Atf4, Stat1,
  Aars, Mki67, Lyz1, Eef1a1, Ifit1, …). GO BP fallback is the natural attempt 04
  if attempt 03 doesn't move the score.

**Next**: run GPT-OSS-120B × 3 seeds × 1,813 prompts on LLM server; compare
attempt 03 LB score to attempt 02. Update this entry with the score.

See `attempts/03_kg_celltype/result.md`.

---

## 2026-06-03 · strategy · Four-layer prompt architecture decided

Articulated the current pipeline's limitation: attempt 02's prompts give the LLM a Replogle scalar without mechanism context or cell-type translation guidance. The LLM is being asked to extrapolate K562/RPE1 → BMDM without being taught how.

**Decision**: build each question's prompt as four conceptual layers.

1. Replogle scalar (existing, attempt 02)
2. KG mechanism context — STRING shortest path, Reactome pathway membership, GO overlap
3. Cell-type translation guide — static rules for what transfers across cell types
4. Case-based exemplars — deferred due to user's prior observation that example label distribution dominates LLM decisions (vote bias)

**Implementation = attempt 03**: layers 2 + 3 only. Layer 4 deferred until 02 vs 03 comparison is done.

**Closes the "should we be like VCWorld?" question**: architecturally yes (same offline-KG → retrieval → structured-prompt pattern, same DE/DIR output structure), but specifics differ. We need mouse BMDM context (VCWorld is human + drug), 4k input-token cap (VCWorld has none), and the double-AUROC parameterization is enforced via separate `P_DE` and `P_up_given_DE` integers.

See `plans/plan.md` for the current pending list.

---

## 2026-06-03 · infra · Convention: keep plan / progress / git in sync

Added explicit requirement to `CLAUDE.md`: after any meaningful work, update `progress.md` AND `plans/plan.md` AND commit + push. The two-server workflow needs the remote current.

---

## 2026-06-03 · infra · Repo initialized for two-server workflow

Made the project a git repo so the LLM-server side can pull and run inference.

- `README.md` documents the full workflow (download data → build prior → build prompts → run LLM → assemble submission).
- `scripts/run_inference.py` works with any OpenAI-compatible endpoint (vLLM, TGI). Reads from `LLM_BASE_URL` and `LLM_API_KEY` env vars. Concurrency, resume, and per-seed token tracking built in.
- `scripts/make_submission.py` packages the zip per Track A spec (`submission.csv` + `prompt.txt`).
- `scripts/download_data.py` pulls competition data via Kaggle API token.
- `.gitignore` excludes competition data, large priors, generated prompts, inference outputs, and the internal Fig6 PDF — all reproducible from committed scripts.
- Final aggregation in `pipeline/runner.py` updated to match the Track A spec wording (final `prediction_up` = mean of per-seed `prediction_up_seedXX`, same for down).
- 29 files committed in initial commit `8edb0cf`.

**Next on this server**: add KG retrieval signal for the 670 `none`-tier rows.
**Next on the LLM server**: pull, run `scripts/run_inference.py`, push outputs back.

---

## 2026-06-03 · attempt 02 · Baseline Track A prompt scaffold

Built `pipeline/` infrastructure and generated 1,813 per-question prompts for Track A.

- **Code**: `pipeline/{replogle_prior,prompt_builder,output_parser,runner}.py`
- **Output**: `attempts/02_baseline_prompts/prompts/{test_id}.txt`
- **Prompt budget**: median 1,018 tokens (cap 4,096 by rules).
- **Test coverage**: full 994 (55%) · pert_only 149 (8%) · none 670 (37%).
- **Parser**: round-trip validated (P_DE 22, P_up_given_DE 35 → p_up 0.077, p_down 0.143).

**Next**: (a) run `GPT-OSS-120B × 3 seeds × 1,813 prompts` once GPU is available;
(b) add KG retrieval signal for the 37% `none`-tier rows (BMDM-relevant TFs);
(c) train auxiliary LightGBM DE classifier.

See `attempts/02_baseline_prompts/result.md`.

---

## 2026-06-03 · attempt 01 · Cross-species transfer pilot (Replogle K562 + RPE1)

Tested whether human CRISPRi (Replogle K562/RPE1) gives a useful prior for mouse BMDM CRISPRi.

- **Best variant**: K562 + RPE1 averaged · combined AUROC **0.602** on 4,154 evaluable train rows.
- **Decomposition**: DE-AUROC 0.541 (≈ random) · DIR-AUROC 0.663 (real signal).
- **Reading**: Cell-type-specific `G_c` (universal drift) dominates DE detection across species,
  but the **direction** of effect is moderately conserved. Replogle is a DIR prior, not a DE detector.
- **Variants tried**: K562 alone (0.574), RPE1 alone (0.586), union avg (0.602), intersection (0.609),
  top-50 thresholded (0.533, hurts), top-200 thresholded (0.542, hurts), mygene ortholog vs uppercase
  fallback (≤ 0.001 difference).
- **Conclusion**: ortholog mapping is saturated. DE channel must come from non-Replogle signals
  (KG retrieval, mechanistic reasoning, auxiliary classifier).

See `attempts/01_cross_species_pilot/result.md`.

---

## 2026-06-03 · context · Source dataset search (no attempt artifact)

Searched for the competition's underlying BMDM CRISPRi data so it could be used for direct lookup.

- Competition identified as the inaugural BRChallenge at **MLGenX@ICLR 2026**.
- Organizers include Aviv Regev and Tommaso Biancalani (both Genentech), plus Fabian Theis.
- "CropFlow" pipeline name has no public footprint.
- Surveyed: scPerturb, X-Atlas/Orion, VIPerturb-seq, Hagai 2018, Sankaran macrophage CRISPR.
  None match the 482-pert mouse BMDM CRISPRi profile.

**Conclusion**: source data is almost certainly Genentech-internal. **No direct lookup possible.**
All progress must go through indirect signal (cross-species, KG, LLM mechanistic).

See `discussion/analysis.md` and `discussion/tricks.md`.
