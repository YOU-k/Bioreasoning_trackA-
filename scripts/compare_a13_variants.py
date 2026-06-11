"""Compare A13 ablations against the A12 ship baseline (C-only):
- SHIP (rules + protocol included)
- no Decision rules
- no Reasoning protocol
- neither (rules + protocol both dropped)

Outputs LLM-only and LLM+hybrid Combined for each.
"""
import csv, json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.replogle_prior import ReplogPrior
from scripts.eval_metric_v4 import pick_rare_gene


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def auroc(y, s):
    pos = [s[i] for i in range(len(y)) if y[i] == 1]
    neg = [s[i] for i in range(len(y)) if y[i] == 0]
    if not pos or not neg:
        return None
    h = sum(1 if p > q else 0.5 if p == q else 0 for p in pos for q in neg)
    return h / (len(pos) * len(neg))


def load_outputs(out_dir):
    out = {}
    if not out_dir.exists():
        return out
    for path in out_dir.glob('*.json'):
        d = json.loads(path.read_text())
        out[d['id']] = {
            'P_DE': d['parsed']['P_DE'] / 100.0,
            'P_up': d['parsed']['P_up_given_DE'] / 100.0,
        }
    return out


def evaluate(name, picks, preds, prior, use_hybrid):
    rows = []
    for r in picks:
        a = preds.get(r['id'])
        if not a:
            continue
        if use_hybrid:
            tier = prior.tier(r['pert'], r['gene'])
            if tier == 'full':
                lf = prior.get_pair_logfc(r['pert'], r['gene'])
                r_replogle = sigmoid(3 * lf)
                r_final = 0.4 * a['P_up'] + 0.6 * r_replogle
            else:
                r_final = 0.62
        else:
            r_final = a['P_up']
        rows.append({'true': r['label'], 'P_DE': a['P_DE'], 'r': r_final})

    y_de = [1 if r['true'] in ('up', 'down') else 0 for r in rows]
    de = auroc(y_de, [r['P_DE'] for r in rows]) or 0
    dir_rows = [r for r in rows if r['true'] in ('up', 'down')]
    y_dir = [1 if r['true'] == 'up' else 0 for r in dir_rows]
    dr = auroc(y_dir, [r['r'] for r in dir_rows]) or 0
    print(f'  {name:<36s} n={len(rows):>3}  DE={de:.3f}  DIR={dr:.3f}  '
          f'Combined={(de + dr) / 2:.3f}')


def main():
    prior = ReplogPrior()
    picks = pick_rare_gene(60, 789)
    variants = [
        ('A12 SHIP (C-only)',         ROOT / 'attempts/12_cleaner_prompt/outputs/probe60_C_only/single'),
        ('no Decision rules',         ROOT / 'attempts/13_minimal_prompt/outputs/probe60_no_rules/single'),
        ('no Reasoning protocol',     ROOT / 'attempts/13_minimal_prompt/outputs/probe60_no_proto/single'),
        ('no rules + no protocol',    ROOT / 'attempts/13_minimal_prompt/outputs/probe60_no_both/single'),
    ]

    print('=== Pure LLM (no runner hybrid) ===')
    for name, path in variants:
        preds = load_outputs(path)
        if preds:
            evaluate(name, picks, preds, prior, use_hybrid=False)
        else:
            print(f'  {name:<36s} (no outputs yet)')
    print()
    print('=== LLM + hybrid runner ===')
    for name, path in variants:
        preds = load_outputs(path)
        if preds:
            evaluate(name, picks, preds, prior, use_hybrid=True)
        else:
            print(f'  {name:<36s} (no outputs yet)')


if __name__ == '__main__':
    main()
