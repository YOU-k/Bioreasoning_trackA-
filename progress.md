# Progress log

Append-only. One block per completed attempt. Newest at the top.

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
