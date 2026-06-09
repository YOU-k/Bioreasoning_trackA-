"""Audit: are attempt-07's gains real perturbation-specific reasoning,
or gene-prior / pert-prior voting in disguise?

Per discussion/next_paradigm_gpt.md §7, this is the #1 audit to run before
any GPT-OSS-120B spend. Compares attempt 07 to three baselines on the same
60-row probe (seed=123) and reports a clear verdict.
"""
from __future__ import annotations
import csv, json, sys, random
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pick_random(n: int, seed: int):
    rng = random.Random(seed)
    rows = list(csv.DictReader(open(ROOT / 'data/train.csv')))
    rng.shuffle(rows)
    return rows[:n]


def load_train():
    return list(csv.DictReader(open(ROOT / 'data/train.csv')))


def index_train(train):
    """Returns (by_gene, by_pert) -> list of (pert, gene, label) tuples."""
    by_gene = defaultdict(list)
    by_pert = defaultdict(list)
    for r in train:
        t = (r['pert'], r['gene'], r['label'])
        by_gene[r['gene']].append(t)
        by_pert[r['pert']].append(t)
    return by_gene, by_pert


def gene_prior(by_gene, pert, gene, exclude_pert=True):
    """For (pert, gene), look at all train rows containing this gene but
    NOT this pert. Return (P_DE_gene, P_up_given_DE_gene, n_neighbors).

    Mimics exclude_query=True semantics: a train row sharing pert is leakage.
    """
    rows = [t for t in by_gene.get(gene, [])
            if (not exclude_pert or t[0] != pert)]
    if not rows:
        return 0.5, 0.5, 0  # uninformative prior
    n_total = len(rows)
    n_de = sum(1 for _, _, l in rows if l in ('up', 'down'))
    p_de = n_de / n_total
    n_up = sum(1 for _, _, l in rows if l == 'up')
    n_dn = sum(1 for _, _, l in rows if l == 'down')
    p_up = (n_up / (n_up + n_dn)) if (n_up + n_dn) > 0 else 0.5
    return p_de, p_up, n_total


def pert_prior(by_pert, pert, gene, exclude_gene=True):
    """Symmetric to gene_prior."""
    rows = [t for t in by_pert.get(pert, [])
            if (not exclude_gene or t[1] != gene)]
    if not rows:
        return 0.5, 0.5, 0
    n_total = len(rows)
    n_de = sum(1 for _, _, l in rows if l in ('up', 'down'))
    p_de = n_de / n_total
    n_up = sum(1 for _, _, l in rows if l == 'up')
    n_dn = sum(1 for _, _, l in rows if l == 'down')
    p_up = (n_up / (n_up + n_dn)) if (n_up + n_dn) > 0 else 0.5
    return p_de, p_up, n_total


def auroc(y, s):
    pos = [s[i] for i in range(len(y)) if y[i] == 1]
    neg = [s[i] for i in range(len(y)) if y[i] == 0]
    if not pos or not neg:
        return None
    h = 0.0
    for p in pos:
        for q in neg:
            if p > q:
                h += 1
            elif p == q:
                h += 0.5
    return h / (len(pos) * len(neg))


def spearman(x: list[float], y: list[float]) -> float:
    """Quick Spearman without numpy. Returns rho in [-1, 1]."""
    n = len(x)
    if n < 2:
        return 0.0
    def rank(vals):
        ordered = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[ordered[j + 1]] == vals[ordered[i]]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[ordered[k]] = avg_rank
            i = j + 1
        return r
    rx = rank(x); ry = rank(y)
    mx = sum(rx) / n; my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def load_attempt07_preds() -> dict:
    """Load attempt-07 per-row P_DE and P_up_given_DE from JSONs."""
    out = {}
    json_dir = ROOT / 'attempts/07_no_anchors/outputs/eval60/single'
    for path in json_dir.glob('*.json'):
        d = json.loads(path.read_text())
        out[d['id']] = {
            'P_DE': d['parsed']['P_DE'] / 100.0,
            'P_up': d['parsed']['P_up_given_DE'] / 100.0,
        }
    return out


