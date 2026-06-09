"""Sanity tests for ExampleRetriever.retrieve_analog_contrast (attempt 05).

Paper §3.4.2: retrieval splits train pairs into analog (l=1) + contrast (l=0)
pools by task, ranks each by KG similarity, returns top-k from each.
"""
from pipeline.retrieve_examples import ExampleRetriever


def test_de_pools_split_correctly():
    r = ExampleRetriever()
    analog, contrast = r.retrieve_analog_contrast(
        'Aars', 'Atf4', task='de', k_a=5, k_c=5, exclude_query=True, seed=42,
    )
    # DE analog = label in {up, down}
    for p, g, lbl in analog:
        assert lbl in ('up', 'down'), f"DE analog has wrong label: {(p,g,lbl)}"
    # DE contrast = label == none
    for p, g, lbl in contrast:
        assert lbl == 'none', f"DE contrast has wrong label: {(p,g,lbl)}"


def test_dir_pools_exclude_none():
    r = ExampleRetriever()
    analog, contrast = r.retrieve_analog_contrast(
        'Aars', 'Atf4', task='dir', k_a=5, k_c=5, exclude_query=True, seed=42,
    )
    for p, g, lbl in analog:
        assert lbl == 'up', f"DIR analog has wrong label: {(p,g,lbl)}"
    for p, g, lbl in contrast:
        assert lbl == 'down', f"DIR contrast has wrong label: {(p,g,lbl)}"


def test_exclude_query_drops_self():
    r = ExampleRetriever()
    pert, gene = 'Stat1', 'Ifit1'
    analog, contrast = r.retrieve_analog_contrast(
        pert, gene, task='de', k_a=5, k_c=5, exclude_query=True, seed=42,
    )
    for p, g, _ in analog + contrast:
        assert p != pert and g != gene, f"query leak: {(p,g)}"


def test_budget_respected():
    r = ExampleRetriever()
    analog, contrast = r.retrieve_analog_contrast(
        'Aars', 'Atf4', task='de', k_a=3, k_c=4, exclude_query=True, seed=42,
    )
    assert len(analog) <= 3
    assert len(contrast) <= 4


def test_format_analog_contrast_renders_real_labels():
    """The format function must show "Yes/No" for DE and "Increase/Decrease"
    for DIR based on real labels (not random)."""
    analog = [('Qars', 'Trib3', 'up'), ('Sars', 'Ddit3', 'up')]
    contrast = [('Hars', 'Hspa5', 'none')]
    out_de = ExampleRetriever.format_block_analog_contrast(
        analog, contrast, task='de', seed=42)
    assert 'Qars' in out_de and 'Hars' in out_de
    assert 'Yes' in out_de and 'No' in out_de
    # DIR rendering of an up/down split
    analog2 = [('Qars', 'Trib3', 'up')]
    contrast2 = [('Sars', 'Trib3', 'down')]
    out_dir = ExampleRetriever.format_block_analog_contrast(
        analog2, contrast2, task='dir', seed=42)
    assert 'Increase' in out_dir and 'Decrease' in out_dir


def test_single_anchor_fallback_recovers_examples():
    r = ExampleRetriever()
    # In the shipped test split, this pair has pert-side KG support but
    # little/no gene-side support. Retrieval should still surface examples.
    analog, contrast = r.retrieve_analog_contrast(
        'Stat2', 'Mx1', task='de', k_a=5, k_c=5, exclude_query=False, seed=42,
    )
    assert len(analog) + len(contrast) > 0


def test_gene_only_fallback_recovers_examples():
    r = ExampleRetriever()
    # This pair has gene-side ER/proteostasis neighbors but no pert-side
    # KG neighborhood in the filtered index. We should still get examples.
    analog, contrast = r.retrieve_analog_contrast(
        'Slc35b1', 'Pdia6', task='de', k_a=5, k_c=5, exclude_query=False, seed=42,
    )
    assert len(analog) + len(contrast) > 0


if __name__ == '__main__':
    test_de_pools_split_correctly()
    test_dir_pools_exclude_none()
    test_exclude_query_drops_self()
    test_budget_respected()
    test_format_analog_contrast_renders_real_labels()
    test_single_anchor_fallback_recovers_examples()
    test_gene_only_fallback_recovers_examples()
    print('test_retrieve_analog_contrast: 7/7 passed')
