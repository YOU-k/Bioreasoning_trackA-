"""Layer 2 — KG mechanism context for a (pert, gene) pair.

For each query returns:
  - Reactome pathways the pert belongs to (top 3)
  - Reactome pathways the gene belongs to (top 3)
  - Shared pathways (mechanistic connection)
  - STRING shortest path pert -> gene (if any within depth 3, score >=700)

The index is built by attempts/03_kg_celltype/build_kg_index.py and lives
under data/kg_index/.
"""
from __future__ import annotations
import json
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KG = ROOT / 'data' / 'kg_index'


class KGRetrieval:
    def __init__(self):
        self.pathways = json.loads((KG / 'gene_reactome.json').read_text())
        edges = json.loads((KG / 'string_edges.json').read_text())
        self.adj = defaultdict(dict)
        for a, b, score in edges:
            # Keep max-score edge if duplicate
            if score > self.adj[a].get(b, 0):
                self.adj[a][b] = score
                self.adj[b][a] = score
        self._edge_count = sum(len(v) for v in self.adj.values()) // 2

    def has_pathways(self, gene: str) -> bool:
        return gene in self.pathways

    def get_pathways(self, gene: str, top_n: int = 3) -> list[str]:
        return self.pathways.get(gene, [])[:top_n]

    def shared_pathways(self, a: str, b: str) -> list[str]:
        sa = set(self.pathways.get(a, []))
        sb = set(self.pathways.get(b, []))
        return sorted(sa & sb, key=len, reverse=True)

    def shortest_path(self, src: str, dst: str, max_depth: int = 3) -> list[str] | None:
        """BFS for shortest path src -> dst at depth <= max_depth.
        Returns the list of symbols [src, ..., dst] or None if no such path.
        Score is implicit (all edges in adj are already >=700 STRING)."""
        if src == dst:
            return [src]
        if src not in self.adj or dst not in self.adj:
            return None
        if dst in self.adj[src]:
            return [src, dst]
        # BFS
        visited = {src: None}
        q = deque([(src, 0)])
        while q:
            node, depth = q.popleft()
            if depth >= max_depth:
                continue
            for nb in self.adj[node]:
                if nb in visited:
                    continue
                visited[nb] = node
                if nb == dst:
                    # Reconstruct path
                    path = [dst]
                    cur = node
                    while cur is not None:
                        path.append(cur)
                        cur = visited[cur]
                    return list(reversed(path))
                q.append((nb, depth + 1))
        return None

    def get_context(self, pert: str, gene: str, max_path_depth: int = 3) -> dict:
        """Bundle everything for a query into one dict."""
        return {
            'pert_pathways': self.get_pathways(pert),
            'gene_pathways': self.get_pathways(gene),
            'shared_pathways': self.shared_pathways(pert, gene)[:3],
            'shortest_path': self.shortest_path(pert, gene, max_path_depth),
        }

    def stats(self) -> dict:
        return {
            'n_genes_with_pathways': len(self.pathways),
            'n_high_conf_edges': self._edge_count,
            'n_nodes_in_graph': len(self.adj),
        }
