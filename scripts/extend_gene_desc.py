"""Extend data/gene_desc.json with human-ortholog NCBI summaries for
mouse symbols that came back name-only. Uses mygene.info."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESC = ROOT / 'data/gene_desc.json'
M2H = ROOT / 'data/mouse_to_human_ortholog.json'


def main():
    import mygene
    mg = mygene.MyGeneInfo()
    cache = json.loads(DESC.read_text())
    m2h = json.loads(M2H.read_text())  # {mouse_symbol: HUMAN_SYMBOL}

    # Names without real summary -> try human ortholog
    candidates = [s for s, v in cache.items() if not v or v.startswith('[no summary')]
    print(f'{len(candidates)} mouse symbols need richer desc')

    # Build mouse -> human map (upper-case fallback)
    target_pairs = []
    for s in candidates:
        h = m2h.get(s) or s.upper()
        target_pairs.append((s, h))

    # Query human symbols in batches
    BATCH = 500
    n_filled = 0
    for i in range(0, len(target_pairs), BATCH):
        batch = target_pairs[i:i+BATCH]
        hsyms = [p[1] for p in batch]
        print(f'  batch {i//BATCH+1}/{(len(target_pairs)+BATCH-1)//BATCH}: {len(hsyms)} human symbols')
        try:
            res = mg.querymany(hsyms, scopes='symbol,alias', fields='symbol,summary,name',
                               species='human', returnall=True)
        except Exception as e:
            print(f'  batch failed: {e}')
            continue
        # build {query_human_symbol: best_summary}
        best = {}
        for hit in res.get('out', []):
            q = hit.get('query')
            summary = hit.get('summary', '')
            if q and summary and (q not in best or len(summary) > len(best[q])):
                best[q] = summary
        for mouse_s, human_s in batch:
            if human_s in best:
                cache[mouse_s] = best[human_s]
                n_filled += 1
        DESC.write_text(json.dumps(cache, ensure_ascii=False, indent=1))

    print(f'filled {n_filled} from human orthologs')
    # final stats
    with_sum = sum(1 for v in cache.values() if v and not v.startswith('[no summary'))
    print(f'now {with_sum}/{len(cache)} have full summaries ({with_sum/len(cache)*100:.1f}%)')


if __name__ == '__main__':
    main()
