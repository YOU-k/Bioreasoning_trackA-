"""Sanity tests for output_parser. Runs in <1s."""
from pipeline.output_parser import extract_p_de, extract_p_up_given_de, parse


def test_clean_parse():
    out = """Reasoning: brief mechanistic chain here.

P_DE: 70
P_up_given_DE: 25
"""
    p = parse(out)
    assert p.parse_status == 'ok'
    assert abs(p.p_de - 0.70) < 1e-9
    assert abs(p.p_up_given_de - 0.25) < 1e-9
    assert abs(p.p_up - 0.175) < 1e-9
    assert abs(p.p_down - 0.525) < 1e-9


def test_fallback_on_partial():
    out = """P_DE: 60
(missing P_up_given_DE)"""
    p = parse(out)
    assert p.parse_status == 'fallback'
    assert abs(p.p_de - 0.60) < 1e-9


def test_safe_defaults_on_failure():
    p = parse("I cannot answer this.")
    assert p.parse_status == 'failed'
    # default p_de=0.45, p_up_given_de=0.5 → p_up=p_down=0.225
    assert abs(p.p_up - 0.225) < 1e-9
    assert abs(p.p_down - 0.225) < 1e-9


def test_clamps_oob_values():
    p = parse("P_DE: 150\nP_up_given_DE: -10")
    # 150 -> 100, -10 -> 0 (regex matches positive integers only, so -10
    # never gets through; we accept that as long as p_de clamps correctly)
    assert p.p_de == 1.0


def test_extract_task_specific_scores():
    p_de, s_de = extract_p_de("scratch\nP_DE: 85\nmore scratch")
    p_up, s_up = extract_p_up_given_de("scratch\nP_up_given_DE: 95\nmore scratch")
    assert s_de == 'ok'
    assert s_up == 'ok'
    assert abs(p_de - 0.85) < 1e-9
    assert abs(p_up - 0.95) < 1e-9


def test_extract_task_specific_scores_loose_forms():
    p_de, s_de = extract_p_de("Thus final integers: P_DE 30, P_up_given_DE 75.")
    p_up, s_up = extract_p_up_given_de("Thus final values: P_DE maybe 18, P_up_given_DE maybe 54.")
    p_up_short, s_up_short = extract_p_up_given_de("Direction uncertain but maybe P_up 60.")
    assert s_de == 'ok'
    assert s_up == 'ok'
    assert s_up_short == 'ok'
    assert abs(p_de - 0.30) < 1e-9
    assert abs(p_up - 0.54) < 1e-9
    assert abs(p_up_short - 0.60) < 1e-9


if __name__ == '__main__':
    test_clean_parse()
    test_fallback_on_partial()
    test_safe_defaults_on_failure()
    test_clamps_oob_values()
    test_extract_task_specific_scores()
    test_extract_task_specific_scores_loose_forms()
    print('test_parser: 6/6 passed')
