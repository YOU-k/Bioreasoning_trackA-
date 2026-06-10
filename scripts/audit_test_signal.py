"""Step 3: how much actual signal does each test row have to reason from?

For each of 1813 test rows, check the four signal sources that our pipeline
uses:
  1. Replogle ortholog scalar: does pert have a human ortholog in Replogle?
                               does (pert, gene) have a direct logFC?
  2. KG pathway / STRING neighbors for the pert
  3. KG pathway / STRING neighbors for the gene
  4. NCBI/MGI description longer than the symbol itself (gene_desc.json)

Output per-row signal flags + summary table by combination. Sets the
realistic ceiling for any LLM-based method on this test set.
"""
from __future__ import annotations
import csv, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.replogle_prior import ReplogPrior
from pipeline.kg_retrieval import KGRetrieval
from pipeline.gene_desc import default as gene_desc_default


def has_meaningful_desc(symbol: str, desc_obj, threshold: int = 80) -> bool:
    """A description is 'meaningful' if it's substantially longer than the
    symbol itself (i.e., has actual functional text, not just the gene name)."""
    txt = desc_obj.get(symbol)
    if not txt:
        return False
    # Strip the symbol from the front, count remaining chars
    rest = txt.replace(symbol, '').strip()
    return len(rest) >= threshold


def main():
    prior = ReplogPrior()
    kg = KGRetrieval()
    desc = gene_desc_default()

    test_rows = list(csv.DictReader(open(ROOT / 'data/test.csv')))
    print(f'Auditing {len(test_rows)} test rows')
    print()

    flags = []
    for r in test_rows:
        pert, gene = r['pert'], r['gene']

        # Replogle: tier returns 'full' (both pert+gene have orthologs in Replogle),
        # 'pert_only' (only pert), or 'none'.
        replogle_tier = prior.tier(pert, gene)
        has_replogle_pert = replogle_tier in ('full', 'pert_only')
        has_replogle_full = replogle_tier == 'full'

        # KG: any STRING neighbors / Reactome pathway membership?
        pert_paths = kg.get_pathways(pert, top_n=3)
        gene_paths = kg.get_pathways(gene, top_n=3)
        pert_adj = bool(kg.adj.get(pert))
        gene_adj = bool(kg.adj.get(gene))
        has_kg_pert = bool(pert_paths) or pert_adj
        has_kg_gene = bool(gene_paths) or gene_adj

        # Description
        has_desc_pert = has_meaningful_desc(pert, desc)
        has_desc_gene = has_meaningful_desc(gene, desc)

        flags.append({
            'id': r['id'],
            'pert': pert, 'gene': gene,
            'replogle_pert': has_replogle_pert,
            'replogle_full': has_replogle_full,
            'kg_pert': has_kg_pert,
            'kg_gene': has_kg_gene,
            'desc_pert': has_desc_pert,
            'desc_gene': has_desc_gene,
        })

    n = len(flags)
    print('=== Per-source coverage ===')
    for key in ['replogle_pert', 'replogle_full', 'kg_pert', 'kg_gene',
                'desc_pert', 'desc_gene']:
        c = sum(1 for r in flags if r[key])
        print(f'  {key:<18s}  {c:>5}/{n}  ({100*c/n:5.1f}%)')
    print()

    # Tier classification: how much signal does each row have?
    # Tier 0 (rich): both pert AND gene have KG + desc + Replogle full
    # Tier 1 (mid):  pert has solid signal, gene has at least desc OR kg
    # Tier 2 (poor): neither has much
    print('=== Composite info tiers ===')
    tier_counts = Counter()
    for r in flags:
        pert_signals = sum([r['replogle_pert'], r['kg_pert'], r['desc_pert']])
        gene_signals = sum([r['kg_gene'], r['desc_gene']])
        if r['replogle_full'] and pert_signals >= 2 and gene_signals >= 1:
            tier = 'Tier 0 (rich: replogle-full + KG/desc both sides)'
        elif pert_signals >= 2 and gene_signals >= 1:
            tier = 'Tier 1 (mid: kg/desc both sides, no replogle direct)'
        elif pert_signals >= 1 and gene_signals >= 1:
            tier = 'Tier 2 (thin: at least 1 signal per side)'
        elif pert_signals >= 1 or gene_signals >= 1:
            tier = 'Tier 3 (one-sided)'
        else:
            tier = 'Tier 4 (no signal at all)'
        tier_counts[tier] += 1

    for tier in sorted(tier_counts):
        c = tier_counts[tier]
        print(f'  {tier:<55s}  {c:>5}/{n}  ({100*c/n:5.1f}%)')
    print()

    # Riken-ID flagging (proxy for obscure mouse genes the LLM probably doesn't know)
    riken_genes = sum(1 for r in flags
                      if any(r['gene'].startswith(p) for p in ('Gm', 'Riken', 'A', 'B', 'C'))
                      and r['gene'].endswith('Rik'))
    riken_genes_strict = sum(1 for r in flags if r['gene'].endswith('Rik'))
    print(f'=== Obscure-gene flags ===')
    print(f'  gene ends in "Rik" (Riken ID):  {riken_genes_strict}/{n}  ({100*riken_genes_strict/n:.1f}%)')
    # Other obscure patterns
    gm = sum(1 for r in flags if r['gene'].startswith('Gm') and r['gene'][2:].isdigit())
    print(f'  gene starts "Gm<digits>" (predicted):  {gm}/{n}  ({100*gm/n:.1f}%)')

    # Save the raw flags
    out_path = ROOT / 'attempts/10_test_signal_audit/coverage.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        'n_test': n,
        'per_source': {k: sum(1 for r in flags if r[k]) for k in
                       ['replogle_pert', 'replogle_full', 'kg_pert', 'kg_gene',
                        'desc_pert', 'desc_gene']},
        'tier_counts': dict(tier_counts),
        'flags_per_row': flags,
    }, indent=2))
    print()
    print(f'wrote {out_path}')

    # Verdict on realistic ceiling
    print()
    print('=== Realistic ceiling estimate ===')
    rich_n = tier_counts.get('Tier 0 (rich: replogle-full + KG/desc both sides)', 0)
    mid_n  = tier_counts.get('Tier 1 (mid: kg/desc both sides, no replogle direct)', 0)
    thin_n = tier_counts.get('Tier 2 (thin: at least 1 signal per side)', 0)
    no_signal_n = tier_counts.get('Tier 4 (no signal at all)', 0) + tier_counts.get('Tier 3 (one-sided)', 0)

    # Optimistic per-tier AUROC guess:
    #   rich: 0.65 (eval60 number was leakage-inflated; assume rich rows still get good signal)
    #   mid:  0.58
    #   thin: 0.52
    #   no_signal: 0.50 (random/prior)
    est = (rich_n * 0.65 + mid_n * 0.58 + thin_n * 0.52 + no_signal_n * 0.50) / n
    print(f'  Rich     ({rich_n:>4}, est AUROC 0.65 on this slice)')
    print(f'  Mid      ({mid_n:>4}, est 0.58)')
    print(f'  Thin     ({thin_n:>4}, est 0.52)')
    print(f'  No signl ({no_signal_n:>4}, est 0.50)')
    print(f'  Weighted estimate of realistic Combined ceiling: ~{est:.3f}')
    print(f'  (These per-tier numbers are guesses — see actual probe60 results.)')


if __name__ == '__main__':
    main()
