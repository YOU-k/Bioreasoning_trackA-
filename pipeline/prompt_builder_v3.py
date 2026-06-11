"""Track-A compliant single-call prompt builder (attempts 06 + 07).

Produces ONE prompt per (pert, gene) query that elicits BOTH integers in
one LLM response:

    P_DE: <0-100>
    P_up_given_DE: <0-100>

The runner then folds:
    p_up   = P_DE/100 * P_up_given_DE/100
    p_down = P_DE/100 * (1 - P_up_given_DE/100)

Three additions over the two-prompt attempt 05 surface that survived
attempt 06's failure analysis:

1. Anti-storytelling guard (R1) — explicit qualitative rule that
   plausibility ≠ prediction; absence of pert-specific evidence is itself
   evidence FOR `none`.
2. BMDM context rule (R3) — silent vs expressed vs inducible programs.
3. Replogle direction-transfer rule (R5) — when cross-species transfer is
   reliable.
4. Decoupling rule (R6) — high direction confidence does NOT inflate P_DE.

Attempt 06 ALSO tried two prescriptive numerical anchors that BACKFIRED
and were removed in attempt 07:
- "default P_up ≈ 62" → 26/60 rows returned exactly 62 (lazy escape).
- "lean P_DE toward 15-25" → DE compression at the low end killed ranking.

Attempt 07 replaces these with **descriptive tier ladders** that say what
each band of P_DE / P_up_given_DE *means* in terms of evidence strength,
without giving the model a printed integer to copy.

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
from .hagai_prior import HagaiPrior, default as hagai_default


_HEADER = """You are a biological-reasoning engine for mouse bone-marrow-derived macrophages (BMDM) under CRISPRi perturbation.

Task: For CRISPRi knockdown of `{pert}` and readout gene `{gene}` in mouse BMDM, emit TWO calibrated integers:

  P_DE          = P(target `{gene}` is differentially expressed) × 100
                  (DE = FDR<5% AND |shrunken log2 fold-change| ≥ log2(1.5) ≈ 0.585, within 24-72h scRNA-seq pseudobulk)
  P_up_given_DE = P(direction is UP | DE happens) × 100

These are DIFFERENT quantities. High direction confidence does NOT imply high P_DE: "if DE, surely up" only justifies a high P_up_given_DE; P_DE depends on whether DE crosses the cutoff at all."""


_RULES = """Decision rules (read these BEFORE reasoning):

R1. Plausibility ≠ prediction. A mechanism that "could plausibly cause DE" is NOT evidence of DE. Most pairs are `none` because they failed the magnitude/FDR cutoff, not because no mechanism exists. Absence of pert-specific evidence is itself evidence FOR `none`.

R2. Match the BMDM context. Genes in silent BMDM programs (cell cycle, adaptive immunity, neuronal/epithelial lineage) usually stay silent under KD of upstream regulators. Genes in actively expressed BMDM programs (TLR, NF-κB, ISR, IFN, ER, ribosome) are easier to perturb.

R3. **Hagai (mouse BMDM, LPS6h) is the strongest mouse-native prior** for whether a gene is regulated in this exact cell type. A gene with large |Hagai logFC| under LPS is an inflammation-responsive gene that is "easy to perturb"; a flat / n.s. gene is harder to perturb and more often `none`. Hagai measures LPS stimulation, NOT CRISPRi knockdown — direction does not directly transfer (KD of an LPS pathway activator → LPS targets DOWN; KD of an inhibitor → LPS targets UP). Use Hagai magnitude for P_DE and as a signal that the target gene "can be perturbed at all" in BMDM.

R4. Replogle (human K562 + RPE1 CRISPRi) direction transfers for cell-autonomous programs (translation, ISR, proteostasis, chromatin). It is UNRELIABLE for macrophage-specific programs (TLR/NLR, NF-κB, IFN-I, MHC-II). Where Replogle has a direct (pert, gene) ortholog match, trust its direction unless Hagai or BMDM context contradicts.

R5. The two integers are independent. Estimate P_DE using DE-magnitude logic (R1-R3 + Hagai magnitude + Replogle scalar + analog/contrast). Estimate P_up_given_DE using direction logic (activator/repressor parity + signed pathway + Replogle direct direction). Do not let one anchor the other: "if DE, surely up" only justifies high P_up_given_DE — it does NOT inflate P_DE."""


_PROTOCOL = """Reasoning protocol (≤ 2 lines each, terse):

