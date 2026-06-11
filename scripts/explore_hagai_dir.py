"""D: Explore Hagai DIR-signal variants on A12 SHIP outputs (no API).

Variants tested:
  D0: baseline (A15 hybrid - just Replogle blend + 0.58 fallback)
  D1: replace constant 0.58 with sigmoid(2 * Hagai.logfc_gene) when Hagai has the gene
  D2: same as D1 but only when Hagai padj < 0.05 AND |logfc| >= 0.585 (significant)
  D3: full-tier blend, but down-weight LLM further when |Hagai.logfc_gene| is large
      (because Hagai-strongly-regulated genes should mostly follow Replogle direction)

All 4 variants use the same A12 SHIP LLM outputs.
"""
import csv, json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.replogle_prior import ReplogPrior
from pipeline.hagai_prior import default as hagai_default
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
    hagai = hagai_default()
    picks = pick_rare_gene(60, 789)
    a12 = {}
    for f in (ROOT / 'attempts/12_cleaner_prompt/outputs/probe60_C_only/single').glob('*.json'):
        d = json.load(open(f))
        a12[d['id']] = {'P_DE': d['parsed']['P_DE'] / 100,
                        'P_up': d['parsed']['P_up_given_DE'] / 100}

    def metric(rows):
        y_de = [1 if r['true'] in ('up', 'down') else 0 for r in rows]
        de = auroc(y_de, [r['P_DE'] for r in rows]) or 0
        dir_rows = [r for r in rows if r['true'] in ('up', 'down')]
        y_dir = [1 if r['true'] == 'up' else 0 for r in dir_rows]
        dr = auroc(y_dir, [r['r'] for r in dir_rows]) or 0
        return de, dr, (de + dr) / 2

    def variant(strategy):
        rows = []
        for r in picks:
            a = a12.get(r['id'])
            if not a:
                continue
            pert, gene = r['pert'], r['gene']
            tier = prior.tier(pert, gene)
            r_llm = a['P_up']
            if tier == 'full':
                lf = prior.get_pair_logfc(pert, gene)
                r_replogle = sigmoid(3 * lf)
                if strategy == 'D3_adaptive_alpha':
                    # Lower alpha (less LLM weight) when Hagai shows the gene is
                    # strongly LPS-regulated — these are inflammation-axis genes
                    # where Replogle direction is the cleanest signal.
                    hg = hagai.get(gene)
                    if hg and abs(hg['logfc']) >= 0.585:
                        alpha = 0.20  # trust Replogle more
                    else:
                        alpha = 0.45  # default
                else:
                    alpha = 0.45
                r_final = alpha * r_llm + (1 - alpha) * r_replogle
            else:
                if strategy == 'D0_baseline':
                    r_final = 0.58
                elif strategy == 'D1_hagai_raw':
                    hg = hagai.get(gene)
                    if hg:
                        r_final = sigmoid(2 * hg['logfc'])
                    else:
                        r_final = 0.58
                elif strategy == 'D2_hagai_sig':
                    hg = hagai.get(gene)
                    if hg and hg['p_adj'] < 0.05 and abs(hg['logfc']) >= 0.585:
                        r_final = sigmoid(2 * hg['logfc'])
                    else:
                        r_final = 0.58
                elif strategy == 'D3_adaptive_alpha':
                    r_final = 0.58
                else:
                    raise ValueError(strategy)
            rows.append({'true': r['label'], 'P_DE': a['P_DE'], 'r': r_final})
        return metric(rows)

    print('=== D variants on A12 SHIP outputs (probe60) ===')
    print(f'{"variant":<28s} {"DE":>6} {"DIR":>6} {"Combined":>10}')
    for tag in ['D0_baseline', 'D1_hagai_raw', 'D2_hagai_sig', 'D3_adaptive_alpha']:
        de, dr, c = variant(tag)
        marker = '  ← current ship' if tag == 'D0_baseline' else ''
        print(f'  {tag:<26s} {de:>6.3f} {dr:>6.3f} {c:>10.3f}{marker}')


if __name__ == '__main__':
    main()
