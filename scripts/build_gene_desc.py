"""One-time fetch of gene functional summaries for all mouse symbols
appearing in train + test (pert or gene). Uses mygene.info.

Output: data/gene_desc.json  {symbol: "summary text"}

Symbols with no available summary are stored as empty string so we don't
re-query next time.
"""
from __future__ import annotations
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data/gene_desc.json'


def collect_symbols() -> list[str]:
    syms = set()
    for f in ['data/train.csv', 'data/test.csv']:
        for r in csv.DictReader(open(ROOT / f)):
            syms.add(r['pert'])
            syms.add(r['gene'])
    return sorted(syms)


def main():
    import mygene
    mg = mygene.MyGeneInfo()
    symbols = collect_symbols()
    print(f'querying mygene.info for {len(symbols)} mouse symbols...')

    # Load existing cache if any
    cache: dict[str, str] = {}
    if OUT.exists():
        cache = json.loads(OUT.read_text())
        print(f'existing cache: {len(cache)} symbols, will skip those')

    todo = [s for s in symbols if s not in cache]
    if not todo:
        print('cache complete; nothing to do.')
        return

    # batch query — mygene allows up to ~1000 per call
    BATCH = 500
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i+BATCH]
        print(f'  batch {i // BATCH + 1}/{(len(todo) + BATCH - 1) // BATCH}: {len(batch)} symbols')
        try:
            res = mg.querymany(
                batch,
                scopes='symbol,alias',
                fields='symbol,summary,name',
                species='mouse',
                returnall=True,
            )
        except Exception as e:
            print(f'  batch failed: {e}')
            continue
        # res = {"out": [...], "missing": [...], "dup": [...]}
        for hit in res.get('out', []):
            q = hit.get('query')
            if q is None: continue
            summary = hit.get('summary', '')
            name = hit.get('name', '')
            if summary:
                cache[q] = summary
            elif name and q not in cache:
                cache[q] = f'[no summary] {name}'
        for miss in res.get('missing', []):
            q = miss.get('query') if isinstance(miss, dict) else miss
            if q not in cache:
                cache[q] = ''
        # write incremental
        OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=1))

    print(f'done. cache now has {len(cache)} symbols.')
    n_with = sum(1 for v in cache.values() if v and not v.startswith('[no summary'))
    n_name = sum(1 for v in cache.values() if v.startswith('[no summary'))
    n_empty = sum(1 for v in cache.values() if not v)
    print(f'  with summary: {n_with}')
    print(f'  name-only:    {n_name}')
    print(f'  empty:        {n_empty}')


if __name__ == '__main__':
    main()
