"""Sanity tests for ReplogPrior. Runs in <5s."""
from pipeline.replogle_prior import ReplogPrior


def test_loads_and_has_entries():
    p = ReplogPrior()
    assert len(p.de) > 100, "Should have hundreds of perts mapped"
    assert len(p.m2h) > 1000, "Should have ortholog map with >1000 entries"


def test_known_essential_pert():
    p = ReplogPrior()
    # Actb (housekeeping) should be in K562_essential
    assert p.has_pert('Actb')
    tops = p.get_top_responders('Actb', n=5)
    assert len(tops['up']) == 5 and len(tops['down']) == 5
    # logFC values should be sorted descending for up, ascending for down
    up_lfcs = [t['logfc'] for t in tops['up']]
    dn_lfcs = [t['logfc'] for t in tops['down']]
    assert up_lfcs == sorted(up_lfcs, reverse=True)
    assert dn_lfcs == sorted(dn_lfcs)


def test_uppercase_rescue():
    p = ReplogPrior()
    # Aars (mouse) -> AARS (Replogle's older symbol, rescued by uppercase fallback)
    assert p.has_pert('Aars'), "Aars should be rescued via uppercase fallback"


def test_tier_none_for_bmdm_tf():
    p = ReplogPrior()
    # STAT1, CEBPB, NFKB1 are TFs — not in Replogle K562/RPE1 essential
    assert p.tier('Stat1', 'Irf1') == 'none'
    assert p.tier('Cebpb', 'Acsl1') == 'none'


if __name__ == '__main__':
    test_loads_and_has_entries()
    test_known_essential_pert()
    test_uppercase_rescue()
    test_tier_none_for_bmdm_tf()
    print('test_prior: 4/4 passed')
