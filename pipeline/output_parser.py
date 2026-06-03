"""Parse LLM outputs from Track A prompts: extract P_DE and P_up_given_DE,
fold them into p_up / p_down for the submission."""
from __future__ import annotations
import re
from dataclasses import dataclass

# Allow either "P_DE: 50", "P_DE = 50", with optional leading **, etc.
_RE_PDE = re.compile(r'P_?DE\s*[:=]\s*([0-9]{1,3})', re.IGNORECASE)
_RE_PUP = re.compile(r'P_?up_?given_?DE\s*[:=]\s*([0-9]{1,3})', re.IGNORECASE)
_RE_REASONING_BLOCK = re.compile(r'Reasoning\s*:(.+?)(?=P_?DE\s*[:=]|$)', re.IGNORECASE | re.DOTALL)


@dataclass
class ParsedOutput:
    p_de: float          # in [0, 1]
    p_up_given_de: float # in [0, 1]
    reasoning: str       # the reasoning trace text
    raw: str             # full raw output
    parse_status: str    # 'ok' | 'fallback' | 'failed'

    @property
    def p_up(self) -> float:
        return self.p_de * self.p_up_given_de

    @property
    def p_down(self) -> float:
        return self.p_de * (1.0 - self.p_up_given_de)


def parse(raw_output: str, default_pde: float = 0.45, default_pup: float = 0.5) -> ParsedOutput:
    """Parse a single LLM output. If parsing fails, return prior-style defaults.

    Defaults are chosen to be conservative:
      - default_pde = 0.45 (slightly below the 0.55 prior of `none`)
      - default_pup = 0.5  (equal probability up/down conditional on DE)
    These give p_up = 0.225, p_down = 0.225 → AUROC contribution near 0.5.
    """
    raw = str(raw_output or "")

    m_de = _RE_PDE.search(raw)
    m_up = _RE_PUP.search(raw)
    m_reason = _RE_REASONING_BLOCK.search(raw)

    if m_de and m_up:
        pde = max(0, min(100, int(m_de.group(1)))) / 100.0
        pup = max(0, min(100, int(m_up.group(1)))) / 100.0
        status = 'ok'
    elif m_de or m_up:
        pde = (max(0, min(100, int(m_de.group(1)))) / 100.0) if m_de else default_pde
        pup = (max(0, min(100, int(m_up.group(1)))) / 100.0) if m_up else default_pup
        status = 'fallback'
    else:
        pde = default_pde
        pup = default_pup
        status = 'failed'

    reasoning = m_reason.group(1).strip() if m_reason else raw.strip()[:2000]  # cap

    return ParsedOutput(
        p_de=pde, p_up_given_de=pup,
        reasoning=reasoning, raw=raw, parse_status=status
    )
