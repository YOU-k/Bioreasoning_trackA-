"""VCWorld-style retrieval of train (pert', gene') exemplars for a test query.

For a test (pert*, gene*), select up to K=10 train pairs (pert', gene') where:
  - pert' is structurally close to pert* (STRING neighbors / Reactome shared)
  - gene' is structurally close to gene*  (same)

Test set is double-disjoint vs train (no pert overlap, no gene overlap), so
only "both-similar" pairs are possible — single-anchor patterns (same pert,
similar gene) from VCWorld's original code are empty for this competition.

The exemplar pairs are returned WITHOUT labels — caller decides how to fill
the `Result` field (random per VCWorld, or omitted).

For validation on TRAIN rows (where leakage is possible), pass
`exclude_query=True` to drop pairs that share the query's pert or gene.
"""
from __future__ import annotations
import csv, random
from collections import defaultdict
from pathlib import Path
from typing import Optional
from .kg_retrieval import KGRetrieval

ROOT = Path('/data/yy_data/Bioreasoning_trackA')
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

    def _similar_perts(self, pert: str, top_n: int = 20) -> list[str]:
        """Train perts ranked by KG similarity to query pert.
        Similarity = STRING direct edge (weighted) + Reactome shared count.
        Falls back to Reactome co-membership if pert not in STRING."""
        scores: dict[str, float] = defaultdict(float)
        # STRING direct neighbors
        for nb, score in self.kg.adj.get(pert, {}).items():
            scores[nb] += score / 1000.0  # 0-1 range from STRING confidence
        # Reactome shared pathways
        pert_paths = set(self.kg.pathways.get(pert, []))
        if pert_paths:
            for cand in self._train_perts:
                shared = pert_paths & set(self.kg.pathways.get(cand, []))
                if shared:
                    scores[cand] += len(shared) * 0.5
        # Restrict to train perts
        ranked = sorted(
            ((p, s) for p, s in scores.items() if p in set(self._train_perts) and p != pert),
            key=lambda x: -x[1],
        )
        return [p for p, _ in ranked[:top_n]]

    def _similar_genes(self, gene: str, top_n: int = 20) -> list[str]:
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
        ranked = sorted(
            ((g, s) for g, s in scores.items() if g in set(self._train_genes) and g != gene),
            key=lambda x: -x[1],
        )
        return [g for g, _ in ranked[:top_n]]

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

    @staticmethod
    def format_block_random_labels(examples: list[tuple[str, str, str]],
                                   choices: list[str], seed: int = 42) -> str:
        """VCWorld-style: render exemplars with RANDOMIZED labels (50/50)
        so the model can't vote-count, only use the structural existence."""
        rng = random.Random(seed)
        if not examples:
            return "No structurally similar (perturbed, target) pairs available in train."
        lines = []
        for i, (p, g, _real_label) in enumerate(examples, 1):
            choice = rng.choice(choices)
            lines.append(f"Example {i}: pert=`{p}`, target=`{g}`. Result: {choice}")
        return '\n'.join(lines)

    @staticmethod
    def format_block_real_labels(examples: list[tuple[str, str, str]]) -> str:
        """Alternative: keep real labels. Useful for ablation."""
        if not examples:
            return "No structurally similar (perturbed, target) pairs available in train."
        lines = []
        for i, (p, g, lbl) in enumerate(examples, 1):
            lines.append(f"Example {i}: pert=`{p}`, target=`{g}`. True label: {lbl}")
        return '\n'.join(lines)
