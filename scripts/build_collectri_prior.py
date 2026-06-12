"""Build a mouse signed TF→target prior from the OmniPath REST API.

The OmniPath endpoint aggregates CollecTRI + DoRothEA + TRRUST + several
ChIP-derived sources into a single mouse (organism=10090) interaction
table with consensus directionality (consensus_stimulation /
consensus_inhibition).

For each (TF, target) pair we collapse to a single sign:
  +1  consensus says stimulation only       (activator)
  -1  consensus says inhibition only        (repressor)
   0  both observed OR neither (ambiguous)

We then save to `data/collectri_mouse_signed.json` for use in the runner.

Coverage on the Track-A test set was disappointingly thin:
  - Test perts that ARE TFs in atlas:        7 / 96
  - Test rows with direct (pert, gene) sign: 3 / 1813
  - Test rows where pert is a TF in atlas: 142 / 1813 (~8%)

So the atlas only directly answers 3 rows. The other 139 TF-rows can
optionally use the TF's overall activator/repressor tendency as a weak
prior.
"""
from __future__ import annotations
import csv, json
from collections import defaultdict, Counter
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / 'data/collectri_mouse_signed.json'

OMNIPATH_URL = (
    'https://omnipathdb.org/interactions'
    '?resources=CollecTRI'
    '&organisms=10090'
    '&genesymbols=1'
    '&fields=sources'
    '&format=tsv'
)


def fetch_omnipath() -> list[dict]:
    print(f'GET {OMNIPATH_URL}')
    with urllib.request.urlopen(OMNIPATH_URL, timeout=60) as fh:
        text = fh.read().decode('utf-8')
    rows = list(csv.DictReader(text.splitlines(), delimiter='\t'))
    print(f'  {len(rows)} mouse TF-target interaction rows')
    return rows


def build_lookup(rows):
    lookup = {}
    sign_count = Counter()
    for r in rows:
        src = r['source_genesymbol']
        tgt = r['target_genesymbol']
        cs = r['consensus_stimulation'] == 'True'
        ci = r['consensus_inhibition']  == 'True'
        if cs and not ci:
            sign = +1
        elif ci and not cs:
            sign = -1
        else:
            sign = 0
        sign_count[sign] += 1
        # Keep the strongest non-ambiguous sign if we see duplicates
        key = (src, tgt)
        if key not in lookup or abs(sign) > abs(lookup[key]):
            lookup[key] = sign
    return lookup, sign_count


def main():
    rows = fetch_omnipath()
    lookup, sign_count = build_lookup(rows)

    print(f'\nsign distribution:')
    print(f'  +1 activator: {sign_count[1]:>5}')
    print(f'  -1 repressor: {sign_count[-1]:>5}')
    print(f'   0 ambiguous: {sign_count[0]:>5}')
    print(f'unique (TF, target) pairs: {len(lookup)}')
    print(f'unique TFs: {len(set(k[0] for k in lookup))}')
    print(f'unique targets: {len(set(k[1] for k in lookup))}')

    # Coverage against test set
    test_rows = list(csv.DictReader(open(ROOT / 'data/test.csv')))
    perts = set(r['pert'] for r in test_rows)
    genes = set(r['gene'] for r in test_rows)
    tfs_in_atlas = perts & set(k[0] for k in lookup)
    targets_in_atlas = genes & set(k[1] for k in lookup)
    direct_pairs = sum(1 for r in test_rows if (r['pert'], r['gene']) in lookup)
    direct_signed = sum(1 for r in test_rows
                        if lookup.get((r['pert'], r['gene']), 0) != 0)
    n_rows_pert_is_tf = sum(1 for r in test_rows if r['pert'] in tfs_in_atlas)

    print(f'\n=== Test set coverage ({len(test_rows)} rows) ===')
    print(f'  perts that ARE TFs in atlas:        {len(tfs_in_atlas):>4} / {len(perts)}')
    print(f'  genes as targets in atlas:          {len(targets_in_atlas):>4} / {len(genes)}')
    print(f'  rows with direct (pert, gene) pair: {direct_pairs:>4}')
    print(f'  rows with direct + signed:          {direct_signed:>4}')
    print(f'  rows where pert is TF in atlas:     {n_rows_pert_is_tf:>4}')

    # TF-level summary for each test pert that is a TF in atlas
    print(f'\n=== Per-TF target tendency (the {len(tfs_in_atlas)} TFs that are test perts) ===')
    print(f'  {"TF":<10s} {"n_targets":>10s}  {"n_act":>6s}  {"n_rep":>6s}  {"act_ratio":>10s}  {"n_test_rows":>11s}')
    for tf in sorted(tfs_in_atlas):
        targets = [(k[1], lookup[k]) for k in lookup if k[0] == tf]
        n_act = sum(1 for _, s in targets if s == 1)
        n_rep = sum(1 for _, s in targets if s == -1)
        n_total = len(targets)
        act_ratio = n_act / (n_act + n_rep) if (n_act + n_rep) > 0 else 0.5
        n_test_rows = sum(1 for r in test_rows if r['pert'] == tf)
        print(f'  {tf:<10s} {n_total:>10d}  {n_act:>6d}  {n_rep:>6d}  {act_ratio:>10.2f}  {n_test_rows:>11d}')

    # Save
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        'meta': {
            'source': OMNIPATH_URL,
            'description': 'Mouse signed TF -> target consensus from CollecTRI + DoRothEA + TRRUST + ChIP via OmniPath',
            'organism': 'mouse (taxid 10090)',
            'n_pairs': len(lookup),
            'n_signed': sign_count[1] + sign_count[-1],
            'n_activator': sign_count[1],
            'n_repressor': sign_count[-1],
            'test_coverage': {
                'tfs_in_atlas': len(tfs_in_atlas),
                'tfs_in_atlas_list': sorted(tfs_in_atlas),
                'direct_pairs': direct_pairs,
                'direct_signed': direct_signed,
                'rows_pert_is_tf': n_rows_pert_is_tf,
            },
        },
        'pairs': {f'{k[0]}|{k[1]}': v for k, v in lookup.items()},
    }, indent=1))
    print(f'\nwrote {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
