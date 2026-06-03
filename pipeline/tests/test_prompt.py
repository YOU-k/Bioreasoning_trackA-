"""Sanity tests for prompt_builder. Runs in <5s."""
from pipeline.prompt_builder import build_prompt, estimate_tokens
from pipeline.replogle_prior import ReplogPrior


def test_budget_under_4096():
    prior = ReplogPrior()
    for pert, gene in [('Actb', 'Atf4'), ('Stat1', 'Irf1'),
                       ('Aars', '1500011B03Rik'), ('Cebpb', 'Acsl1')]:
        p = build_prompt(pert, gene, prior)
        tok = estimate_tokens(p)
        assert tok < 4096, f"{pert}_{gene}: {tok} tokens > 4096 budget"


def test_required_structure():
    prior = ReplogPrior()
    p = build_prompt('Actb', 'Atf4', prior)
    # Output schema markers
    assert 'P_DE:' in p
    assert 'P_up_given_DE:' in p
    # Disconfirming step
    assert 'disconfirm' in p.lower()
    # Biological context
    assert 'BMDM' in p
    assert 'CRISPRi' in p
    # Replogle prior block when full tier
    assert 'Replogle' in p


def test_no_replogle_block_when_none_tier():
    prior = ReplogPrior()
    p = build_prompt('Stat1', 'Irf1', prior)
    # Should say "Not available" for cross-species prior
    assert 'Not available' in p


if __name__ == '__main__':
    test_budget_under_4096()
    test_required_structure()
    test_no_replogle_block_when_none_tier()
    print('test_prompt: 3/3 passed')
