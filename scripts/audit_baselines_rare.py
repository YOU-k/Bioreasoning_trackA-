"""Compute gene-only / pert-only baselines on the rare-gene probe (seed=789).

Quick adaptation of scripts/audit_baselines.py — same logic but a different
sample, and waits for attempt 07's probe60 outputs (no auto-fail if missing).
"""
from __future__ import annotations
import csv, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.eval_metric_v4 import pick_rare_gene
from scripts.audit_baselines import (
    gene_prior, pert_prior, auroc, spearman, index_train, load_train
)


def main():
    picks = pick_rare_gene(60, 789)
    train = load_train()
    by_gene, by_pert = index_train(train)

    # Try to load attempt 07's probe60 predictions if available
    a7 = {}
    json_dir = ROOT / 'attempts/09_rare_gene_probe/outputs/probe60/single'
    if json_dir.exists():
        for path in json_dir.glob('*.json'):
            d = json.loads(path.read_text())
            a7[d['id']] = {
                'P_DE': d['parsed']['P_DE'] / 100.0,
                'P_up': d['parsed']['P_up_given_DE'] / 100.0,
            }

    rows_gene, rows_pert, rows_a7 = [], [], []
    for r in picks:
        pert, gene, lbl = r['pert'], r['gene'], r['label']
        g_de, g_up, _ = gene_prior(by_gene, pert, gene)
        p_de, p_up, _ = pert_prior(by_pert, pert, gene)
        rows_gene.append({'id': r['id'], 'true': lbl, 'P_DE': g_de, 'P_up': g_up})
        rows_pert.append({'id': r['id'], 'true': lbl, 'P_DE': p_de, 'P_up': p_up})
        if r['id'] in a7:
            rows_a7.append({'id': r['id'], 'true': lbl,
                            'P_DE': a7[r['id']]['P_DE'],
                            'P_up': a7[r['id']]['P_up']})

    def metric(name, rows):
        y_de = [1 if r['true'] in ('up','down') else 0 for r in rows]
        s_de = [r['P_DE'] for r in rows]
        de = auroc(y_de, s_de) or 0.0
        dir_rows = [r for r in rows if r['true'] in ('up','down')]
        y_dir = [1 if r['true']=='up' else 0 for r in dir_rows]
        s_dir = [r['P_up'] for r in dir_rows]
        drc = auroc(y_dir, s_dir) or 0.0
        comb = (de + drc) / 2
        print(f'  {name:<32s}  DE={de:.3f}  DIR={drc:.3f}  Combined={comb:.3f}')
        return {'name': name, 'DE': round(de, 3), 'DIR': round(drc, 3),
                'Combined': round(comb, 3)}

    print('=== Probe60 (rare gene, seed=789) ===')
    print(f'n_rows: {len(picks)}, labels: up={sum(1 for r in picks if r["label"]=="up")} '
          f'down={sum(1 for r in picks if r["label"]=="down")} none={sum(1 for r in picks if r["label"]=="none")}')
    print()
    metrics = []
    metrics.append(metric('Gene-only baseline', rows_gene))
    metrics.append(metric('Pert-only baseline', rows_pert))
    if rows_a7:
        metrics.append(metric(f'Attempt 07 (n={len(rows_a7)})', rows_a7))
    else:
        print(f'  Attempt 07 predictions not found yet ({json_dir})')

    out_path = ROOT / 'attempts/09_rare_gene_probe/audit_baselines.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({'metrics': metrics}, indent=2))
    print(f'\nwrote {out_path}')


if __name__ == '__main__':
    main()
