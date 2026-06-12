"""Build Track-A submission zip for Attempt 04/05 two-prompt outputs."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.output_parser import extract_p_de, extract_p_up_given_de

DATA = ROOT / 'data'


def read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def load_token_sum(path: Path, seeds: tuple[int, ...]) -> int:
    if not path.exists():
        return 0
    d = json.loads(path.read_text())
    return sum(int(d.get(str(seed), 0)) for seed in seeds)


def build_submission(outputs_dir: Path, out_csv: Path, model_name: str, seeds: tuple[int, ...]) -> Path:
    out_rows = []
    with open(DATA / 'test.csv') as fh:
        for row in csv.DictReader(fh):
            rid = row['id']
            by_seed = {}
            for seed in seeds:
                de_raw = read_text(outputs_dir / 'de' / str(seed) / f'{rid}.txt')
                dir_raw = read_text(outputs_dir / 'dir' / str(seed) / f'{rid}.txt')
                p_de, _ = extract_p_de(de_raw)
                p_up_given_de, _ = extract_p_up_given_de(dir_raw)
                p_up = p_de * p_up_given_de
                p_down = p_de * (1.0 - p_up_given_de)
                by_seed[seed] = {
                    'p_up': p_up,
                    'p_down': p_down,
                    'trace': (de_raw or 'none') + '\n\n[DIR]\n' + (dir_raw or 'none'),
                }

            total_tokens = (
                load_token_sum(outputs_dir / 'de' / 'tokens' / f'{rid}.json', seeds)
                + load_token_sum(outputs_dir / 'dir' / 'tokens' / f'{rid}.json', seeds)
            )

            out_rows.append({
                'id': rid,
                'prediction_up': round(sum(by_seed[s]['p_up'] for s in seeds) / len(seeds), 6),
                'prediction_down': round(sum(by_seed[s]['p_down'] for s in seeds) / len(seeds), 6),
                'prediction_up_seed42': round(by_seed[42]['p_up'], 6),
                'prediction_down_seed42': round(by_seed[42]['p_down'], 6),
                'prediction_up_seed43': round(by_seed[43]['p_up'], 6),
                'prediction_down_seed43': round(by_seed[43]['p_down'], 6),
                'prediction_up_seed44': round(by_seed[44]['p_up'], 6),
                'prediction_down_seed44': round(by_seed[44]['p_down'], 6),
                'reasoning_trace_seed42': by_seed[42]['trace'],
                'reasoning_trace_seed43': by_seed[43]['trace'],
                'reasoning_trace_seed44': by_seed[44]['trace'],
                'prompt_tokens': total_tokens,  # Kaggle requires this column name (not `tokens_used`)
                'model_name': model_name,
            })

    with open(out_csv, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    return out_csv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outputs', required=True, help='dir containing de/ and dir/ subdirectories')
    ap.add_argument('--prompt-template', required=True, help='path to the prompt file/description to package as prompt.txt')
    ap.add_argument('--out', required=True, help='output zip path')
    ap.add_argument('--model', default='gpt-oss-120b')
    args = ap.parse_args()

    outputs_dir = Path(args.outputs)
    tmp_dir = outputs_dir.parent / '_submission_staging_v2'
    tmp_dir.mkdir(exist_ok=True)
    csv_path = tmp_dir / 'submission.csv'
    build_submission(outputs_dir, csv_path, args.model, (42, 43, 44))

    template_in = Path(args.prompt_template)
    template_out = tmp_dir / 'prompt.txt'
    if template_in.exists():
        shutil.copy(template_in, template_out)
    else:
        print(f'WARNING: prompt template {template_in} not found; submission will lack prompt.txt')

    out_path = Path(args.out)
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(csv_path, 'submission.csv')
        if template_out.exists():
            zf.write(template_out, 'prompt.txt')
    print(f'wrote {out_path} ({out_path.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
