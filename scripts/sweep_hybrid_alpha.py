"""Fine-grained sweep of hybrid_direction alpha on the A12 SHIP probe60 outputs.

α=0.4 was the result of a coarse {0.0, 0.1, ..., 1.0} sweep on A11 outputs.
With the better A12 SHIP outputs (Combined 0.625 hybrid), retune.

We also test the prior fallback constant for non-full-tier rows — current
is 0.62 (train up:down ≈ 2.2:1) but the LLM-only DIR on those rows might
be informative enough to use a different default.
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


def main():
    prior = ReplogPrior()
    picks = pick_rare_gene(60, 789)
    a12 = {}
    for path in (ROOT / 'attempts/12_cleaner_prompt/outputs/probe60_C_only/single').glob('*.json'):
        d = json.loads(path.read_text())
        a12[d['id']] = {'P_DE': d['parsed']['P_DE'] / 100,
                        'P_up': d['parsed']['P_up_given_DE'] / 100}

    def hybrid(alpha, nf_prior):
        rows = []
        for r in picks:
            a = a12.get(r['id'])
            if not a:
                continue
            tier = prior.tier(r['pert'], r['gene'])
            if tier == 'full':
                lf = prior.get_pair_logfc(r['pert'], r['gene'])
                r_replogle = sigmoid(3 * lf)
                r_final = alpha * a['P_up'] + (1 - alpha) * r_replogle
            else:
                r_final = nf_prior
            rows.append({'true': r['label'], 'P_DE': a['P_DE'], 'r': r_final})
        y_de = [1 if r['true'] in ('up', 'down') else 0 for r in rows]
        de = auroc(y_de, [r['P_DE'] for r in rows]) or 0
        dir_rows = [r for r in rows if r['true'] in ('up', 'down')]
        y_dir = [1 if r['true'] == 'up' else 0 for r in dir_rows]
        dr = auroc(y_dir, [r['r'] for r in dir_rows]) or 0
        return de, dr, (de + dr) / 2

    print('=== Fine α sweep (non-full prior = 0.62, current default) ===')
    best = (-1, None, None)
    for alpha in [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5,
                  0.55, 0.6, 0.7, 0.8, 1.0]:
        de, dr, c = hybrid(alpha, 0.62)
        marker = '  ← current' if abs(alpha - 0.4) < 1e-6 else ''
        print(f'  alpha={alpha:>4.2f}  DE={de:.3f}  DIR={dr:.3f}  Combined={c:.3f}{marker}')
        if c > best[0]:
            best = (c, alpha, 0.62)

    print()
    print('=== Non-full prior constant sweep (at best α) ===')
    best_alpha = best[1]
    for nf in [0.50, 0.55, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70]:
        de, dr, c = hybrid(best_alpha, nf)
        marker = '  ← current' if abs(nf - 0.62) < 1e-6 else ''
        print(f'  alpha={best_alpha:.2f}, nf_prior={nf:.2f}  DE={de:.3f}  DIR={dr:.3f}  Combined={c:.3f}{marker}')
        if c > best[0]:
            best = (c, best_alpha, nf)

    print()
    print('=== 2D joint sweep around the maximum ===')
    for alpha in [max(0.0, best[1] - 0.1), best[1], min(1.0, best[1] + 0.1)]:
        for nf in [best[2] - 0.04, best[2], best[2] + 0.04]:
            de, dr, c = hybrid(alpha, nf)
            print(f'  α={alpha:.2f} nf={nf:.2f}: DE={de:.3f} DIR={dr:.3f} C={c:.3f}')

    print()
    print(f'BEST: alpha={best[1]:.2f}, nf_prior={best[2]:.2f}  →  Combined={best[0]:.3f}')
    print(f'(vs current ship alpha=0.40, nf_prior=0.62  →  Combined=0.625)')


if __name__ == '__main__':
    main()
