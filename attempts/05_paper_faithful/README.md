# Attempt 05 — Paper-faithful VCWorld port

## Hypothesis

Attempt 04 ported VCWorld's overall architecture but used a non-faithful
retrieval scheme. We retrieved K=10 KG-similar train pairs flat and then
**randomized** their `Result:` labels in-prompt — a pattern we found in
`/data3/yy/VCWorld/src/cli_pipeline/stages/prompt.py:61`
(`answer = random.choice(choices)`).

Reading the actual paper (Wei et al., ICLR 2026, `discussion/vcworld_paper.txt`)
shows that codepath does **not** match the published design:

§3.4.2 defines retrieval as the union of two disjoint, label-conditioned
subsets, each ranked by similarity:

> Analogue Cases (S_analog): The top-k_a instances from the subset of D
> with a positive outcome (i.e., label l=1) …
> Contrast Cases (S_contrast): The top-k_c instances from the subset of D
> with a negative outcome (i.e., label l=0) …

Appendix D shows a real prompt for Tofacitinib / FTH1 / Hs766T with **real
labels** (6 examples DE=yes, 4 examples DE=no). No randomization.

The structural mix of positive + negative cases is what defeats vote bias —
not randomization. We lost the empirical label signal in attempt 04 for no
gain. Attempt 05 fixes that.

## Changes vs Attempt 04

| Module | Change |
|---|---|
| `pipeline/retrieve_examples.py` | Added `retrieve_analog_contrast(pert, gene, task, k_a, k_c, exclude_query, seed)` per paper §3.4.2 |
| `pipeline/retrieve_examples.py` | Added `format_block_analog_contrast(analog, contrast, task)` rendering combined+shuffled list with real labels |
| `pipeline/retrieve_examples.py` | Removed `format_block_random_labels` (now unused) |
| `pipeline/prompt_builder_v2.py` | `build_de_prompt` + `build_dir_prompt` both switched to analog+contrast retrieval; default k_a=5, k_c=5 (preserves total budget of 10 examples) |
| `pipeline/prompt_builder_v2.py` | Prompt language updated: "RANDOMIZED labels" → "analogue + contrast cases with real labels, mix is by construction" |
| `pipeline/tests/test_retrieve_analog_contrast.py` | New (5 tests): pool separation by label, query exclusion, budget respect, real-label rendering |

## Task-conditioned retrieval

| Task | Analogue pool (l=1) | Contrast pool (l=0) | Excluded |
|---|---|---|---|
| DE  | label ∈ {up, down}  | label = none        | —      |
| DIR | label = up          | label = down        | label = none (DIR is conditional on DE) |

## Inputs (reproducibility)

Same as attempt 04:
- `data/train.csv`, `data/test.csv`
- `data/replogle_de.pkl`
- `data/mouse_to_human_ortholog.json`
- `data/kg_index/`
- `data/gene_desc.json`

## Outputs

- `attempts/05_paper_faithful/outputs/eval60/de/{id}.json`
- `attempts/05_paper_faithful/outputs/eval60/dir/{id}.json`
- `attempts/05_paper_faithful/result.md`

## Validation gate

On the same 60 random train rows (seed=123) used to grade attempts 03 / 04:

| Outcome | Verdict |
|---|---|
| Combined > 0.640 | **Pass** — paper design > random-label hack; ship this as the full-run prompt |
| Combined ∈ [0.60, 0.64] | Tie. Random-label was not the active ingredient in attempt 04's gain. Pick whichever is simpler. |
| Combined < 0.60 | **Fail** — paper design is worse here than the random hack. Investigate why (label leakage? pool imbalance? prompt wording?). |
