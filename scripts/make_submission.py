"""Read per-seed LLM outputs and produce submission.csv + prompt.txt + zip.

Usage:
  python scripts/make_submission.py \
      --outputs attempts/02_baseline_prompts/outputs \
      --prompt-template attempts/02_baseline_prompts/PROMPT_TEMPLATE.txt \
      --out attempts/02_baseline_prompts/submission.zip \
      --model gpt-oss-120b
"""
from __future__ import annotations
import argparse, zipfile, shutil
from pathlib import Path
from pipeline.runner import assemble_submission


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outputs', required=True, help='dir with {seed}/{id}.txt and tokens/{id}.json')
    ap.add_argument('--prompt-template', required=True, help='path to the prompt template used (goes into zip)')
    ap.add_argument('--out', required=True, help='output zip path')
    ap.add_argument('--model', default='gpt-oss-120b')
    args = ap.parse_args()

    outputs_dir = Path(args.outputs)
    tmp_dir = outputs_dir.parent / '_submission_staging'
    tmp_dir.mkdir(exist_ok=True)
    csv_path = tmp_dir / 'submission.csv'

    assemble_submission(outputs_dir=outputs_dir, out_path=csv_path, model_name=args.model)

    # Copy prompt template into the zip
    template_in = Path(args.prompt_template)
    if not template_in.exists():
        print(f'WARNING: prompt template {template_in} not found; submission will lack prompt.txt')
    template_out = tmp_dir / 'prompt.txt'
    if template_in.exists():
        shutil.copy(template_in, template_out)

    out_path = Path(args.out)
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(csv_path, 'submission.csv')
        if template_out.exists():
            z.write(template_out, 'prompt.txt')
    print(f'wrote {out_path} ({out_path.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
