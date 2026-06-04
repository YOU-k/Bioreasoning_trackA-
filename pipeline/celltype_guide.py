"""Layer 3 — Cross-cell-type translation guide.

Static rules for how K562/RPE1 CRISPRi response transfers to mouse BMDM,
plus per-gene category tagging derived from Reactome pathway membership.

Two outputs:
  rules_block()                       static text shared across all queries
  tag_gene(gene, pathways) -> str     per-gene category tag for the query block
"""
from __future__ import annotations
from typing import Optional


# Keyword → category. Order matters: first match wins. BMDM-context categories
# are tested FIRST because the "should I downweight Replogle?" decision is the
# one we most care about; immune/TLR genes always have generic translation /
# transcription annotations too, but those are not the relevant transfer axis.
_CATEGORIES = [
    # BMDM-context-sensitive (transfer poorly) — try these first
    ('TLR_NLR',              ['toll-like', ' tlr', ' nlr ', 'nod-like', 'irak', 'myd88',
                              'tbk1', 'tlr4', 'tlr3', 'tlr7', 'tlr9']),
    ('INTERFERON',           ['interferon', ' isg ', 'type i ifn', ' irf3', ' irf7',
                              'jak-stat', 'antiviral']),
    ('IMMUNE_EFFECTOR',      ['cytokine signaling', 'interleukin', 'chemokine',
                              ' mhc ', 'antigen present',
                              'complement cascade', 'complement system',
                              'fcgamma', 'fc gamma', 'phagocytosis', 'inflammasome',
                              'tnf signaling', 'tnfr1', 'tnfr2', 'tnfsf']),
    ('MYELOID_LINEAGE',      ['hematopoiesis', 'myeloid differentiation',
                              'macrophage activ', 'monocyte differentiation']),

    # Universal / cell-autonomous (transfer well)
    ('UNIVERSAL_STRESS',     ['unfolded protein', 'integrated stress', 'response to stress',
                              'cellular response to stimuli', 'cellular responses to stress',
                              'amino acid deprivation']),
    ('TRANSLATION',          ['translation initiation', 'translation elongation',
                              'ribosome', 'aminoacyl', 'eukaryotic translation',
                              'rrna processing', 'mrna decay']),
    ('CELL_CYCLE',           ['cell cycle', 'mitotic', 'g1/s', 'g2/m', 'dna replication',
                              'chromosome segregation']),
    ('PROTEOSTASIS',         ['proteasome', 'ubiquitin', 'autophagy', 'protein folding']),
    ('METABOLISM_CORE',      ['glycolysis', 'tca cycle', 'oxidative phosphorylation',
                              'fatty acid', 'lipid metabolism', 'beta-oxidation',
                              'amino acid metabolism', 'pentose phosphate']),
    ('CHROMATIN_GENERIC',    ['chromatin', 'histone', 'transcription', 'rna polymerase']),
]


_RULES_BLOCK = """## Cross-cell-type transfer guide (K562/RPE1 -> mouse BMDM)

The Replogle prior is computed in K562 (leukemia) and RPE1 (epithelial) — neither is a macrophage. Use these rules to weight it:

[Transfer-friendly categories — trust Replogle direction]
  UNIVERSAL_STRESS, TRANSLATION, CELL_CYCLE, PROTEOSTASIS, METABOLISM_CORE,
  CHROMATIN_GENERIC

  Reasoning: these are cell-autonomous machineries shared across all mammalian
  cell types. When the readout gene falls in one of these and the pert KD
  triggers a generic stress/translation/cycle program, the K562/RPE1 direction
  almost always carries over to BMDM.

[Context-dependent categories — downweight Replogle, reason BMDM-specifically]
  IMMUNE_EFFECTOR, INTERFERON, TLR_NLR, MYELOID_LINEAGE

  Reasoning: these are signaling and transcriptional programs that BMDM
  expresses richly but K562/RPE1 either lack or run differently. Even if
  Replogle reports a signal, the BMDM response may be opposite, larger, or
  absent. Lean on your knowledge of macrophage biology, not on the Replogle
  scalar, for these.

[UNTAGGED — no clear pathway annotation]
  Use mechanistic reasoning over the pert/target identity directly; Replogle
  is one signal but not authoritative.

Apply: if the query's pert and target are BOTH transfer-friendly, weight
Replogle direction strongly. If either is context-dependent, treat Replogle
DIR with skepticism (its direction may be wrong in BMDM) and downweight
P_DE because the gene may simply not respond in BMDM the way it does in
the readout cell type."""


def rules_block() -> str:
    """Static text — same for every query, ~250 tokens."""
    return _RULES_BLOCK


def tag_gene(pathways: list[str]) -> Optional[str]:
    """Map a gene's pathway list to its dominant category.

    Counts keyword occurrences across all pathway names; category with the
    highest count wins. Ties broken by _CATEGORIES order. Returns None if
    no keyword fires.

    Score-based (not first-match) so a gene with many CELL_CYCLE hits and
    one IRF hit doesn't get tagged INTERFERON.
    """
    if not pathways:
        return None
    text = ' || '.join(p.lower() for p in pathways)
    scores = {}
    for cat, keywords in _CATEGORIES:
        n = sum(text.count(k) for k in keywords)
        if n > 0:
            scores[cat] = n
    if not scores:
        return None
    order = {c: i for i, (c, _) in enumerate(_CATEGORIES)}
    return max(scores.items(), key=lambda kv: (kv[1], -order[kv[0]]))[0]


def per_query_tag_block(pert: str, gene: str,
                        pert_pathways: list[str],
                        gene_pathways: list[str]) -> str:
    """Compact 3-4 line block for a specific (pert, gene)."""
    pert_cat = tag_gene(pert_pathways) or 'UNTAGGED'
    gene_cat = tag_gene(gene_pathways) or 'UNTAGGED'
    friendly = {'UNIVERSAL_STRESS', 'TRANSLATION', 'CELL_CYCLE',
                'PROTEOSTASIS', 'METABOLISM_CORE', 'CHROMATIN_GENERIC'}
    ctx_dep = {'IMMUNE_EFFECTOR', 'INTERFERON', 'TLR_NLR', 'MYELOID_LINEAGE'}

    def status(cat):
        return ('transfer-friendly' if cat in friendly
                else 'context-dependent' if cat in ctx_dep
                else 'untagged')

    advice = ''
    if pert_cat in friendly and gene_cat in friendly:
        advice = 'BOTH transfer-friendly -> trust Replogle DIR.'
    elif pert_cat in ctx_dep or gene_cat in ctx_dep:
        advice = ('At least one is context-dependent -> Replogle DIR may be '
                  'wrong; reason BMDM-specifically.')
    else:
        advice = ('At least one is untagged -> use Replogle as a weak signal, '
                  'rely on mechanistic reasoning.')

    return (f"## Per-query transfer tags\n"
            f"  pert `{pert}` category: {pert_cat} ({status(pert_cat)})\n"
            f"  target `{gene}` category: {gene_cat} ({status(gene_cat)})\n"
            f"  -> {advice}")
