"""Download mouse KG raw data for attempt 03.

Sources:
  STRING mouse PPI (basic links, combined_score only)
  STRING mouse aliases (ENSP -> gene symbol)
  Reactome (all species; mouse filtered later via ENSMUSG prefix)
  GO mouse annotation (mgi.gaf.gz)

Output: data/kg_raw/*.gz / *.txt
"""
from __future__ import annotations
import os, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KG = ROOT / 'data' / 'kg_raw'
KG.mkdir(parents=True, exist_ok=True)

SOURCES = {
    '10090.protein.links.v12.0.txt.gz':
        'https://stringdb-downloads.org/download/protein.links.v12.0/10090.protein.links.v12.0.txt.gz',
    '10090.protein.aliases.v12.0.txt.gz':
        'https://stringdb-downloads.org/download/protein.aliases.v12.0/10090.protein.aliases.v12.0.txt.gz',
    'Ensembl2Reactome_All_Levels.txt':
        'https://reactome.org/download/current/Ensembl2Reactome_All_Levels.txt',
    'mgi.gaf.gz':
        'https://current.geneontology.org/annotations/mgi.gaf.gz',
}


def fetch(name: str, url: str, out: Path):
    if out.exists() and out.stat().st_size > 0:
        print(f'  {name}: exists ({out.stat().st_size} bytes), skip')
        return
    print(f'  {name}: downloading ...', end=' ', flush=True)
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'kg-fetch/1.0'})
        with urllib.request.urlopen(req, timeout=120) as r, open(out, 'wb') as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        print(f'ok ({out.stat().st_size} bytes, {time.time()-t0:.0f}s)')
    except Exception as e:
        print(f'FAILED: {e}')
        if out.exists():
            out.unlink()
        sys.exit(1)


def main():
    for name, url in SOURCES.items():
        fetch(name, url, KG / name)
    print('done.')


if __name__ == '__main__':
    main()
