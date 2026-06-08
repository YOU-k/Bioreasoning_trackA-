"""Loader for per-gene functional descriptions.

Source: data/gene_desc.json (built by scripts/build_gene_desc.py +
scripts/extend_gene_desc.py).

Format: {mouse_symbol: "summary text"}.
For symbols missing a real summary (or completely absent), returns a
fallback string built from the name field + KG pathway membership.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

ROOT = Path('/data/yy_data/Bioreasoning_trackA')
_DESC_FILE = ROOT / 'data' / 'gene_desc.json'


class GeneDesc:
    def __init__(self):
        if _DESC_FILE.exists():
            self._raw = json.loads(_DESC_FILE.read_text())
        else:
            self._raw = {}

    def get(self, symbol: str, max_chars: int = 350,
            pathway_fallback: Optional[list[str]] = None) -> str:
        """Return a one-line trimmed description for a gene symbol.
        Falls back to '[no summary] <name>' or a pathway-list synthesis."""
        raw = self._raw.get(symbol, '')
        if raw and not raw.startswith('[no summary'):
            # Have a real summary; collapse whitespace, trim
            t = ' '.join(raw.split())
            if len(t) > max_chars:
                t = t[: max_chars - 1].rsplit(' ', 1)[0] + '…'
            return t
        # No summary available: combine name + pathway list (if provided)
        name_part = raw.replace('[no summary] ', '') if raw else symbol
        if pathway_fallback:
            top = '; '.join(pathway_fallback[:3])
            return f'{name_part}. Pathway membership: {top}'
        return name_part if name_part else symbol


_DEFAULT: Optional[GeneDesc] = None


def default() -> GeneDesc:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = GeneDesc()
    return _DEFAULT
