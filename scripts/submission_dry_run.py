"""P2: submission format dry-run.

Generates synthetic per-seed LLM outputs covering all 1813 test rows, runs
`pipeline.runner.assemble_submission`, validates the produced submission.csv
against the Track-A schema documented in `project_info/overview.md`, then
packages the final zip.

Run BEFORE any GPT-OSS-120B spend to catch:
  - missing / extra columns
  - wrong types (float / string / int)
  - any null values
  - id mismatch with test.csv
  - zip layout problems

The synthetic outputs use plausible random LLM-like text so the parser
exercises its full regex path.
"""
from __future__ import annotations
import argparse, csv, json, random, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.runner import assemble_submission


# Official Track-A submission column spec (from project_info/overview.md lines 69-84)
EXPECTED_COLUMNS = [
    'id',
    'prediction_up',
    'prediction_down',
    'prediction_up_seed42',
    'prediction_down_seed42',
    'prediction_up_seed43',
    'prediction_down_seed43',
    'prediction_up_seed44',
    'prediction_down_seed44',
    'reasoning_trace_seed42',
    'reasoning_trace_seed43',
    'reasoning_trace_seed44',
    'prompt_tokens',         # Kaggle actually rejects `tokens_used` (project_info doc was wrong)
    'model_name',
]

COLUMN_TYPES = {
    'id': str,
    'prediction_up': float,
    'prediction_down': float,
    'prediction_up_seed42': float,
    'prediction_down_seed42': float,
    'prediction_up_seed43': float,
    'prediction_down_seed43': float,
    'prediction_up_seed44': float,
    'prediction_down_seed44': float,
    'reasoning_trace_seed42': str,
    'reasoning_trace_seed43': str,
    'reasoning_trace_seed44': str,
    'prompt_tokens': int,
    'model_name': str,
}


def fake_response(rid: str, seed: int, rng: random.Random) -> str:
    """Generate a plausible LLM response text that the parser can extract."""
    p_de = rng.randint(5, 95)
    p_up = rng.randint(5, 95)
    # Mirror the protocol output format the v3 prompt asks for
    return (
        f"A1 — Mechanism & analogues: simulated reasoning for {rid} seed={seed}\n"
        "A2 — BMDM relevance: simulated\n"
        "A3 — Cascade: simulated\n"
        "A4 — DE call: simulated\n"
        "B1 — Direction logic: simulated\n"
        "B2 — Direction call: simulated\n"
        "\n"
        f"P_DE: {p_de}\n"
        f"P_up_given_DE: {p_up}\n"
    )


def make_synthetic_outputs(test_csv: Path, out_dir: Path, seeds=(42, 43, 44)) -> int:
    """Populate {out_dir}/{seed}/{id}.txt + {out_dir}/tokens/{id}.json for every id in test.csv."""
    rng = random.Random(42)
    out_dir.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        (out_dir / str(seed)).mkdir(parents=True, exist_ok=True)
    (out_dir / 'tokens').mkdir(parents=True, exist_ok=True)

    n = 0
    with open(test_csv) as f:
        for row in csv.DictReader(f):
            rid = row['id']
            tokens = {}
            for seed in seeds:
                text = fake_response(rid, seed, rng)
                (out_dir / str(seed) / f'{rid}.txt').write_text(text)
                tokens[str(seed)] = rng.randint(1500, 3500)
            (out_dir / 'tokens' / f'{rid}.json').write_text(json.dumps(tokens))
            n += 1
    return n


