"""VCWorld-style retrieval of train (pert', gene') exemplars for a test query.

For a test (pert*, gene*), select up to K=10 train pairs (pert', gene') where:
  - pert' is structurally close to pert* (STRING neighbors / Reactome shared)
  - gene' is structurally close to gene*  (same)

Retrieval prefers examples where BOTH anchors are structurally similar. When
one side has no KG neighborhood, it falls back to SINGLE-anchor examples
(similar pert with any train gene, or similar gene with any train pert)
instead of returning an empty evidence block.

Two retrieval modes are provided:

* `retrieve()` — flat top-K by KG similarity (no label conditioning).
* `retrieve_analog_contrast()` — paper §3.4.2 design. Splits train pairs
  into two label-conditioned pools (positive outcome / negative outcome),
  ranks each by KG similarity, returns top-k_a analogue + top-k_c contrast.
  Rendered with REAL labels by `format_block_analog_contrast` — vote bias
  is defeated structurally by the forced mix of positive and negative
  examples, not by destroying the label signal.

For validation on TRAIN rows (where leakage is possible), pass
`exclude_query=True` to drop pairs that share the query's pert or gene.
"""
from __future__ import annotations
import csv, random
from collections import defaultdict
from pathlib import Path
from typing import Optional
from .kg_retrieval import KGRetrieval

ROOT = Path(__file__).resolve().parent.parent
_TRAIN = ROOT / 'data' / 'train.csv'