def report_metrics(name: str, rows: list[dict]) -> dict:
    """Compute DE-AUROC, DIR-AUROC, Combined on a list of {true, P_DE, P_up}."""
    y_de = [1 if r['true'] in ('up', 'down') else 0 for r in rows]
    s_de = [r['P_DE'] for r in rows]
    de = auroc(y_de, s_de) or 0.0

    dir_rows = [r for r in rows if r['true'] in ('up', 'down')]
    y_dir = [1 if r['true'] == 'up' else 0 for r in dir_rows]
    s_dir = [r['P_up'] for r in dir_rows]
    drc = auroc(y_dir, s_dir) or 0.0
    comb = (de + drc) / 2
    print(f'  {name:<30s}  DE={de:.3f}  DIR={drc:.3f}  Combined={comb:.3f}')
    return {'name': name, 'DE': round(de, 3), 'DIR': round(drc, 3),
            'Combined': round(comb, 3)}


def main():
    picks = pick_random(60, seed=123)
    train = load_train()
    by_gene, by_pert = index_train(train)
    attempt07 = load_attempt07_preds()

    # Build per-row predictions for all baselines
    rows_gene = []
    rows_pert = []
    rows_hybrid = []
    rows_attempt07 = []
    rows_random = []

    n_gene_no_neighbor = 0
    n_pert_no_neighbor = 0
    n_attempt07_missing = 0

    for row in picks:
        pert, gene, true = row['pert'], row['gene'], row['label']
        rid = row['id']

        # Gene-only
        g_de, g_up, n_g = gene_prior(by_gene, pert, gene)
        if n_g == 0:
            n_gene_no_neighbor += 1
        # Pert-only
        p_de, p_up, n_p = pert_prior(by_pert, pert, gene)
        if n_p == 0:
            n_pert_no_neighbor += 1
        # Hybrid
        h_de = (g_de + p_de) / 2
        h_up = (g_up + p_up) / 2
        # Random (per-row jitter to break ties for AUROC sanity)
        rnd = random.Random(hash(rid) & 0xffffffff)

        rows_gene.append({'id': rid, 'true': true, 'P_DE': g_de, 'P_up': g_up})
        rows_pert.append({'id': rid, 'true': true, 'P_DE': p_de, 'P_up': p_up})
        rows_hybrid.append({'id': rid, 'true': true, 'P_DE': h_de, 'P_up': h_up})
        rows_random.append({'id': rid, 'true': true, 'P_DE': rnd.random(),
                            'P_up': rnd.random()})
        if rid in attempt07:
            rows_attempt07.append({'id': rid, 'true': true,
                                   'P_DE': attempt07[rid]['P_DE'],
                                   'P_up': attempt07[rid]['P_up']})
        else:
            n_attempt07_missing += 1

    print('=== Sample composition ===')
    print(f'  60 random train rows (seed=123)')
    print(f'  rows with no gene-neighbor in train (after exclude_pert): {n_gene_no_neighbor}')
    print(f'  rows with no pert-neighbor in train (after exclude_gene): {n_pert_no_neighbor}')
    print(f'  attempt 07 predictions found: {len(rows_attempt07)}/60 (missing: {n_attempt07_missing})')
    print()
    print('=== Metrics ===')
    metrics = []
    metrics.append(report_metrics('Random', rows_random))
    metrics.append(report_metrics('Gene-only baseline', rows_gene))
    metrics.append(report_metrics('Pert-only baseline', rows_pert))
    metrics.append(report_metrics('Gene+Pert hybrid', rows_hybrid))
    metrics.append(report_metrics('Attempt 07 (single-call LLM)', rows_attempt07))
    print()

    # Correlation: attempt 07 P_DE vs gene-only P_DE
    print('=== Diagnostics ===')
    a7_ids = {r['id'] for r in rows_attempt07}
    aligned_a7 = [r for r in rows_attempt07]
    aligned_g  = [r for r in rows_gene  if r['id'] in a7_ids]
    aligned_p  = [r for r in rows_pert  if r['id'] in a7_ids]
    # sort all by id to ensure alignment
    aligned_a7.sort(key=lambda r: r['id'])
    aligned_g.sort(key=lambda r: r['id'])
    aligned_p.sort(key=lambda r: r['id'])

    rho_de_g = spearman([r['P_DE'] for r in aligned_a7], [r['P_DE'] for r in aligned_g])
    rho_de_p = spearman([r['P_DE'] for r in aligned_a7], [r['P_DE'] for r in aligned_p])
    rho_up_g = spearman([r['P_up'] for r in aligned_a7], [r['P_up'] for r in aligned_g])
    rho_up_p = spearman([r['P_up'] for r in aligned_a7], [r['P_up'] for r in aligned_p])
    print(f'  Spearman(attempt07 P_DE, gene-only P_DE) = {rho_de_g:+.3f}')
    print(f'  Spearman(attempt07 P_DE, pert-only P_DE) = {rho_de_p:+.3f}')
    print(f'  Spearman(attempt07 P_up, gene-only P_up) = {rho_up_g:+.3f}')
    print(f'  Spearman(attempt07 P_up, pert-only P_up) = {rho_up_p:+.3f}')
    print()
    print('  (High correlation = LLM is largely reading the prior;')
    print('   low correlation = LLM is doing independent reasoning.)')
    print()

    # Disagreement audit: rows where attempt 07 says DE but gene-only says not, or vice versa
    print('=== Disagreement audit (DE call, threshold = 0.5) ===')
    n_agree = n_disagree = 0
    a7_right_when_disagree = 0
    g_right_when_disagree = 0
    for a, g in zip(aligned_a7, aligned_g):
        true_de = 1 if a['true'] in ('up', 'down') else 0
        a7_call = 1 if a['P_DE'] >= 0.5 else 0
        g_call  = 1 if g['P_DE'] >= 0.5 else 0
        if a7_call == g_call:
            n_agree += 1
        else:
            n_disagree += 1
            if a7_call == true_de:
                a7_right_when_disagree += 1
            else:
                g_right_when_disagree += 1
    print(f'  Agree:    {n_agree}/{len(aligned_a7)}')
    print(f'  Disagree: {n_disagree}/{len(aligned_a7)}')
    print(f'    of which attempt 07 right: {a7_right_when_disagree}')
    print(f'    of which gene-only right:  {g_right_when_disagree}')
    print()

    # Save the raw data
    audit = {
        'metrics': metrics,
        'correlations': {
            'spearman_p_de_gene': round(rho_de_g, 4),
            'spearman_p_de_pert': round(rho_de_p, 4),
            'spearman_p_up_gene': round(rho_up_g, 4),
            'spearman_p_up_pert': round(rho_up_p, 4),
        },
        'disagreement': {
            'agree': n_agree,
            'disagree': n_disagree,
            'attempt07_right_when_disagree': a7_right_when_disagree,
            'gene_only_right_when_disagree': g_right_when_disagree,
        },
        'sample': {
            'n_rows': 60,
            'seed': 123,
            'attempt_07_missing': n_attempt07_missing,
            'gene_no_neighbor': n_gene_no_neighbor,
            'pert_no_neighbor': n_pert_no_neighbor,
        },
    }
    out_path = ROOT / 'attempts/08_audit_baselines/audit.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(audit, indent=2))
    print(f'wrote raw audit to {out_path}')

    # Verdict
    a7_combined = next(m for m in metrics if 'Attempt' in m['name'])['Combined']
    g_combined  = next(m for m in metrics if 'Gene-only' in m['name'])['Combined']
    delta = a7_combined - g_combined
    print()
    print('=== VERDICT ===')
    print(f'  Attempt 07 Combined: {a7_combined:.3f}')
    print(f'  Gene-only Combined:  {g_combined:.3f}')
    print(f'  Δ (attempt 07 − gene-only) = {delta:+.3f}')
    if g_combined <= 0.55 and delta >= 0.05:
        print('  -> World 1: ship attempt 07, the LLM is doing real reasoning')
    elif 0.56 <= g_combined <= 0.59 and delta >= 0.03:
        print('  -> Mixed: ship with caveats; the LLM adds some signal on top of gene prior')
    else:
        print('  -> World 2: gene prior dominates; pivot to CORE-style same-readout contrastive evidence')


if __name__ == '__main__':
    main()
