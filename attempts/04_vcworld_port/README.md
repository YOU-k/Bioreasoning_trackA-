# Attempt 04 — VCWorld-style port

## Hypothesis

Attempt 03 (KG mechanism + cell-type guidance, **one** prompt outputs both `P_DE`
and `P_up_given_DE`) hurt the metric on the rows where Replogle has direct data:

| Predictor (60 random train rows) | DE-AUROC | DIR-AUROC | Combined |
|---|---|---|---|
| DeepSeek + Attempt 03 prompt | 0.654 | **0.451** | 0.552 |
| Replogle |logFC| + sign alone   | 0.531 |  0.471  | 0.501 |
| Attempt 01 (whole train Replogle) | 0.541 | **0.663** | 0.602 |

The 0.295 DIR-AUROC on the **full**-tier subset shows the LLM is *systematically*
overriding Replogle direction with mechanism reasoning that's wrong in BMDM. The
metric punishes that.

VCWorld (ICLR 2026, Wei et al., `/data3/yy/VCWorld/`) solves the same shape of
problem on Tahoe-100M drug perturb with:

1. **Two separate prompts** (DE and DIR) — each focused on one output
2. **Rich per-gene descriptions** (NCBI/UniProt-style function paragraphs)
3. **Rich per-cell-line context** (mutations, lineage, baseline state)
4. **Retrieval evidence**: K=10 structurally similar (pert', gene') pairs from
   train; **labels are randomized** in the prompt to prevent vote bias — the
   pairs prove the question is well-defined, the model reasons from descriptions.
5. **5-step structured reasoning** → final hard answer (Yes/No/Insufficient).

This attempt ports that architecture to mouse BMDM CRISPRi.

## Changes vs Attempt 03

| Module | New | Notes |
|---|---|---|
| `pipeline/bmdm_context.py` | ✓ | Single function returning the rich BMDM cell-state paragraph |
| `pipeline/gene_desc.py` | ✓ | Loads `data/gene_desc.json` (NCBI/MGI summaries via mygene) |
| `pipeline/retrieve_examples.py` | ✓ | VCWorld-style retrieval over train, KG-similarity backbone |
| `pipeline/prompt_builder_v2.py` | ✓ | Two builders: `build_de_prompt`, `build_dir_prompt` |
| `pipeline/runner.py` | Reused | Aggregation unchanged; per-seed P_DE, P_up_given_DE → submission |
| `scripts/build_gene_desc.py` | ✓ | One-time cache of mygene summaries for 2,623 gene symbols |
| `scripts/run_inference_v2.py` | ✓ | Calls DE prompt + DIR prompt per query; parses to (P_DE, P_up) |

## Inputs

- `data/train.csv`, `data/test.csv` (Track A competition files)
- `data/replogle_de.pkl` (kept for DE prompt only)
- `data/kg_index/` (STRING + Reactome filtered for mouse, used to define
  "structurally similar" perts and genes)
- `data/gene_desc.json` (new — fetched once)

## Outputs

- `attempts/04_vcworld_port/prompts/de/{test_id}.txt`
- `attempts/04_vcworld_port/prompts/dir/{test_id}.txt`
- `attempts/04_vcworld_port/outputs/de/{seed}/{test_id}.txt`
- `attempts/04_vcworld_port/outputs/dir/{seed}/{test_id}.txt`
- `attempts/04_vcworld_port/result.md` (final numbers + verdict)

## Validation gate

Before any GPT full run, re-evaluate on the same 60 random train rows
(`seed=123`) used to grade attempt 03.

- **Pass** if Combined > 0.602 (attempt 01 baseline)
- **Fail** if Combined ≤ 0.55 (architecture isn't the bottleneck)
