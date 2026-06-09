"""Track-A compliant single-call prompt builder (attempt 06).

Produces ONE prompt per (pert, gene) query that elicits BOTH integers in
one LLM response:

    P_DE: <0-100>
    P_up_given_DE: <0-100>

The runner then folds:
    p_up   = P_DE/100 * P_up_given_DE/100
    p_down = P_DE/100 * (1 - P_up_given_DE/100)

Three deliberate additions over attempt 05:

1. Direction prior — when direction evidence is weak, default to ~62 rather
   than 50. Train DE distribution is up:down ≈ 2.2:1 (≈ 0.69 up).
2. Anti-storytelling guard — explicit rule that plausibility ≠ prediction,
   so the absence of pert-specific evidence is itself evidence FOR `none`.
3. Decoupling rule — high direction confidence must NOT inflate P_DE; the
   two integers measure different things.

Retrieval is unchanged from attempt 05: paper §3.4.2 analog + contrast pools
with real labels (k_a=5 + k_c=5).
"""
from __future__ import annotations
from typing import Optional
from .bmdm_context import bmdm_block
from .gene_desc import GeneDesc, default as gene_desc_default
from .retrieve_examples import ExampleRetriever
from .kg_retrieval import KGRetrieval
from .replogle_prior import ReplogPrior


_HEADER = """You are a biological-reasoning engine for mouse bone-marrow-derived macrophages (BMDM) under CRISPRi perturbation.

Task: For CRISPRi knockdown of `{pert}` and readout gene `{gene}` in mouse BMDM, emit TWO calibrated integers:

  P_DE          = P(target `{gene}` is differentially expressed) × 100
                  (DE = FDR<5% AND |shrunken log2 fold-change| ≥ log2(1.5) ≈ 0.585, within 24-72h scRNA-seq pseudobulk)
  P_up_given_DE = P(direction is UP | DE happens) × 100

These are DIFFERENT quantities. High direction confidence does NOT imply high P_DE: "if DE, surely up" only justifies a high P_up_given_DE; P_DE depends on whether DE crosses the cutoff at all."""


_RULES = """Decision rules (read these BEFORE reasoning):

R1. Plausibility ≠ prediction. A mechanism that "could plausibly cause DE" is NOT evidence of DE. Most pairs are `none` because they failed the magnitude/FDR cutoff, not because no mechanism exists.

R2. Absence of pert-specific evidence is evidence FOR `none`. If the analogue cases below are weak/distant and the cascade is indirect, lean P_DE toward 15-25, not toward 50.

R3. Match the BMDM context. Genes in silent BMDM programs (cell cycle, adaptive immunity, neuronal/epithelial lineage) usually stay silent under KD of upstream regulators. Genes in actively expressed BMDM programs (TLR, NF-κB, ISR, IFN, ER, ribosome) are easier to perturb.

R4. Direction prior. In the train DE set, perturbations push targets UP about 2.2× more often than DOWN (train up:down ≈ 0.69 : 0.31). When direction evidence is genuinely weak, default P_up_given_DE ≈ 62, not 50. Override with signed-pathway logic if available (KD of an activator → DOWN; KD of a repressor / stress trigger → UP).

R5. Replogle direction transfers for cell-autonomous programs (translation, ISR, proteostasis, chromatin). It is UNRELIABLE for macrophage-specific programs (TLR/NLR, NF-κB, IFN-I, MHC-II) — use BMDM context instead.

R6. The two integers are independent. Estimate P_DE first using R1-R3 and R5 (DE-magnitude logic), then estimate P_up_given_DE using R4 and signed-pathway logic. Do not let one anchor the other."""


_PROTOCOL = """Reasoning protocol (≤ 2 lines each, terse):

Step A1 — Mechanism class of `{pert}`: (TF / kinase / chaperone / aminoacyl-tRNA synthetase / ER-UPR / IFN / chromatin / ribosome / ...). Which analogue cases below are closest?
Step A2 — BMDM relevance of `{gene}`: which BMDM program (expressed / silent / inducible)? Does that program normally respond to perturbations of `{pert}`'s class?
Step A3 — Cascade: trace KD `{pert}` → pathway / TF / stress program → `{gene}`. Note path length and confidence.
Step A4 — DE call (P_DE): apply R1-R3, R5. Compare to analogue vs contrast cases. Output integer 0-100.

Step B1 — Direction logic: is `{pert}` (or its immediate downstream node) an ACTIVATOR or REPRESSOR of programs that include `{gene}`? Apply: KD of activator → DOWN; KD of repressor → UP; KD that triggers ISR/UPR/inflammation → stress-response targets UP.
Step B2 — Direction call (P_up_given_DE): apply R4-R5 and signed-pathway logic. Output integer 0-100; default ≈ 62 when evidence is weak."""


