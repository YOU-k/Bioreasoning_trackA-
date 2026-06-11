"""A: logit-space blend.   B: per-row adaptive α based on Replogle |logFC|.

Both run on A12 SHIP probe60 outputs (no API). Variants explored:

  baseline:   r = 0.45 * r_LLM + 0.55 * sigmoid(3 * lf)             [linear]

  A_logit:    r = sigmoid(0.45 * logit(r_LLM) + 0.55 * logit(sigmoid(3*lf)))

  B_adapt:    α(|lf|) = small when |lf| large, large when |lf| small
              Several functional forms tried.

  A+B:        logit-space blend with adaptive α

  Reference distribution: train P(up|DE) = 0.685 (up:down = 2.2:1).
  Current nf_default = 0.58 — under the prior, empirically best in A15.
"""
import json, math, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.replogle_prior import ReplogPrior
from scripts.eval_metric_v4 import pick_rare_gene


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def logit(p, eps=1e-6):
    p = max(eps, min(1 - eps, p))
    return math.log(p / (1 - p))


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
    for f in (ROOT / 'attempts/12_cleaner_prompt/outputs/probe60_C_only/single').glob('*.json'):
        d = json.load(open(f))
        a12[d['id']] = {'P_DE': d['parsed']['P_DE'] / 100,
                        'P_up': d['parsed']['P_up_given_DE'] / 100}

    def evaluate(strategy_fn, name):
        rows = []
        for r in picks:
            a = a12.get(r['id'])
            if not a:
                continue
            r_h = strategy_fn(r['pert'], r['gene'], a)
            rows.append({'true': r['label'], 'P_DE': a['P_DE'], 'r': r_h})
        y_de = [1 if r['true'] in ('up', 'down') else 0 for r in rows]
        de = auroc(y_de, [r['P_DE'] for r in rows]) or 0
        dir_rows = [r for r in rows if r['true'] in ('up', 'down')]
        y_dir = [1 if r['true'] == 'up' else 0 for r in dir_rows]
        dr = auroc(y_dir, [r['r'] for r in dir_rows]) or 0
        print(f'  {name:<40s}  DE={de:.3f}  DIR={dr:.3f}  Combined={(de+dr)/2:.3f}')
        return (de + dr) / 2

    # Baseline (current A15 ship)
    def baseline(pert, gene, a):
        tier = prior.tier(pert, gene)
        if tier == 'full':
            lf = prior.get_pair_logfc(pert, gene)
            r_rep = sigmoid(3 * lf)
            return 0.45 * a['P_up'] + 0.55 * r_rep
        return 0.58

    print('=== Baseline ===')
    evaluate(baseline, 'A15 SHIP (linear blend, α=0.45, nf=0.58)')

    print()
    print('=== A: Logit-space blend ===')

    def A_logit_a(pert, gene, a, alpha=0.45, nf=0.58):
        tier = prior.tier(pert, gene)
        if tier == 'full':
            lf = prior.get_pair_logfc(pert, gene)
            r_rep = sigmoid(3 * lf)
            return sigmoid(alpha * logit(a['P_up']) + (1 - alpha) * logit(r_rep))
        return nf

    for alpha in [0.3, 0.4, 0.45, 0.5, 0.6, 0.7]:
        evaluate(lambda p, g, a, _a=alpha: A_logit_a(p, g, a, alpha=_a),
                 f'A_logit α={alpha:.2f} nf=0.58')

    # nf for logit blend
    print()
    print('=== A_logit at best α, sweep nf ===')
    for nf in [0.50, 0.55, 0.58, 0.60, 0.62, 0.65, 0.685, 0.70]:
        evaluate(lambda p, g, a, _nf=nf: A_logit_a(p, g, a, alpha=0.45, nf=_nf),
                 f'A_logit α=0.45 nf={nf:.3f}')

    print()
    print('=== B: Per-row adaptive α (based on |Replogle logFC|) ===')

    def B_adapt(pert, gene, a, alpha_low=0.20, alpha_high=0.65,
                threshold=0.5, nf=0.58):
        """α_low when |lf| ≥ threshold (trust Replogle more)
           α_high when |lf| < threshold (let LLM weigh in more)."""
        tier = prior.tier(pert, gene)
        if tier == 'full':
            lf = prior.get_pair_logfc(pert, gene)
            r_rep = sigmoid(3 * lf)
            alpha = alpha_low if abs(lf) >= threshold else alpha_high
            return alpha * a['P_up'] + (1 - alpha) * r_rep
        return nf

    for thr in [0.3, 0.5, 0.7, 1.0]:
        for al, ah in [(0.20, 0.65), (0.30, 0.60), (0.25, 0.55)]:
            evaluate(lambda p, g, a, _thr=thr, _al=al, _ah=ah: B_adapt(p, g, a,
                                                                       alpha_low=_al,
                                                                       alpha_high=_ah,
                                                                       threshold=_thr),
                     f'B_adapt α[{al},{ah}] |lf|>{thr}')

    print()
    print('=== B: smooth adaptive (sigmoid of |lf|) ===')

    def B_smooth(pert, gene, a, alpha_max=0.7, beta=0.5, nf=0.58):
        """α(|lf|) = α_max * sigmoid(-2*(|lf| - β))
           Smaller α when |lf| big → more Replogle weight."""
        tier = prior.tier(pert, gene)
        if tier == 'full':
            lf = prior.get_pair_logfc(pert, gene)
            r_rep = sigmoid(3 * lf)
            alpha = alpha_max * sigmoid(-2 * (abs(lf) - beta))
            return alpha * a['P_up'] + (1 - alpha) * r_rep
        return nf

    for am in [0.6, 0.7, 0.8]:
        for b in [0.2, 0.4, 0.6]:
            evaluate(lambda p, g, a, _am=am, _b=b: B_smooth(p, g, a,
                                                            alpha_max=_am,
                                                            beta=_b),
                     f'B_smooth α_max={am:.1f} β={b:.1f}')

    print()
    print('=== A + B: logit-space blend + adaptive α ===')

    def AB(pert, gene, a, alpha_low=0.20, alpha_high=0.65,
           threshold=0.5, nf=0.58):
        tier = prior.tier(pert, gene)
        if tier == 'full':
            lf = prior.get_pair_logfc(pert, gene)
            r_rep = sigmoid(3 * lf)
            alpha = alpha_low if abs(lf) >= threshold else alpha_high
            return sigmoid(alpha * logit(a['P_up']) + (1 - alpha) * logit(r_rep))
        return nf

    for thr in [0.3, 0.5, 0.7]:
        for al, ah in [(0.20, 0.65), (0.25, 0.55), (0.30, 0.60)]:
            label = f'AB α[{al},{ah}] |lf|>{thr}'
            evaluate(lambda p, g, a, _thr=thr, _al=al, _ah=ah: AB(p, g, a,
                                                                  alpha_low=_al,
                                                                  alpha_high=_ah,
                                                                  threshold=_thr),
                     label)


if __name__ == '__main__':
    main()
