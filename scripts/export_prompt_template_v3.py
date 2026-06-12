#!/usr/bin/env python3
"""Export the shipped Track-A v3 prompt template for submission packaging.

Track A requires `prompt.txt` in the submission zip. Our prompts are
question-specific, so this exports a representative template with placeholders
and the shipped defaults documented in a single text file.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        '--out',
        default=str(ROOT / 'attempts' / '12_cleaner_prompt' / 'PROMPT_TEMPLATE_v3.txt'),
        help='output path for prompt template text',
    )
    return ap.parse_args()


def main():
    args = parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    text = """Track-A shipped prompt pipeline: prompt_builder_v3 (A12 ship)

Model usage:
- Base model: GPT-OSS-120B
- 3 samples per question with seeds 42, 43, 44
- temperature = 1.0
- top_p = 1.0
- Harmony/chat path for gpt-oss

Prompt builder defaults:
- include_bmdm_context = False
- include_decision_rules = True
- include_reasoning_protocol = True
- enrich_examples = False
- retrieval = DE-task analogue + contrast examples
- extra priors = Hagai mouse BMDM LPS6h + Replogle cross-species prior

Prompt structure:
1. Header defining two outputs:
   P_DE
   P_up_given_DE
2. Query block with perturbed gene and target gene descriptions
3. Retrieved evidence cases from train (analogue + contrast)
4. Hagai prior block
5. Replogle prior block
6. Decision rules
7. Reasoning protocol
8. Tier ladders
9. Strict output format

Question-specific placeholders:
- {pert}: perturbed gene
- {gene}: target/readout gene
- retrieved evidence cases vary per row
- Hagai/Replogle lines vary per row

Submission aggregation:
- parse per-seed P_DE and P_up_given_DE
- fuse q=P(DE) and r=P(up|DE) across seeds by logit averaging
- apply hybrid direction in runner:
  full-tier Replogle rows: r = 0.4 * r_llm + 0.6 * sigmoid(3 * replogle_logfc)
  non-full rows: r = 0.62
"""
    out.write_text(text)
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
