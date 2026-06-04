"""Sanity tests for kg_retrieval + celltype_guide."""
from pipeline.kg_retrieval import KGRetrieval
from pipeline.celltype_guide import tag_gene, per_query_tag_block, rules_block


def test_loads():
    kg = KGRetrieval()
    s = kg.stats()
    assert s['n_genes_with_pathways'] > 1000
    assert s['n_high_conf_edges'] > 50000
    assert s['n_nodes_in_graph'] > 5000


def test_known_direct_ppi():
    kg = KGRetrieval()
    # Stat1 and Irf1 are direct neighbors at STRING >=700
    p = kg.shortest_path('Stat1', 'Irf1', max_depth=3)
    assert p is not None
    assert len(p) == 2 and p[0] == 'Stat1' and p[1] == 'Irf1'


def test_two_hop_via_known_intermediate():
    kg = KGRetrieval()
    # Cebpb -> Acsl1 should route through Pparg (known TF -> target)
    p = kg.shortest_path('Cebpb', 'Acsl1', max_depth=3)
    assert p is not None
    assert p[0] == 'Cebpb' and p[-1] == 'Acsl1'
    assert 'Pparg' in p, f'expected Pparg in path, got {p}'


def test_no_path_returns_none():
    kg = KGRetrieval()
    p = kg.shortest_path('Pak2', 'Mapkbp1', max_depth=3)
    assert p is None


def test_category_tagging():
    kg = KGRetrieval()
    cases = {
        'Tnf':   'IMMUNE_EFFECTOR',
        'Cd14':  'TLR_NLR',
        'Nfkb1': 'TLR_NLR',
        'Rps3':  'TRANSLATION',
        'Cdk1':  'CELL_CYCLE',
        'Acaa2': 'METABOLISM_CORE',
    }
    for gene, expect in cases.items():
        got = tag_gene(kg.pathways.get(gene, []))
        assert got == expect, f'{gene}: expected {expect}, got {got}'


def test_untagged_genes_return_none():
    kg = KGRetrieval()
    # Atf4 / Stat1 have no Reactome mouse coverage — should be UNTAGGED
    for g in ['Atf4', 'Stat1']:
        assert tag_gene(kg.pathways.get(g, [])) is None


def test_per_query_block_advice_branches():
    kg = KGRetrieval()
    # Both transfer-friendly (Cdk1=CELL_CYCLE, Cdk2=...): trust Replogle
    pp = kg.get_pathways('Cdk1', top_n=20)
    gp = kg.get_pathways('Acaa2', top_n=20)
    block = per_query_tag_block('Cdk1', 'Acaa2', pp, gp)
    assert 'BOTH transfer-friendly' in block

    # One context-dependent (Tnf=IMMUNE_EFFECTOR): warn
    block = per_query_tag_block('Nfkb1', 'Tnf',
                                kg.get_pathways('Nfkb1', top_n=20),
                                kg.get_pathways('Tnf', top_n=20))
    assert 'context-dependent' in block.lower()


def test_rules_block_static():
    # Same call twice produces identical text
    assert rules_block() == rules_block()
    assert 'transfer-friendly' in rules_block().lower()


if __name__ == '__main__':
    test_loads()
    test_known_direct_ppi()
    test_two_hop_via_known_intermediate()
    test_no_path_returns_none()
    test_category_tagging()
    test_untagged_genes_return_none()
    test_per_query_block_advice_branches()
    test_rules_block_static()
    print('test_kg: 8/8 passed')
