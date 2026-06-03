"""Build mouse->human ortholog map for all Track A perts and genes.

Strategy:
  1. Query mygene with scopes='symbol' (precise) for all mouse symbols
  2. For misses, retry with scopes='symbol,alias,name'
  3. From homologene.genes, extract human entry (taxid=9606)
  4. Map entrez ID to symbol via second mygene call
"""
import mygene, csv, json, time

mg = mygene.MyGeneInfo()
t0 = time.time()

# Collect all mouse symbols
mouse_symbols = set()
for f in ['/data/yy_data/Bioreasoning_trackA/train.csv',
          '/data/yy_data/Bioreasoning_trackA/test.csv']:
    with open(f) as fh:
        for row in csv.DictReader(fh):
            mouse_symbols.add(row['pert'])
            mouse_symbols.add(row['gene'])
mouse_symbols = sorted(mouse_symbols)
print(f"[t={time.time()-t0:.0f}s] {len(mouse_symbols)} unique mouse symbols")

# Pass 1: scopes='symbol' precise. Use small batches + retry on 500.
import time as _t
def safe_querymany(syms, scopes):
    all_res = []
    batch = 200
    for i in range(0, len(syms), batch):
        chunk = syms[i:i+batch]
        for attempt in range(3):
            try:
                r = mg.querymany(chunk, scopes=scopes, species='mouse',
                                 fields='symbol,homologene', returnall=False, verbose=False)
                all_res.extend(r)
                break
            except Exception as e:
                print(f"  retry {attempt+1} for batch {i}: {e}")
                _t.sleep(3)
        else:
            print(f"  batch {i} FAILED")
    return all_res

res1 = safe_querymany(mouse_symbols, 'symbol')
hit1 = {r['query']: r for r in res1 if 'notfound' not in r}
miss1 = [r['query'] for r in res1 if 'notfound' in r]
print(f"[t={time.time()-t0:.0f}s] Pass 1 (symbol): hit {len(hit1)}/{len(mouse_symbols)}, miss {len(miss1)}")

# Pass 2: alias + name retry on misses
if miss1:
    res2 = safe_querymany(miss1, 'symbol,alias,name')
    # Take first hit per query (mygene returns multiple if multi-alias)
    seen = set()
    hit2 = {}
    for r in res2:
        if 'notfound' in r or r['query'] in seen: continue
        if r['query'] not in hit2:
            hit2[r['query']] = r
            seen.add(r['query'])
    print(f"[t={time.time()-t0:.0f}s] Pass 2 (alias): rescued {len(hit2)}/{len(miss1)}")
    hit1.update(hit2)

# Extract homologene group + find human entrez
mouse_to_hg = {}      # mouse_sym -> homologene id
mouse_to_human_entrez = {}
human_entrez_set = set()
no_hg = 0
no_human = 0
for q, r in hit1.items():
    hg = r.get('homologene')
    if not isinstance(hg, dict):
        no_hg += 1
        continue
    mouse_to_hg[q] = hg.get('id')
    genes = hg.get('genes', [])
    h = next((g[1] for g in genes if g[0] == 9606), None)
    if h is None:
        no_human += 1
        continue
    mouse_to_human_entrez[q] = h
    human_entrez_set.add(h)

print(f"[t={time.time()-t0:.0f}s] mouse->human_entrez: {len(mouse_to_human_entrez)} mapped; {no_hg} no homologene; {no_human} no human member in group")

# Convert human entrez -> symbol (batch)
print(f"[t={time.time()-t0:.0f}s] Resolving {len(human_entrez_set)} human entrez IDs to symbols...")
def safe_getgenes(ids):
    out = []
    batch = 200
    ids_list = list(ids)
    for i in range(0, len(ids_list), batch):
        chunk = ids_list[i:i+batch]
        for attempt in range(3):
            try:
                r = mg.getgenes(chunk, fields='symbol', species='human')
                out.extend(r)
                break
            except Exception as e:
                print(f"  retry {attempt+1} for batch {i}: {e}")
                time.sleep(3)
    return out
res3 = safe_getgenes(human_entrez_set)
entrez_to_sym = {int(r['_id']): r['symbol'] for r in res3 if 'symbol' in r}
print(f"[t={time.time()-t0:.0f}s] {len(entrez_to_sym)} entrez->symbol resolved")

# Final map
mouse_to_human_sym = {}
for mouse_sym, ent in mouse_to_human_entrez.items():
    if ent in entrez_to_sym:
        mouse_to_human_sym[mouse_sym] = entrez_to_sym[ent]

print(f"\n=== Final mouse->human symbol map ===")
print(f"input mouse symbols: {len(mouse_symbols)}")
print(f"mapped to human symbol: {len(mouse_to_human_sym)} ({len(mouse_to_human_sym)/len(mouse_symbols)*100:.1f}%)")

# Compare with naive uppercase mapping
def upper_match(s):
    return s.upper()

# Compare per-set
import csv as csv2
def get_subset(fname, field):
    s = set()
    with open(fname) as fh:
        for row in csv2.DictReader(fh):
            s.add(row[field])
    return s

train_perts = get_subset('/data/yy_data/Bioreasoning_trackA/train.csv','pert')
test_perts = get_subset('/data/yy_data/Bioreasoning_trackA/test.csv','pert')
train_genes = get_subset('/data/yy_data/Bioreasoning_trackA/train.csv','gene')
test_genes = get_subset('/data/yy_data/Bioreasoning_trackA/test.csv','gene')

for name, syms in [('train_perts', train_perts), ('test_perts', test_perts),
                   ('train_genes', train_genes), ('test_genes', test_genes)]:
    naive = sum(1 for s in syms if upper_match(s) == upper_match(s))  # always true (just count)
    upper_hits = len(syms)  # trivial
    ortho = sum(1 for s in syms if s in mouse_to_human_sym)
    diff = sum(1 for s in syms if s in mouse_to_human_sym and mouse_to_human_sym[s] != upper_match(s))
    print(f"  {name:12s}: n={len(syms):4d}  mygene_ortho={ortho:4d} ({ortho/len(syms)*100:.0f}%)  diff_from_upper={diff}")

# Save
with open('/data/yy_data/Bioreasoning_trackA/mouse_to_human_ortholog.json', 'w') as fh:
    json.dump(mouse_to_human_sym, fh)
print(f"\nSaved to mouse_to_human_ortholog.json. Total time: {time.time()-t0:.0f}s")
