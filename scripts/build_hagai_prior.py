"""Build a mouse-native DE direction prior from Hagai et al. 2018 BMDM
LPS6h vs ctrl perturb-seq.

Source: /data2/lanxiang/data/Task3_data/Hagai.h5ad
- 62,114 cells total (rat / rabbit / mouse / pig)
- Conditions: ctrl (n=33,350) vs LPS6 (n=28,764)
- Mouse subset: ~15,053 cells

We compute per-gene log2(fold change) and a Wilcoxon-equivalent p-value
between LPS6 and ctrl using only mouse cells.

Output: `data/hagai_lps_prior.json` — {symbol: {logfc, p_value, n_lps, n_ctrl}}

This gives us a mouse-BMDM-NATIVE direction prior, complementing Replogle
(human K562/RPE1) which doesn't transfer well for macrophage-specific
programs.
"""
from __future__ import annotations
import csv, json, sys
from collections import Counter
from pathlib import Path

import anndata as ad
import numpy as np
import scipy.sparse as sp
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
HAGAI_PATH = Path('/data2/lanxiang/data/Task3_data/Hagai.h5ad')
OUT_PATH = ROOT / 'data/hagai_lps_prior.json'


def main():
    print(f'Loading {HAGAI_PATH} ...')
    A = ad.read_h5ad(HAGAI_PATH)
    print(f'  shape: {A.shape}')
    print(f'  conditions: {dict(A.obs["condition"].value_counts())}')
    print(f'  species:    {dict(A.obs["species"].value_counts())}')

    # Subset to mouse only
    is_mouse = A.obs['species'] == 'mouse'
    A_m = A[is_mouse].copy()
    print(f'\nMouse subset: {A_m.n_obs} cells')
    cond = A_m.obs['condition'].values
    n_lps  = int((cond == 'LPS6').sum())
    n_ctrl = int((cond == 'ctrl').sum())
    print(f'  LPS6: {n_lps}, ctrl: {n_ctrl}')

    # Get gene names — try the cleanest column. var_names should be the symbol.
    genes = list(A_m.var_names)
    print(f'  genes: {len(genes)}')
    print(f'  sample genes: {genes[:5]} ... {genes[-5:]}')

    # X is sparse — convert to dense per gene as needed to keep memory sane
    X = A_m.X
    if not sp.issparse(X):
        X = sp.csr_matrix(X)
    # Confirm gene-major access (need column slicing) → convert to CSC
    X = X.tocsc()

    mask_lps  = (cond == 'LPS6')
    mask_ctrl = (cond == 'ctrl')
    n_genes = X.shape[1]

    # Compute log fold change using normalized counts.
    # First normalize per-cell: count / sum(count) * 1e4, then log1p.
    # (This is standard Scanpy practice for DE on raw counts.)
    # We'll do this gene-by-gene to avoid blowing up memory.

    # Step A: per-cell library size
    lib = np.asarray(X.sum(axis=1)).flatten() + 1e-8

    print(f'\nComputing logFC + p_value per gene ...')
    results = []
    log_step = max(1, n_genes // 20)
    for j in range(n_genes):
        col = X[:, j].toarray().flatten()
        # CPM-style normalize
        norm = (col / lib) * 1e4
        x_lps  = np.log1p(norm[mask_lps])
        x_ctrl = np.log1p(norm[mask_ctrl])

        mean_lps  = float(np.mean(x_lps))
        mean_ctrl = float(np.mean(x_ctrl))
        logfc = mean_lps - mean_ctrl  # log scale already

        # Skip MWU if gene is essentially zero (saves a lot of time)
        if max(mean_lps, mean_ctrl) < 1e-3:
            pval = 1.0
        else:
            try:
                _, pval = mannwhitneyu(x_lps, x_ctrl, alternative='two-sided')
                pval = float(pval)
            except Exception:
                pval = 1.0

        results.append({
            'gene':     genes[j],
            'logfc':    round(logfc, 4),
            'mean_lps': round(mean_lps, 4),
            'mean_ctrl': round(mean_ctrl, 4),
            'p_value':  pval,
        })

        if (j + 1) % log_step == 0:
            print(f'  {j+1}/{n_genes} ({100*(j+1)/n_genes:.0f}%)')

    # Bonferroni-ish correction: padj = pval * n_genes_tested (capped at 1)
    n_tested = sum(1 for r in results if r['p_value'] < 1.0)
    for r in results:
        r['p_adj'] = min(1.0, r['p_value'] * n_tested)
        r['p_adj'] = round(r['p_adj'], 6)

    # Save the lookup
    lookup = {r['gene']: {'logfc': r['logfc'], 'p_value': r['p_value'],
                          'p_adj': r['p_adj'],
                          'mean_lps': r['mean_lps'],
                          'mean_ctrl': r['mean_ctrl']}
              for r in results}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        'meta': {
            'source': 'Hagai et al. 2018 - mouse BMDM LPS6 vs ctrl',
            'n_lps': n_lps, 'n_ctrl': n_ctrl,
            'n_genes': n_genes,
        },
        'prior': lookup,
    }, indent=2))
    print(f'\nwrote {OUT_PATH}')

    # Coverage summary against train + test
    train_g = set(r['gene'] for r in csv.DictReader(open(ROOT / 'data/train.csv')))
    train_p = set(r['pert'] for r in csv.DictReader(open(ROOT / 'data/train.csv')))
    test_g  = set(r['gene'] for r in csv.DictReader(open(ROOT / 'data/test.csv')))
    test_p  = set(r['pert'] for r in csv.DictReader(open(ROOT / 'data/test.csv')))

    h_genes = set(lookup.keys())
    print('\n=== Coverage ===')
    print(f'  Hagai genes (mouse, with logfc): {len(h_genes)}')
    for name, s in [('train gene', train_g), ('train pert', train_p),
                    ('test gene', test_g), ('test pert', test_p)]:
        c = len(s & h_genes)
        print(f'  {name:<14s} {c}/{len(s)} ({100*c/len(s):.1f}%) in Hagai')

    # Show distribution of |logfc| for a few well-known LPS targets
    print('\n=== Sanity check on known LPS targets ===')
    targets = ['Tnf', 'Il6', 'Il1b', 'Nfkb1', 'Stat1', 'Irf3', 'Ifit1', 'Isg15',
               'Atf4', 'Ddit3', 'Hspa5', 'Lyz1', 'Cd14', 'Trib3', 'Mki67', 'Ccnb1',
               'Hmox1', 'Sod2', 'Aars', 'Cebpb']
    print(f'  {"gene":<10s} {"logfc":>8s} {"p_adj":>10s}  (>0 = UP under LPS)')
    for g in targets:
        if g in lookup:
            v = lookup[g]
            sig = '✓' if v['p_adj'] < 0.05 else ' '
            print(f'  {g:<10s} {v["logfc"]:>+8.3f}  {v["p_adj"]:>10.2e} {sig}')
        else:
            print(f'  {g:<10s} not in Hagai (mouse)')


if __name__ == '__main__':
    main()
