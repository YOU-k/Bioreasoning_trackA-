"""Sanity tests for prompt_builder_v2 (attempt 04). Runs in <5s."""
from pipeline.prompt_builder_v2 import (
    build_de_prompt, build_dir_prompt, estimate_tokens,
    CHOICES_DE, CHOICES_DIR,
)
from pipeline.retrieve_examples import ExampleRetriever
from pipeline.gene_desc import GeneDesc


def test_de_prompt_structure():
    p = build_de_prompt('Aars', 'Atf4')
    assert 'P_DE:' in p
    assert 'P_up_given_DE:' not in p, "DE prompt must not ask for P_up"
    assert 'BMDM' in p
    assert 'CRISPRi' in p
    assert 'Aars' in p and 'Atf4' in p
    # Cross-species reference always present (block exists, may be 'not available')
    assert 'Replogle' in p
    # Retrieval block present
    assert 'similar' in p.lower() and 'Example' in p
    # Randomized-label fingerprint
    assert any(c in p for c in CHOICES_DE)


def test_dir_prompt_structure():
    p = build_dir_prompt('Aars', 'Atf4')
    assert 'P_up_given_DE:' in p
    assert 'P_DE:' not in p, "DIR prompt must not ask for P_DE"
    assert 'BMDM' in p
    assert 'Aars' in p and 'Atf4' in p
    # DIR also includes Replogle ref block (we kept the cross-species DIR reference
    # but the model is instructed to ignore it for macrophage-specific programs)
    assert 'Replogle' in p
    assert any(c in p for c in CHOICES_DIR)


def test_budget_reasonable():
    for pert, gene in [('Actb', 'Atf4'), ('Stat1', 'Irf1'),
                       ('Aars', '1500011B03Rik'), ('Cebpb', 'Acsl1')]:
        for builder in (build_de_prompt, build_dir_prompt):
            p = builder(pert, gene)
            tok = estimate_tokens(p)
            # Generous budget; VCWorld prompts are larger than v1
            assert tok < 4096, f"{builder.__name__}({pert},{gene}): {tok} tokens > 4096"


def test_exclude_query_filters_self():
    """With exclude_query=True, retrieved exemplars must not share pert or gene
    with the query (simulates double-disjoint test conditions on a train probe)."""
    r = ExampleRetriever()
    pert, gene = 'Stat1', 'Ifit1'  # both likely in train; not committing to that
    exs = r.retrieve(pert, gene, budget=10, exclude_query=True, seed=42)
    for p2, g2, _ in exs:
        assert p2 != pert, f"retrieved pair {(p2, g2)} shares pert with query"
        assert g2 != gene, f"retrieved pair {(p2, g2)} shares gene with query"


def test_gene_desc_fallback():
    """For an unknown gene, description should fall back to symbol-only and
    not raise."""
    gd = GeneDesc()
    out = gd.get('ThisGeneDoesNotExist_xyz')
    assert isinstance(out, str) and len(out) > 0


if __name__ == '__main__':
    test_de_prompt_structure()
    test_dir_prompt_structure()
    test_budget_reasonable()
    test_exclude_query_filters_self()
    test_gene_desc_fallback()
    print('test_prompt_v2: 5/5 passed')
