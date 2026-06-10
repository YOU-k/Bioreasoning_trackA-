"""Blend the LLM's P_up_given_DE with a Replogle-direct-sign signal for the
subset of rows where Replogle has a full ortholog match for (pert, gene).

Sweep blend weight alpha and report the best Combined on probe60_rare_gene.

Uses existing attempt-11 LLM outputs (no API spend).

  r_blend = alpha * r_LLM + (1 - alpha) * r_Replogle    (if Replogle full)
          = r_LLM                                         (if not)
"""
from __future__ import annotations
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


def main():
    prior = ReplogPrior()
    picks = pick_rare_gene(60, 789)

    # Load A11 LLM outputs
    a11 = {}
    json_dir = ROOT / 'attempts/11_hagai_in_prompt/outputs/probe60/single'
    for path in json_dir.glob('*.json'):
        d = json.loads(path.read_text())
        a11[d['id']] = {
            'P_DE': d['parsed']['P_DE'] / 100.0,
            'P_up': d['parsed']['P_up_given_DE'] / 100.0,
        }

    # For each row compute Replogle direct sign-based P_up (if full tier).
    # Otherwise mark as None (no blend possible).
    rows = []
    n_replogle_full = 0
    for r in picks:
        pert, gene, true = r['pert'], r['gene'], r['label']
        rid = r['id']
        a = a11.get(rid)
        if not a:
            continue
        tier = prior.tier(pert, gene)
        r_replogle = None
        if tier == 'full':
            lf = prior.get_pair_logfc(pert, gene)
            r_replogle = sigmoid(3 * lf)
            n_replogle_full += 1
        rows.append({
            'id': rid, 'true': true,
            'P_DE': a['P_DE'],
            'r_LLM': a['P_up'],
            'r_replogle': r_replogle,
        })

    print(f'{len(rows)} rows; {n_replogle_full} have Replogle full-tier direction signal')
    print()

    # No blend (alpha=1, pure LLM)
    def metric(rows_in, label):
        y_de = [1 if r['true'] in ('up', 'down') else 0 for r in rows_in]
        s_de = [r['P_DE'] for r in rows_in]
        de = auroc(y_de, s_de) or 0.0
        dir_rows = [r for r in rows_in if r['true'] in ('up', 'down')]
        y_dir = [1 if r['true'] == 'up' else 0 for r in dir_rows]
        s_dir = [r['r_final'] for r in dir_rows]
        dr = auroc(y_dir, s_dir) or 0.0
        print(f'  {label:<32s}  DE={de:.3f}  DIR={dr:.3f}  Combined={(de+dr)/2:.3f}')
        return (de + dr) / 2

    # Pure LLM (alpha = 1)
    for r in rows:
        r['r_final'] = r['r_LLM']
    print('=== Reference: pure LLM (no blend) ===')
    metric(rows, 'alpha=1.0 (A11 baseline)')
    print()

    # Sweep alpha
    print('=== Blend sweep: alpha = LLM weight, (1-alpha) = Replogle weight ===')
    best_alpha = None
    best_combined = -1
    for alpha in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        for r in rows:
            if r['r_replogle'] is not None:
                r['r_final'] = alpha * r['r_LLM'] + (1 - alpha) * r['r_replogle']
            else:
                r['r_final'] = r['r_LLM']
        comb = metric(rows, f'alpha={alpha:.2f}')
        if comb > best_combined:
            best_combined = comb
            best_alpha = alpha
    print()
    print(f'BEST alpha = {best_alpha:.2f}  →  Combined = {best_combined:.3f}')

    # Detailed at the best alpha
    print()
    print('=== At best alpha, broken down by Replogle availability ===')
    for r in rows:
        if r['r_replogle'] is not None:
            r['r_final'] = best_alpha * r['r_LLM'] + (1 - best_alpha) * r['r_replogle']
        else:
            r['r_final'] = r['r_LLM']
    full = [r for r in rows if r['r_replogle'] is not None]
    notfull = [r for r in rows if r['r_replogle'] is None]
    metric(full, f'Full-tier rows ({len(full)})')
    metric(notfull, f'Not-full rows ({len(notfull)}, LLM only)')


if __name__ == '__main__':
    main()