_OUTPUT_FORMAT = """OUTPUT FORMAT (STRICT — every step on one short line; final two lines MUST match exactly):

A1 — Mechanism & analogues: <1 line>
A2 — BMDM relevance:        <1 line>
A3 — Cascade:               <1 line>
A4 — DE call:               <1 line>
B1 — Direction logic:       <1 line>
B2 — Direction call:        <1 line>

P_DE: <integer 0-100>
P_up_given_DE: <integer 0-100>"""


def _format_replogle(prior: ReplogPrior, pert: str, gene: str) -> str:
    tier = prior.tier(pert, gene)
    if tier == 'none':
        return ("Cross-species Replogle prior: not available "
                "(perturbed gene has no human ortholog in Replogle K562+RPE1).")
    hpert = prior.m2h.get(pert, pert.upper())
    tops = prior.get_top_responders(pert, n=5)
    lines = [
        f"Cross-species Replogle prior (K562 + RPE1 averaged, human ortholog `{hpert}` of `{pert}`):",
        f"  Top upregulated:   " + ', '.join(
            f"{t['mouse_symbol']} ({t['logfc']:+.2f})" for t in tops['up']),
        f"  Top downregulated: " + ', '.join(
            f"{t['mouse_symbol']} ({t['logfc']:+.2f})" for t in tops['down']),
    ]
    if tier == 'full':
        lf = prior.get_pair_logfc(pert, gene)
        hgene = prior.m2h.get(gene, gene.upper())
        lines.append(
            f"  Direct query: target `{gene}` ortholog `{hgene}` Replogle logFC = {lf:+.3f}")
    return '\n'.join(lines)


def build_track_a_prompt(pert: str, gene: str, *,
                         prior: Optional[ReplogPrior] = None,
                         retriever: Optional[ExampleRetriever] = None,
                         desc: Optional[GeneDesc] = None,
                         kg: Optional[KGRetrieval] = None,
                         k_a: int = 5, k_c: int = 5,
                         exclude_query: bool = False,
                         seed: int = 42) -> str:
    """Build the single-call Track-A prompt for (pert, gene)."""
    prior = prior or ReplogPrior()
    kg = kg or KGRetrieval()
    retriever = retriever or ExampleRetriever(kg=kg)
    desc = desc or gene_desc_default()

    # Use DE-task analog/contrast pools (positive = DE happened, negative = none).
    # This is more informative for the joint task than DIR pools because DIR's
    # contrast pool (down) is often empty in our data.
    analog, contrast = retriever.retrieve_analog_contrast(
        pert, gene, task='de', k_a=k_a, k_c=k_c,
        exclude_query=exclude_query, seed=seed)
    ex_block = ExampleRetriever.format_block_analog_contrast(
        analog, contrast, task='de', seed=seed)

    pert_paths = kg.get_pathways(pert, top_n=3)
    gene_paths = kg.get_pathways(gene, top_n=3)

    body = [
        _HEADER.format(pert=pert, gene=gene),
        '',
        '## Cell context (BMDM)',
        bmdm_block(),
        '',
        '## Query',
        f'  Perturbed gene (CRISPRi KD): `{pert}`',
        f'    Description: {desc.get(pert, pathway_fallback=pert_paths)}',
        f'  Target gene (readout):       `{gene}`',
        f'    Description: {desc.get(gene, pathway_fallback=gene_paths)}',
        '',
        '## Evidence cases from train (analogue + contrast, real labels)',
        f'{len(analog)} analogue cases (similar pert/gene pairs where DE was observed) and '
        f'{len(contrast)} contrast cases (similar pairs where DE was NOT observed). '
        'Pairs were retrieved by STRING + Reactome similarity to the query. The mix '
        'of Yes/No outcomes is by construction; reason about which side the present '
        'case is closer to and why. Do not vote — apply rule R1.',
        ex_block,
        '',
        '## ' + _format_replogle(prior, pert, gene),
        '',
        _RULES,
        '',
        _PROTOCOL.format(pert=pert, gene=gene),
        '',
        _OUTPUT_FORMAT,
    ]
    return '\n'.join(body)


def estimate_tokens(text: str) -> int:
    return len(text) // 4
