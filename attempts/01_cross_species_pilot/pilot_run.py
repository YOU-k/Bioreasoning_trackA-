"""Rebuild Replogle DE prior with merged ortholog strategy:
   1. mygene ortholog (modern names)
   2. fallback to naive uppercase
   Recompute DE for any perts rescued by the fallback.
"""
import anndata, csv, json, numpy as np, time, pickle
t0 = time.time()

# Load gene index
sym_to_idx = {}
with open('/data/yy_data/RVQ-Alpha/data_utils/gene_name_list_with_index.csv') as f:
    for row in csv.DictReader(f):
        sym_to_idx[row['Gene_Name']] = int(row['Index']) - 1

# Load mygene ortholog
with open('/data/yy_data/Bioreasoning_trackA/mouse_to_human_ortholog.json') as f:
    m2h_mygene = json.load(f)

# Build merged: mygene preferred, uppercase fallback
mouse_syms = set()
for f in ['/data/yy_data/Bioreasoning_trackA/train.csv', '/data/yy_data/Bioreasoning_trackA/test.csv']:
    with open(f) as fh:
        for row in csv.DictReader(fh):
            mouse_syms.add(row['pert'])
            mouse_syms.add(row['gene'])

# Get all Replogle conds first
def replogle_perts(path):
    a = anndata.read_h5ad(path, backed='r')
    return {c.replace('+ctrl','').split('+')[0] for c in a.obs['condition'].unique() if c != 'ctrl'}, a

k_perts, a_k = replogle_perts("/data/data/biodata/scRNAseq/drug_pert/normalized/P007_ReplogleWeissman2022_K562_essential.h5ad")
r_perts, a_r = replogle_perts("/data/data/biodata/scRNAseq/drug_pert/normalized/P007_ReplogleWeissman2022_rpe1.h5ad")
all_replogle = k_perts | r_perts

# Best ortholog per mouse symbol (prefers mygene, falls back to uppercase if uppercase is in Replogle)
m2h_best = {}
for m in mouse_syms:
    cand_mg = m2h_mygene.get(m)
    cand_up = m.upper()
    if cand_mg in all_replogle:
        m2h_best[m] = cand_mg
    elif cand_up in all_replogle:
        m2h_best[m] = cand_up
    elif cand_mg in sym_to_idx:
        # not in Replogle perts, but maybe useful for gene-side lookup
        m2h_best[m] = cand_mg
    elif cand_up in sym_to_idx:
        m2h_best[m] = cand_up
    # else: no mapping at all

print(f"[t={time.time()-t0:.0f}s] m2h_best size: {len(m2h_best)}")

# Compute DE: build matched dict using m2h_best for ALL perts (train+test+gene)
def compute_de(adata, label):
    t1 = time.time()
    conds = {c.replace('+ctrl','').split('+')[0]: c for c in adata.obs['condition'].unique() if c != 'ctrl'}
    matched = {m: conds[m2h_best[m]] for m in m2h_best if m2h_best[m] in conds}
    print(f"[{label}] matched: {len(matched)}")
    ctrl_cells = np.where((adata.obs['condition'] == 'ctrl').values)[0]
    X_ctrl = adata.X[ctrl_cells, :]
    mean_ctrl = np.asarray(X_ctrl.mean(axis=0)).flatten()
    de = {}
    for mp, cond_str in matched.items():
        cells = np.where((adata.obs['condition'] == cond_str).values)[0]
        if len(cells) < 10: continue
        X = adata.X[cells, :]
        mean_p = np.asarray(X.mean(axis=0)).flatten()
        de[mp] = mean_p - mean_ctrl
    print(f"[{label}] DE for {len(de)} perts in {time.time()-t1:.0f}s")
    return de

de_k562 = compute_de(a_k, "K562")
de_rpe1 = compute_de(a_r, "RPE1")

# Combined
de_combined = {}
for p in (set(de_k562) | set(de_rpe1)):
    if p in de_k562 and p in de_rpe1:
        de_combined[p] = (de_k562[p] + de_rpe1[p]) / 2
    elif p in de_k562:
        de_combined[p] = de_k562[p]
    else:
        de_combined[p] = de_rpe1[p]

# Re-evaluate
train_rows = []
with open('/data/yy_data/Bioreasoning_trackA/train.csv') as f:
    for row in csv.DictReader(f):
        train_rows.append((row['pert'], row['gene'], row['label']))

from sklearn.metrics import roc_auc_score
def eval_de(de_dict, name):
    preds = []
    for pert, gene, label in train_rows:
        if pert not in de_dict: continue
        hg = m2h_best.get(gene)
        if hg is None or hg not in sym_to_idx: continue
        preds.append((float(de_dict[pert][sym_to_idx[hg]]), label))
    y_de = np.array([0 if p[1]=='none' else 1 for p in preds])
    s_de = np.array([abs(p[0]) for p in preds])
    de_auc = roc_auc_score(y_de, s_de)
    mask = [p[1]!='none' for p in preds]
    y_dir = np.array([1 if preds[i][1]=='up' else 0 for i in range(len(preds)) if mask[i]])
    s_dir = np.array([preds[i][0] for i in range(len(preds)) if mask[i]])
    dir_auc = roc_auc_score(y_dir, s_dir)
    print(f"[{name}] n={len(preds)}  DE={de_auc:.4f}  DIR={dir_auc:.4f}  combined={(de_auc+dir_auc)/2:.4f}")

print("\n=== v3 (merged ortholog: mygene + upper fallback) ===")
eval_de(de_k562, "K562")
eval_de(de_rpe1, "RPE1")
eval_de(de_combined, "K562+RPE1_avg")

# Save
with open('/data/yy_data/Bioreasoning_trackA/replogle_de.pkl', 'wb') as f:
    pickle.dump({'k562': de_k562, 'rpe1': de_rpe1, 'combined': de_combined,
                 'm2h': m2h_best, 'sym_to_idx': sym_to_idx}, f)
print(f"\nSaved replogle_de.pkl. Total: {time.time()-t0:.0f}s")
