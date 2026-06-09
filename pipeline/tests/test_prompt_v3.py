"""Sanity tests for prompt_builder_v3 (attempt 06, single-call Track A)."""
from pipeline.prompt_builder_v3 import build_track_a_prompt, estimate_tokens
from pipeline.output_parser import parse
from pipeline.runner import fuse_q_r_logit


def test_single_call_prompt_emits_both_keys():
    p = build_track_a_prompt('Aars', 'Atf4')
    assert 'P_DE:' in p
    assert 'P_up_given_DE:' in p
    assert 'BMDM' in p and 'CRISPRi' in p


def test_single_call_prompt_has_direction_prior_and_guard():
    p = build_track_a_prompt('Aars', 'Atf4')
    # Direction prior 62 must be in the rules
    assert '62' in p
    assert '2.2' in p, "should cite the 2.2:1 train up:down ratio"
    # Anti-storytelling guard
    assert 'Plausibility' in p or 'plausibility' in p
    # Decoupling rule: high direction confidence ≠ high P_DE
    assert 'independent' in p or 'NOT imply' in p


def test_single_call_prompt_token_budget():
    """Combined prompt must still fit Track A's 4096 token budget."""
    for pert, gene in [('Actb', 'Atf4'), ('Stat1', 'Irf1'),
                       ('Aars', '1500011B03Rik'), ('Cebpb', 'Acsl1')]:
        p = build_track_a_prompt(pert, gene)
        tok = estimate_tokens(p)
        assert tok < 4096, f"{(pert, gene)} prompt {tok} tokens > 4096 budget"


def test_parser_extracts_both_from_combined_output():
    sample = (
        "A1 — Mechanism: aaRS\n"
        "A2 — BMDM relevance: ISR\n"
        "A3 — Cascade: KD Aars -> GCN2 -> ATF4\n"
        "A4 — DE call: high\n"
        "B1 — Direction logic: ISR up\n"
        "B2 — Direction call: up\n"
        "\n"
        "P_DE: 85\n"
        "P_up_given_DE: 95\n"
    )
    p = parse(sample)
    assert p.parse_status == 'ok'
    assert abs(p.p_de - 0.85) < 1e-6
    assert abs(p.p_up_given_de - 0.95) < 1e-6
    # p_up = q*r = 0.85 * 0.95 = 0.8075
    assert abs(p.p_up - 0.8075) < 1e-6


def test_logit_fusion_extreme_seed_does_not_dominate_other_head():
    """Three seeds where ONE is extreme on r but moderate on q. After logit-
    fusion, the q channel should not be pulled by the extreme r value, and
    vice versa. This is exactly the failure mode plain p_up averaging has."""
    q_seeds = [0.4, 0.5, 0.45]
    r_seeds = [0.6, 0.62, 0.98]  # one extreme on direction
    q, r, p_up, p_down = fuse_q_r_logit(q_seeds, r_seeds)
    # q should be near the seed mean (~0.45) regardless of r outlier
    assert 0.35 < q < 0.55
    # r should be pulled up but not collapsed
    assert 0.65 < r < 0.95
    # p_up * 1 + p_down * 1 == q (probability mass conservation)
    assert abs((p_up + p_down) - q) < 1e-6


def test_logit_fusion_consistency_with_q_r_definition():
    q_seeds = [0.5, 0.5, 0.5]
    r_seeds = [0.62, 0.62, 0.62]
    q, r, p_up, p_down = fuse_q_r_logit(q_seeds, r_seeds)
    assert abs(q - 0.5) < 1e-3
    assert abs(r - 0.62) < 1e-3
    assert abs(p_up - 0.31) < 1e-3
    assert abs(p_down - 0.19) < 1e-3


if __name__ == '__main__':
    test_single_call_prompt_emits_both_keys()
    test_single_call_prompt_has_direction_prior_and_guard()
    test_single_call_prompt_token_budget()
    test_parser_extracts_both_from_combined_output()
    test_logit_fusion_extreme_seed_does_not_dominate_other_head()
    test_logit_fusion_consistency_with_q_r_definition()
    print('test_prompt_v3: 6/6 passed')