Step A1 — Mechanism class of `{pert}`: (TF / kinase / chaperone / aminoacyl-tRNA synthetase / ER-UPR / IFN / chromatin / ribosome / ...). Does Hagai show `{pert}` itself as LPS-regulated?
Step A2 — BMDM relevance of `{gene}`: which BMDM program (expressed / silent / inducible)? What does Hagai say about `{gene}` (large |logFC| → easy to perturb; flat → hard to perturb)?
Step A3 — Cascade: trace KD `{pert}` → pathway / TF / stress program → `{gene}`. Note path length and confidence.
Step A4 — DE call: locate the query on the P_DE ladder (see ladder below). Anchor on Hagai magnitude (R3) and Replogle |logFC| (R4); compare analogue vs contrast cases; apply R1-R2.

Step B1 — Direction logic: is `{pert}` (or its immediate downstream node) an ACTIVATOR or REPRESSOR of programs that include `{gene}`? Apply: KD of activator → DOWN; KD of repressor → UP; KD that triggers ISR/UPR/inflammation → stress-response targets UP. If Replogle has a direct (pert, gene) ortholog match, trust its sign unless R4 contradicts.
Step B2 — Direction call: locate the query on the P_up_given_DE ladder (see ladder below). Apply R4 + signed-pathway logic."""


_TIER_LADDERS = """P_DE ladder — locate the query on this scale of DE-magnitude evidence:
   90-100  direct, well-established BMDM regulation (analogues + Replogle + signed cascade all agree)
   70-89   strong pathway link + analogue / Replogle support
   50-69   plausible link, context uncertain
   30-49   weak / indirect link, multiple confound paths
   10-29   active reason to expect NO effect (silent program, distance, paralog rescue)
    0-9    strongly contradicted

P_up_given_DE ladder — locate the query on this scale of direction evidence:
   90-100  `{pert}` clearly represses `{gene}` (KD releases → UP); or strong stress trigger → stress-response UP
   70-89   pathway-level evidence for derepression / stress-induced UP
   55-69   slight lean UP (analogues + Replogle agree)
   45-54   ambiguous direction (no signed path, mixed analogue evidence)
   30-44   slight lean DOWN
   11-29   pathway-level evidence for activation removal → DOWN
    0-10   `{pert}` clearly activates `{gene}` (KD reduces → DOWN)"""


_OUTPUT_FORMAT = """OUTPUT FORMAT (STRICT — every step on one short line; final two lines MUST match exactly):

A1 — Mechanism & analogues: <1 line>
A2 — BMDM relevance:        <1 line>
A3 — Cascade:               <1 line>
A4 — DE call:               <1 line>
B1 — Direction logic:       <1 line>
B2 — Direction call:        <1 line>