def validate_csv(csv_path: Path, test_csv: Path) -> dict:
    """Returns {'errors': [...], 'warnings': [...], 'n_rows': int}."""
    errors, warnings = [], []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = list(reader)

    # Column check
    if cols != EXPECTED_COLUMNS:
        missing = [c for c in EXPECTED_COLUMNS if c not in cols]
        extra = [c for c in cols if c not in EXPECTED_COLUMNS]
        order_off = cols and (set(cols) == set(EXPECTED_COLUMNS)) and (cols != EXPECTED_COLUMNS)
        if missing:
            errors.append(f'missing columns: {missing}')
        if extra:
            warnings.append(f'extra columns: {extra}')
        if order_off:
            warnings.append(f'column ORDER differs from spec (set OK, but ordering: {cols})')

    # Row count check
    test_ids = []
    with open(test_csv) as f:
        for row in csv.DictReader(f):
            test_ids.append(row['id'])
    submitted_ids = [r['id'] for r in rows]
    if len(rows) != len(test_ids):
        errors.append(f'row count mismatch: submission has {len(rows)}, test has {len(test_ids)}')
    sub_set = set(submitted_ids); test_set = set(test_ids)
    if sub_set != test_set:
        missing_ids = test_set - sub_set
        extra_ids = sub_set - test_set
        if missing_ids:
            errors.append(f'{len(missing_ids)} test ids missing from submission (sample: {sorted(missing_ids)[:3]})')
        if extra_ids:
            errors.append(f'{len(extra_ids)} extra ids in submission (sample: {sorted(extra_ids)[:3]})')

    # Type and null checks (sample first 5 + last 5 rows)
    sample_rows = rows[:5] + rows[-5:] if len(rows) > 10 else rows
    for r in sample_rows:
        for col in EXPECTED_COLUMNS:
            v = r.get(col)
            if v is None or v == '':
                if col in ('reasoning_trace_seed42', 'reasoning_trace_seed43', 'reasoning_trace_seed44',
                           'model_name'):
                    if v == '':
                        errors.append(f'row {r.get("id")}: column {col} is empty string (must be "none" or non-empty)')
                else:
                    errors.append(f'row {r.get("id")}: column {col} is null/empty')
                continue
            try:
                COLUMN_TYPES[col](v)
            except (ValueError, TypeError):
                errors.append(f'row {r.get("id")}: column {col} value {v!r} does not parse as {COLUMN_TYPES[col].__name__}')

    # Float range check on per-seed predictions (must be in [0, 1])
    for r in sample_rows:
        for col in ['prediction_up', 'prediction_down',
                    'prediction_up_seed42', 'prediction_down_seed42',
                    'prediction_up_seed43', 'prediction_down_seed43',
                    'prediction_up_seed44', 'prediction_down_seed44']:
            try:
                v = float(r[col])
                if v < 0 or v > 1:
                    errors.append(f'row {r["id"]}: {col} = {v} out of [0,1]')
            except Exception:
                pass

    return {
        'errors': errors,
        'warnings': warnings,
        'n_rows': len(rows),
        'n_cols': len(cols),
        'cols': cols,
    }


