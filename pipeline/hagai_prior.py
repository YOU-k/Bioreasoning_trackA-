"""Mouse-native BMDM LPS6h direction + magnitude prior (Hagai et al. 2018).

Built from /data2/lanxiang/data/Task3_data/Hagai.h5ad (mouse subset only,
15,053 cells: 7,428 LPS6 vs 7,625 ctrl) by `scripts/build_hagai_prior.py`.

Per gene the lookup returns:
    {
        'logfc':    log2(mean(LPS6)+1) - log2(mean(ctrl)+1) after CPM norm
        'p_value':  Mann-Whitney U two-sided
        'p_adj':    Bonferroni-corrected (n_tested = n_genes_expressed)
        'mean_lps': normalized mean expression under LPS6
        'mean_ctrl':                            under ctrl
    }

This complements `pipeline/replogle_prior.py`:
* Replogle is human K562 + RPE1 → requires mouse→human ortholog, reliable
  for cell-autonomous programs (translation, ISR, proteostasis), unreliable
  for macrophage-specific programs.
* Hagai is direct mouse BMDM under inflammation → no ortholog hop, native
  for the cell context we care about.

Coverage: ~44% of train + test gene symbols, ~53% of perts.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIOR_PATH = ROOT / 'data/hagai_lps_prior.json'


class HagaiPrior:
    def __init__(self, path: Path | None = None):
        path = path or PRIOR_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found — run scripts/build_hagai_prior.py")
        blob = json.loads(path.read_text())
        self.meta = blob.get('meta', {})
        self.prior: dict[str, dict] = blob['prior']

    def get(self, symbol: str) -> dict | None:
        """Return the per-gene record, or None if the gene is not in Hagai."""
        return self.prior.get(symbol)

    def has(self, symbol: str) -> bool:
        return symbol in self.prior

    def logfc(self, symbol: str) -> float | None:
        r = self.prior.get(symbol)
        return None if r is None else r['logfc']

    def is_significant(self, symbol: str, p_thresh: float = 0.05,
                       lfc_thresh: float = 0.585) -> bool:
        """LPS-DE call: padj < p_thresh AND |logfc| >= lfc_thresh
        (lfc_thresh defaults to log2(1.5) ≈ 0.585, matching the competition's
        DE threshold)."""
        r = self.prior.get(symbol)
        if r is None:
            return False
        return r['p_adj'] < p_thresh and abs(r['logfc']) >= lfc_thresh


_DEFAULT: HagaiPrior | None = None


def default() -> HagaiPrior:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = HagaiPrior()
    return _DEFAULT
