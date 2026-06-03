# Attempt 02 — Result

## Output
- **1,813 prompts** generated in `prompts/{test_id}.txt`.
- Token estimates: **min 861, median 1,018, max 1,031** (budget 4,096).
- Plenty of headroom for further additions (KG retrieval, exemplars).

## Tier distribution on test
| Tier | Rows | % | Meaning |
|---|---:|---:|---|
| `full` | 994 | 55% | Both pert and target gene have Replogle data → full DIR prior available |
| `pert_only` | 149 | 8% | Pert in Replogle, target gene is mouse-specific (e.g., Riken) → top-responder context only |
| `none` | 670 | 37% | Pert is BMDM-relevant TF/signaling (Cebpb, Stat1, Nfkb1, Irf-family, Plcg2, …), not in K562/RPE1 essential → no Replogle signal |

## Sanity checks passed
- Sample prompt for `Aars → Acaa2` (a rescued uppercase case) correctly shows
  the AARS KD ISR signature (Trib3, Ddit4, Atf4 targets up; translation
  machinery down) and the specific logFC for ACAA2 (= −0.092, borderline).
- Round-trip parser test: a model output of `P_DE: 22 / P_up_given_DE: 35`
  → `p_up = 0.077, p_down = 0.143` (down-leaning, consistent with the prompt's
  hint).
- Parser fallback test: a malformed output gracefully returns `p_up = p_down = 0.225`
  (AUROC contribution ≈ 0.5, no harm).

## Verdict
The scaffold is functional. The main expected limitations are:
1. The 37% `none`-tier rows have no quantitative signal — model must reason
   from gene-name knowledge alone, which is exactly where the
   "any function = useful" bias hurts most.
2. DE-AUROC is the bottleneck. Replogle gives DIR ~0.66 (good) but DE ≈ 0.54
   (useless). The prompt's disconfirming step is the only DE-side calibration
   wedge currently in place.

## Next actions (carried forward to next attempt)
1. Run `GPT-OSS-120B × 3 seeds × 1,813 prompts` to get a real baseline score.
2. Add KG retrieval (STRING/Reactome pathway distance) into the prompt body
   to improve `none`-tier rows.
3. Train a small DE classifier on Replogle vec + pathway features as a
   non-LLM DE prior, surface its prediction in the prompt.
4. Pull the actual `sample_submission_track_a.csv` from the logged-in Kaggle
   Data tab to lock down column types before the first real submission.