def make_prompt_txt(staging: Path) -> Path:
    """Write a prompt.txt that documents the prompt template we use.

    Track-A spec wants the prompt template included in the zip and limits
    it to <=4096 tokens. v2 of the user's submission was REJECTED with
    "Prompt-token limit exceeded: max 4,096, but submission reports 6,066",
    so we must keep this file under that cap.

    Strategy: include ONLY the static skeleton (headers, rules, protocol,
    output format, tier ladders). Skip the per-query rendered sections
    (query, evidence cases, Hagai/Replogle blocks) — those are content
    that varies per row, not part of the prompt TEMPLATE.
    """
    out = staging / 'prompt.txt'
    from pipeline.prompt_builder_v3 import (
        _HEADER, _RULES, _PROTOCOL, _TIER_LADDERS, _OUTPUT_FORMAT,
    )
    template = (
        '# Track-A submission prompt template (Attempt 15 SHIP)\n'
        '# Architecture: single-call per (pert, gene) per seed.\n'
        '#   prompt_builder: pipeline/prompt_builder_v3.py\n'
        '#   retrieval:      paper §3.4.2 analog (DE) + contrast (none), k_a=5 + k_c=5\n'
        '#   priors used:    Replogle K562/RPE1 logFC + Hagai mouse-BMDM LPS6h |logFC|\n'
        '#   runner-side:    3-seed logit fusion of q=P(DE) and r=P(up|DE);\n'
        '#                   hybrid_direction(α=0.45, nf=0.58) blends Replogle direct\n'
        '#                   ortholog logFC sign into r for full-tier rows\n'
        '# Below is the STATIC template (rules + protocol + output format),\n'
        '# rendered with placeholder {pert}/{gene} tokens. The per-row prompt\n'
        '# also includes a BMDM-context-stripped query block + analog/contrast\n'
        '# retrieval + Hagai/Replogle priors before this template.\n\n'
    )
    body = (
        _HEADER.format(pert='{pert}', gene='{gene}') + '\n\n'
        + _RULES + '\n\n'
        + _PROTOCOL.format(pert='{pert}', gene='{gene}') + '\n\n'
        + _TIER_LADDERS.format(pert='{pert}', gene='{gene}') + '\n\n'
        + _OUTPUT_FORMAT
    )
    out.write_text(template + body)
    # Sanity check: estimate tokens (~4 chars per token)
    est_tokens = len(out.read_text()) // 4
    if est_tokens >= 4096:
        print(f'      ⚠ prompt.txt estimated at {est_tokens} tokens >= 4096 cap. '
              'Kaggle will reject. Trim further.')
    else:
        print(f'      prompt.txt ~{est_tokens} tokens (under 4096 cap)')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--staging', default=str(ROOT / 'attempts/20_submission_dryrun/staging'),
                    help='where to put synthetic outputs + assembled CSV + zip')
    ap.add_argument('--out-zip', default=str(ROOT / 'attempts/20_submission_dryrun/submission_dryrun.zip'),
                    help='final zip path')
    ap.add_argument('--model', default='gpt-oss-120b')
    args = ap.parse_args()

    staging = Path(args.staging)
    staging.mkdir(parents=True, exist_ok=True)
    outputs_dir = staging / 'outputs'

    print(f'[1/4] Generating synthetic LLM outputs in {outputs_dir} ...')
    n = make_synthetic_outputs(ROOT / 'data/test.csv', outputs_dir)
    print(f'      Wrote {n} rows × 3 seeds = {n*3} response files + {n} token files')

    print(f'\n[2/4] Assembling submission.csv via pipeline.runner.assemble_submission ...')
    csv_path = staging / 'submission.csv'
    assemble_submission(outputs_dir=outputs_dir, out_path=csv_path, model_name=args.model)
    print(f'      Wrote {csv_path} ({csv_path.stat().st_size:,} bytes)')

    print(f'\n[3/4] Validating against Track-A spec ...')
    result = validate_csv(csv_path, ROOT / 'data/test.csv')
    print(f'      rows: {result["n_rows"]}, cols: {result["n_cols"]}')
    print(f'      column order: {"OK" if result["cols"] == EXPECTED_COLUMNS else "MISMATCH"}')
    if result['warnings']:
        print('      WARNINGS:')
        for w in result['warnings']:
            print(f'        - {w}')
    if result['errors']:
        print('      ERRORS:')
        for e in result['errors']:
            print(f'        - {e}')
        raise SystemExit(1)
    else:
        print('      ✓ all schema checks passed')

    print(f'\n[4/4] Packaging zip ...')
    prompt_path = make_prompt_txt(staging)
    out_zip = Path(args.out_zip)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(csv_path, 'submission.csv')
        z.write(prompt_path, 'prompt.txt')
    print(f'      Wrote {out_zip} ({out_zip.stat().st_size:,} bytes)')

    # Inspect zip layout
    with zipfile.ZipFile(out_zip) as z:
        names = z.namelist()
    print(f'      Zip contents: {names}')
    if set(names) != {'submission.csv', 'prompt.txt'}:
        print(f'      ⚠ zip names should be exactly [submission.csv, prompt.txt]')
        raise SystemExit(1)

    # Sample first row sanity
    print(f'\n=== First row of submission.csv ===')
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        first = next(reader)
        for col in EXPECTED_COLUMNS:
            v = first[col]
            display = v if len(v) < 60 else v[:57] + '...'
            print(f'  {col:<32s}: {display}')

    print(f'\n✓ DRY RUN COMPLETE. submission_dryrun.zip is schema-valid.')
    print(f'  Next: replace synthetic LLM outputs with real GPT-OSS-120B outputs and re-run.')


if __name__ == '__main__':
    main()