class ExampleRetriever:
    def __init__(self, kg: Optional[KGRetrieval] = None):
        self.kg = kg or KGRetrieval()
        # Load train.csv
        self._train = []
        for r in csv.DictReader(open(_TRAIN)):
            self._train.append((r['pert'], r['gene'], r['label']))
        # Index: pert -> set of train genes, gene -> set of train perts
        self._train_perts = sorted({p for p, _, _ in self._train})
        self._train_genes = sorted({g for _, g, _ in self._train})
        # (pert, gene) -> label lookup
        self._pair_label = {(p, g): lbl for p, g, lbl in self._train}

    def _similar_perts_scored(self, pert: str, top_n: int = 20) -> list[tuple[str, float]]:
        """Train perts ranked by KG similarity to query pert.
        Similarity = STRING direct edge (weighted) + Reactome shared count.
        Falls back to Reactome co-membership if pert not in STRING."""
        scores: dict[str, float] = defaultdict(float)
        for nb, score in self.kg.adj.get(pert, {}).items():
            scores[nb] += score / 1000.0  # 0-1 range from STRING confidence
        pert_paths = set(self.kg.pathways.get(pert, []))
        if pert_paths:
            for cand in self._train_perts:
                shared = pert_paths & set(self.kg.pathways.get(cand, []))
                if shared:
                    scores[cand] += len(shared) * 0.5
        train_perts = set(self._train_perts)
        ranked = sorted(
            ((p, s) for p, s in scores.items() if p in train_perts and p != pert),
            key=lambda x: -x[1],
        )
        return ranked[:top_n]

    def _similar_genes_scored(self, gene: str, top_n: int = 20) -> list[tuple[str, float]]:
        """Train genes ranked by KG similarity to query gene (same logic)."""
        scores: dict[str, float] = defaultdict(float)
        for nb, score in self.kg.adj.get(gene, {}).items():
            scores[nb] += score / 1000.0
        gene_paths = set(self.kg.pathways.get(gene, []))
        if gene_paths:
            for cand in self._train_genes:
                shared = gene_paths & set(self.kg.pathways.get(cand, []))
                if shared:
                    scores[cand] += len(shared) * 0.5
        train_genes = set(self._train_genes)
        ranked = sorted(
            ((g, s) for g, s in scores.items() if g in train_genes and g != gene),
            key=lambda x: -x[1],
        )
        return ranked[:top_n]

    def _similar_perts(self, pert: str, top_n: int = 20) -> list[str]:
        return [p for p, _ in self._similar_perts_scored(pert, top_n)]

    def _similar_genes(self, gene: str, top_n: int = 20) -> list[str]:
        return [g for g, _ in self._similar_genes_scored(gene, top_n)]

    def retrieve(self, pert: str, gene: str, budget: int = 10,
                 exclude_query: bool = False, seed: int = 42) -> list[tuple[str, str, str]]:
        """Return up to `budget` (pert', gene', label) train triplets.

        Strategy:
          1. Both-similar: pert' similar to pert AND gene' similar to gene
          2. Single anchor as backup: pert' similar AND gene' is any train gene
             that pert' was tested with (only if step 1 underfills)
        """
        rng = random.Random(seed)
        close_perts = self._similar_perts(pert, top_n=30)
        close_genes = self._similar_genes(gene, top_n=30)
        # Train pair index for fast both-anchor lookup
        both = [(p2, g2, self._pair_label[(p2, g2)])
                for p2 in close_perts for g2 in close_genes
                if (p2, g2) in self._pair_label]
        if exclude_query:
            both = [(p2, g2, l) for p2, g2, l in both if p2 != pert and g2 != gene]
        if len(both) > budget:
            both = rng.sample(both, budget)

        if len(both) < budget:
            # Pad with single-anchor: for each close_pert, pick one train gene
            need = budget - len(both)
            seen = set((p2, g2) for p2, g2, _ in both)
            single = []
            # pert-anchor: same close_pert with one of its actual train genes
            for p2 in close_perts:
                for p3, g3, lbl in self._train:
                    if p3 == p2 and (p3, g3) not in seen:
                        single.append((p3, g3, lbl))
                        seen.add((p3, g3))
                        break
            if exclude_query:
                single = [(p, g, l) for p, g, l in single if p != pert and g != gene]
            if single:
                rng.shuffle(single)
                both += single[:need]

        return both

    def retrieve_analog_contrast(self, pert: str, gene: str, *,
                                 task: str,
                                 k_a: int = 5, k_c: int = 5,
                                 exclude_query: bool = False,
                                 seed: int = 42,
                                 ) -> tuple[list[tuple[str, str, str]],
                                            list[tuple[str, str, str]]]:
        """Paper §3.4.2 retrieval with single-anchor fallback.

        Splits train pairs into label-conditioned pools and ranks each by KG
        similarity to the query (pert, gene). Candidate ranking prefers
        examples with BOTH anchors matched; when only one side is matched, the
        candidate is still allowed as a fallback with lower priority.
        Returns (analog, contrast) where each list contains
        (pert', gene', real_label) triplets.

        task='de'  -> analog pool = {up, down}; contrast pool = {none}
        task='dir' -> analog pool = {up};       contrast pool = {down}
                     (label='none' pairs excluded entirely)
        """
        if task not in ('de', 'dir'):
            raise ValueError(f"task must be 'de' or 'dir', got {task!r}")
        rng = random.Random(seed)
        pert_scores = dict(self._similar_perts_scored(pert, top_n=50))
        gene_scores = dict(self._similar_genes_scored(gene, top_n=50))
        if not pert_scores and not gene_scores:
            return [], []
        candidates = []
        for p2, g2, lbl in self._train:
            if exclude_query and (p2 == pert or g2 == gene):
                continue
            ps = pert_scores.get(p2, 0.0)
            gs = gene_scores.get(g2, 0.0)
            anchor_count = int(ps > 0) + int(gs > 0)
            if anchor_count == 0:
                continue
            pair_sim = ps + gs
            candidates.append((anchor_count, pair_sim, p2, g2, lbl))

        if task == 'de':
            pos_labels = {'up', 'down'}
            neg_labels = {'none'}
        else:
            pos_labels = {'up'}
            neg_labels = {'down'}

        pos_pool = [(a, s, p, g, l) for a, s, p, g, l in candidates if l in pos_labels]
        neg_pool = [(a, s, p, g, l) for a, s, p, g, l in candidates if l in neg_labels]
        # Prefer two-anchor matches; break ties by total KG similarity, with a
        # shuffle first so identical scores do not always return the same rows.
        rng.shuffle(pos_pool)
        rng.shuffle(neg_pool)
        pos_pool.sort(key=lambda t: (-t[0], -t[1]))
        neg_pool.sort(key=lambda t: (-t[0], -t[1]))

        analog = [(p, g, l) for _, _, p, g, l in pos_pool[:k_a]]
        contrast = [(p, g, l) for _, _, p, g, l in neg_pool[:k_c]]
        return analog, contrast

    @staticmethod
    def format_block_real_labels(examples: list[tuple[str, str, str]]) -> str:
        """Alternative: keep real labels. Useful for ablation."""
        if not examples:
            return "No structurally similar (perturbed, target) pairs available in train."
        lines = []
        for i, (p, g, lbl) in enumerate(examples, 1):
            lines.append(f"Example {i}: pert=`{p}`, target=`{g}`. True label: {lbl}")
        return '\n'.join(lines)

    @staticmethod
    def format_block_analog_contrast(analog: list[tuple[str, str, str]],
                                     contrast: list[tuple[str, str, str]],
                                     *, task: str, seed: int = 42) -> str:
        """Paper §3.4.2 + Appendix D rendering.

        Combine analog (positive outcome) and contrast (negative outcome)
        pools into one shuffled list, showing the REAL label per example.
        Per-task label rendering:
          task='de'  -> "DE: Yes" (up/down) or "DE: No" (none)
          task='dir' -> "Increase" (up) or "Decrease" (down)
        """
        if not analog and not contrast:
            return "No structurally similar (perturbed, target) pairs available in train."
        combined = list(analog) + list(contrast)
        random.Random(seed).shuffle(combined)
        def render_label(lbl: str) -> str:
            if task == 'de':
                return 'Yes (differentially expressed)' if lbl in ('up', 'down') \
                    else 'No (not differentially expressed)'
            return 'Increase' if lbl == 'up' else 'Decrease'
        lines = []
        for i, (p, g, lbl) in enumerate(combined, 1):
            lines.append(f"Example {i}: pert=`{p}`, target=`{g}`. Result: {render_label(lbl)}")
        return '\n'.join(lines)