P_DE: <integer 0-100>
P_up_given_DE: <integer 0-100>"""


def _format_hagai_line(hagai: HagaiPrior, symbol: str, role: str) -> str:
    """One terse line per gene: logFC, padj, qualitative tag."""
    r = hagai.get(symbol)
    if r is None:
        return f"  {role:<13}  `{symbol}` — not in Hagai (gene not measured in mouse BMDM LPS dataset)"
    lf = r['logfc']
    padj = r['p_adj']
    sig_tag = ''
    if padj < 1e-10 and abs(lf) >= 0.585:
        sig_tag = ' (strong)'
    elif padj < 0.05 and abs(lf) >= 0.585:
        sig_tag = ' (moderate)'
    elif padj < 0.05:
        sig_tag = ' (weak)'
    else:
        sig_tag = ' (n.s.)'
    direction = 'UP' if lf > 0 else 'DOWN' if lf < 0 else 'flat'
    return (f"  {role:<13}  `{symbol}` Hagai logFC = {lf:+.2f}, padj = {padj:.1e} "
            f"→ {direction}{sig_tag} under LPS")


def _format_hagai(hagai: HagaiPrior, pert: str, gene: str) -> str:
    return (
        "Mouse BMDM LPS6h prior (Hagai 2018, mouse macrophages stimulated with "
        "LPS for 6h vs unstimulated control). Direct mouse-native signal — no "
        "ortholog hop:\n"
        + _format_hagai_line(hagai, pert, 'KD candidate') + "\n"
        + _format_hagai_line(hagai, gene, 'Target gene')
    )


def _format_evidence_enriched(analog: list, contrast: list, *,
                              hagai: HagaiPrior, prior: ReplogPrior,
                              seed: int = 42) -> str:
    """Enriched version of format_block_analog_contrast for the DE task.

    Each example line now includes:
      - pert / gene names and real DE-task label (Yes/No)
      - Hagai |logFC| for the example's pert and gene (mouse-native)
      - Replogle logFC for the (pert, gene) pair if Replogle has full match

    This costs ~25-35 tokens per example vs the plain version's ~12. The
    rationale is that the LLM should be able to see WHICH dimension makes
    each example similar to the query, not just its label.
    """
    if not analog and not contrast:
        return "No structurally similar (perturbed, target) pairs available in train."
    import random as _random
    combined = list(analog) + list(contrast)
    _random.Random(seed).shuffle(combined)
    lines = []
    for i, (p, g, lbl) in enumerate(combined, 1):
        result = ('Yes (DE observed)' if lbl in ('up', 'down')
                  else 'No (not DE)')
        # Hagai features
        hp = hagai.get(p); hg = hagai.get(g)
        feats = []
        feats.append(
            f"Hagai pert |logFC|={abs(hp['logfc']):.2f}" if hp else "Hagai pert n/a")
        feats.append(
            f"Hagai target |logFC|={abs(hg['logfc']):.2f}" if hg else "Hagai target n/a")
        # Replogle direct logFC if available
        if prior.tier(p, g) == 'full':
            rep_lf = prior.get_pair_logfc(p, g)
            feats.append(f"Replogle logFC={rep_lf:+.2f}")
        lines.append(
            f"Example {i}: pert=`{p}`, target=`{g}` → {result}. "
            f"[{'; '.join(feats)}]"
        )
    return '\n'.join(lines)


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
                         hagai: Optional[HagaiPrior] = None,
                         retriever: Optional[ExampleRetriever] = None,
                         desc: Optional[GeneDesc] = None,
                         kg: Optional[KGRetrieval] = None,
                         k_a: int = 5, k_c: int = 5,
                         exclude_query: bool = False,
                         seed: int = 42,
                         include_bmdm_context: bool = False,
                         include_decision_rules: bool = True,
                         include_reasoning_protocol: bool = True,
                         enrich_examples: bool = False,
                         hide_example_labels: bool = False) -> str:
    """Build the single-call Track-A prompt for (pert, gene)."""
    prior = prior or ReplogPrior()
    hagai = hagai or hagai_default()
    kg = kg or KGRetrieval()
    retriever = retriever or ExampleRetriever(kg=kg)
    desc = desc or gene_desc_default()

    # Use DE-task analog/contrast pools (positive = DE happened, negative = none).
    # This is more informative for the joint task than DIR pools because DIR's
    # contrast pool (down) is often empty in our data.
    analog, contrast = retriever.retrieve_analog_contrast(
        pert, gene, task='de', k_a=k_a, k_c=k_c,
        exclude_query=exclude_query, seed=seed)
    if hide_example_labels:
        ex_block = ExampleRetriever.format_block_no_labels(
            analog, contrast, seed=seed)
    elif enrich_examples:
        ex_block = _format_evidence_enriched(
            analog, contrast, hagai=hagai, prior=prior, seed=seed)
    else:
        ex_block = ExampleRetriever.format_block_analog_contrast(
            analog, contrast, task='de', seed=seed)

    pert_paths = kg.get_pathways(pert, top_n=3)
    gene_paths = kg.get_pathways(gene, top_n=3)

    body = [_HEADER.format(pert=pert, gene=gene), '']
    if include_bmdm_context:
        body += ['## Cell context (BMDM)', bmdm_block(), '']
    body += [
        '## Query',
        f'  Perturbed gene (CRISPRi KD): `{pert}`',
        f'    Description: {desc.get(pert, pathway_fallback=pert_paths)}',
        f'  Target gene (readout):       `{gene}`',
        f'    Description: {desc.get(gene, pathway_fallback=gene_paths)}',
        '',
        '## Evidence cases from train (analogue + contrast)',
        (f'{len(analog) + len(contrast)} structurally similar (pert, target) pairs that exist '
         f'in train, retrieved by STRING + Reactome similarity to the query. '
         f'These exist as a sanity check that the question is well-defined — '
         f'the LLM should not infer outcome from their absence.') if hide_example_labels else
        (f'{len(analog)} analogue cases (similar pert/gene pairs where DE was observed) and '
         f'{len(contrast)} contrast cases (similar pairs where DE was NOT observed). '
         'Pairs were retrieved by STRING + Reactome similarity to the query. The mix '
         'of Yes/No outcomes is by construction; reason about which side the present '
         'case is closer to and why. Do not vote — apply rule R1.'),
        ex_block,
        '',
        '## ' + _format_hagai(hagai, pert, gene),
        '',
        '## ' + _format_replogle(prior, pert, gene),
        '',
    ]
    if include_decision_rules:
        body += [_RULES, '']
    if include_reasoning_protocol:
        body += [_PROTOCOL.format(pert=pert, gene=gene), '']
    # Tier ladders always included — descriptive calibration anchors are
    # essential per A06 → A07 finding; cheap (~250 tokens).
    body += [_TIER_LADDERS.format(pert=pert, gene=gene), '', _OUTPUT_FORMAT]
    return '\n'.join(body)


def estimate_tokens(text: str) -> int:
    return len(text) // 4
