# Progress log

Append-only. One block per completed attempt. Newest at the top.

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
