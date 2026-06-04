"""Build the filtered KG index used by pipeline/kg_retrieval.py.

Reads:
  data/kg_raw/10090.protein.aliases.v12.0.txt.gz
  data/kg_raw/10090.protein.links.v12.0.txt.gz
  data/kg_raw/Ensembl2Reactome_All_Levels.txt
  data/train.csv, data/test.csv  (to know which symbols matter)

Writes:
  data/kg_index/symbol_to_ensp.json
  data/kg_index/string_edges.json    high-confidence (>=700) edges as symbols
  data/kg_index/gene_reactome.json   {symbol: [pathway_name, ...]}
"""
from __future__ import annotations
import csv, gzip, json, time
from collections import defaultdict
from pathlib import Path

ROOT = Path('/data/yy_data/Bioreasoning_trackA')
RAW = ROOT / 'data/kg_raw'
OUT = ROOT / 'data/kg_index'
OUT.mkdir(exist_ok=True)

STRING_SCORE_MIN = 700  # high-confidence per STRING docs (>=700 of 1000)


def collect_genes_of_interest() -> set:
    """Mouse symbols seen in train/test (pert or gene column)."""
    s = set()
    for f in [ROOT / 'data/train.csv', ROOT / 'data/test.csv']:
        with open(f) as fh:
            for row in csv.DictReader(fh):
                s.add(row['pert'])
                s.add(row['gene'])
    return s


def build_string_mappings():
    """Parse STRING aliases. Returns (ensp_to_symbol, ensp_to_ensmusg).
    Strips the '10090.' prefix from protein IDs.
    """
    t0 = time.time()
    ensp_to_symbol = {}     # bare ENSP -> mouse symbol
    ensp_to_ensmusg = {}    # bare ENSP -> ENSMUSG
    with gzip.open(RAW / '10090.protein.aliases.v12.0.txt.gz', 'rt') as fh:
        for line in fh:
            if line.startswith('#'):
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            pid, alias, source = parts[0], parts[1], parts[2]
            ensp = pid.split('.', 1)[1] if '.' in pid else pid
            if source == 'Ensembl_MGI' and ensp not in ensp_to_symbol:
                ensp_to_symbol[ensp] = alias
            elif source == 'Ensembl_gene' and alias.startswith('ENSMUSG'):
                ensp_to_ensmusg[ensp] = alias
    print(f'  [{time.time()-t0:.0f}s] STRING aliases: {len(ensp_to_symbol)} ENSP->symbol, {len(ensp_to_ensmusg)} ENSP->ENSMUSG')
    return ensp_to_symbol, ensp_to_ensmusg


def ensmusg_to_symbol_map(ensp_to_symbol, ensp_to_ensmusg) -> dict:
    """Compose two maps."""
    m = {}
    for ensp, ensmusg in ensp_to_ensmusg.items():
        sym = ensp_to_symbol.get(ensp)
        if sym:
            m.setdefault(ensmusg, sym)
    return m


def build_string_edges(ensp_to_symbol, goi: set):
    """High-confidence STRING edges where at least one endpoint is in goi.
    Symbol-keyed."""
    t0 = time.time()
    edges = []
    n_read = 0
    with gzip.open(RAW / '10090.protein.links.v12.0.txt.gz', 'rt') as fh:
        header = fh.readline()
        for line in fh:
            n_read += 1
            a, b, score = line.rstrip('\n').split(' ')
            score = int(score)
            if score < STRING_SCORE_MIN:
                continue
            ea = a.split('.', 1)[1] if '.' in a else a
            eb = b.split('.', 1)[1] if '.' in b else b
            sa = ensp_to_symbol.get(ea)
            sb = ensp_to_symbol.get(eb)
            if not sa or not sb:
                continue
            if sa not in goi and sb not in goi:
                continue
            edges.append([sa, sb, score])
    print(f'  [{time.time()-t0:.0f}s] STRING edges: {len(edges)} high-conf, '
          f'>=1 endpoint in {len(goi)} genes (read {n_read} total lines)')
    return edges


def build_gene_reactome(ensmusg_to_symbol: dict, goi: set):
    """Parse Reactome all-levels, filter mouse rows, keep our gene set."""
    t0 = time.time()
    pathways = defaultdict(set)   # symbol -> {pathway_name}
    n_mouse = 0
    with open(RAW / 'Ensembl2Reactome_All_Levels.txt') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 6 or not parts[0].startswith('ENSMUSG'):
                continue
            n_mouse += 1
            ensmusg, pid, url, name, ev, species = parts[:6]
            sym = ensmusg_to_symbol.get(ensmusg)
            if not sym or sym not in goi:
                continue
            pathways[sym].add(name)
    # Keep ALL pathways per gene (~30 KB extra). Display layer truncates;
    # categorization layer needs the full list to match keywords reliably.
    out = {s: sorted(v) for s, v in pathways.items()}
    print(f'  [{time.time()-t0:.0f}s] Reactome: {n_mouse} mouse rows total, '
          f'{len(out)} genes with >=1 pathway (out of {len(goi)} GOI)')
    return out


def main():
    t0 = time.time()
    print('collecting genes of interest from train/test...')
    goi = collect_genes_of_interest()
    print(f'  {len(goi)} unique mouse symbols')

    print('parsing STRING aliases...')
    ensp_to_symbol, ensp_to_ensmusg = build_string_mappings()
    ensmusg_to_sym = ensmusg_to_symbol_map(ensp_to_symbol, ensp_to_ensmusg)
    print(f'  composed ENSMUSG->symbol: {len(ensmusg_to_sym)}')

    print('parsing STRING links (>=700)...')
    edges = build_string_edges(ensp_to_symbol, goi)

    print('parsing Reactome (mouse rows)...')
    gene_react = build_gene_reactome(ensmusg_to_sym, goi)

    # Save
    sym_to_ensp = {s: e for e, s in ensp_to_symbol.items() if s in goi}
    (OUT / 'symbol_to_ensp.json').write_text(json.dumps(sym_to_ensp))
    (OUT / 'string_edges.json').write_text(json.dumps(edges))
    (OUT / 'gene_reactome.json').write_text(json.dumps(gene_react, ensure_ascii=False))

    # Stats: how many of our 96 test perts have Reactome pathways?
    test_perts = set()
    with open(ROOT / 'data/test.csv') as fh:
        for row in csv.DictReader(fh):
            test_perts.add(row['pert'])
    has_path = sum(1 for p in test_perts if p in gene_react)
    print(f'\n=== Index built in {time.time()-t0:.0f}s ===')
    print(f'  symbol_to_ensp.json:   {len(sym_to_ensp)} entries')
    print(f'  string_edges.json:     {len(edges)} edges')
    print(f'  gene_reactome.json:    {len(gene_react)} genes with pathways')
    print(f'  test pert coverage:    {has_path}/{len(test_perts)} ({has_path/len(test_perts)*100:.0f}%) have Reactome pathways')
    for f in OUT.glob('*.json'):
        print(f'    {f.name}: {f.stat().st_size} bytes')


if __name__ == '__main__':
    main()
