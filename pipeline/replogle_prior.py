"""Replogle-based cross-species prior.

Given a mouse (pert, gene) pair, return:
  - per-pert top up/down DEG list (in human space, mapped back to mouse where possible)
  - per (pert, gene) directional logFC value (if both have orthologs)
  - tier label: 'full' (both have data), 'pert_only' (pert has, gene missing), 'none'

Result of cross-species pilot (see analysis.md §A): K562+RPE1 averaged gives
DIR-AUROC=0.66 on train. DE channel is essentially useless from Replogle alone.
So this prior is used for **direction**, not for DE detection.
"""
from __future__ import annotations
import pickle, json, csv, numpy as np
from pathlib import Path

ROOT = Path('/data/yy_data/Bioreasoning_trackA')
DATA = ROOT / 'data'
REPLOGLE_PKL = DATA / 'replogle_de.pkl'
ORTHOLOG_JSON = DATA / 'mouse_to_human_ortholog.json'
GENE_INDEX_CSV = Path('/data/yy_data/RVQ-Alpha/data_utils/gene_name_list_with_index.csv')


class ReplogPrior:
    def __init__(self):
        with open(REPLOGLE_PKL, 'rb') as f:
            d = pickle.load(f)
        self.de = d['combined']         # dict: mouse_pert -> logFC vec (36601,)
        self.de_k562 = d['k562']
        self.de_rpe1 = d['rpe1']
        self.sym_to_idx = d['sym_to_idx']
        self.m2h = d['m2h']
        self.idx_to_sym = {v: k for k, v in self.sym_to_idx.items()}
        self.h2m = {}
        for m, h in self.m2h.items():
            if h not in self.h2m:
                self.h2m[h] = m

    def has_pert(self, mouse_pert: str) -> bool:
        return mouse_pert in self.de

    def has_pair(self, mouse_pert: str, mouse_gene: str) -> bool:
        if not self.has_pert(mouse_pert):
            return False
        hg = self.m2h.get(mouse_gene)
        return hg is not None and hg in self.sym_to_idx

    def get_pair_logfc(self, mouse_pert: str, mouse_gene: str) -> float | None:
        """logFC of human ortholog of `gene` under KD of human ortholog of `pert`,
        averaged across K562+RPE1 (or whichever is available)."""
        if not self.has_pert(mouse_pert):
            return None
        hg = self.m2h.get(mouse_gene)
        if hg is None or hg not in self.sym_to_idx:
            return None
        return float(self.de[mouse_pert][self.sym_to_idx[hg]])

    def get_top_responders(self, mouse_pert: str, n: int = 5) -> dict:
        """For a given mouse pert, return top n up and top n down responder genes
        in human Replogle space, with their mouse symbol if available."""
        if not self.has_pert(mouse_pert):
            return {'up': [], 'down': []}
        vec = self.de[mouse_pert]
        top_up_idx = np.argpartition(vec, -n)[-n:]
        top_up_idx = top_up_idx[np.argsort(-vec[top_up_idx])]
        top_dn_idx = np.argpartition(vec, n)[:n]
        top_dn_idx = top_dn_idx[np.argsort(vec[top_dn_idx])]

        def fmt(idx_list):
            out = []
            for i in idx_list:
                hsym = self.idx_to_sym.get(int(i), f'idx{i}')
                msym = self.h2m.get(hsym, hsym)
                out.append({'mouse_symbol': msym, 'human_symbol': hsym, 'logfc': float(vec[i])})
            return out
        return {'up': fmt(top_up_idx), 'down': fmt(top_dn_idx)}

    def tier(self, mouse_pert: str, mouse_gene: str) -> str:
        if not self.has_pert(mouse_pert):
            return 'none'
        hg = self.m2h.get(mouse_gene)
        if hg is None or hg not in self.sym_to_idx:
            return 'pert_only'
        return 'full'
