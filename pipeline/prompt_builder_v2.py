"""Per-query prompt builders (attempts 04 + 05, VCWorld-style).

Two independent prompts per (pert, gene) query:
  * build_de_prompt  -> asks ONLY "is target DE?"  emits P_DE
  * build_dir_prompt -> asks ONLY "if DE, up or down?"  emits P_up_given_DE

Retrieval pattern follows VCWorld paper §3.4.2 (Wei et al., ICLR 2026): for
each task we retrieve two label-conditioned pools from train, ranked by KG
similarity, and present them with REAL labels. The structural mix of positive
and negative examples defeats vote bias without destroying the empirical
signal (attempt 04 used random labels which were not faithful to the paper).

Both prompts share: rich BMDM context, gene/pert description, analogue +
contrast exemplars with real labels. DE prompt includes the Replogle scalar
(it gave real DE signal in our evaluation). DIR prompt deliberately omits
Replogle's direction — attempt 03 showed the LLM systematically overrides it
with bad mechanism inference, hurting DIR-AUROC below random.
"""
from __future__ import annotations
from typing import Optional
from .bmdm_context import bmdm_block
from .gene_desc import GeneDesc, default as gene_desc_default
from .retrieve_examples import ExampleRetriever
from .kg_retrieval import KGRetrieval
from .replogle_prior import ReplogPrior


CHOICES_DE = ['Yes', 'No']
CHOICES_DIR = ['Increase', 'Decrease']


_DE_HEADER = """You are VCWorld-Mouse-BMDM, a biological world model and causal-reasoning engine for mouse bone-marrow-derived macrophages under CRISPRi perturbation.

Goal: Determine whether CRISPRi knockdown of `{pert}` produces significant differential expression (DE) of `{gene}` in mouse BMDM, measured by scRNA-seq pseudobulk. DE = (FDR<5%) AND (|shrunken log2 fold-change| >= log2(1.5) ≈ 0.585) within 24-72h."""


_DIR_HEADER = """You are VCWorld-Mouse-BMDM, a biological world model and causal-reasoning engine for mouse bone-marrow-derived macrophages under CRISPRi perturbation.

Goal: ASSUMING `{gene}` is differentially expressed in response to CRISPRi knockdown of `{pert}` in mouse BMDM, determine whether it is UPREGULATED or DOWNREGULATED. (You do not need to estimate the magnitude or whether DE happens — only the direction conditional on it happening.)"""


_DE_STEPS = """Reasoning protocol (perform a stepwise biological simulation; do not text-match):

1) Mechanism & analogue identification
   What functional class does `{pert}` belong to (TF, kinase, chaperone, ribosomal, aminoacyl-tRNA synthetase, ER/UPR, IFN axis, chromatin remodeller, …)? Which of the listed example perts share that class or the same Reactome / STRING neighbourhood?

2) Specificity & relevance in BMDM
   - Is `{gene}` part of a program that BMDM expresses richly at baseline (TLR/NLR, NF-kB, IFN-I, MHC-II, ribosome, ER, ISR), or one BMDM keeps silent (cell cycle, adaptive immunity, neuronal/epithelial)?
   - Given BMDM are post-mitotic and uncoligated, can the perturbation actually reach this readout?

3) Downstream signalling cascade
   Trace the cascade from KD of `{pert}` to a transcriptional consequence. Identify the TF or stress program that would (or would not) end up regulating `{gene}`.

4) Causal bridge & evidence synthesis
   Construct: KD `{pert}` -> Target/Pathway -> TF/Stress program -> `{gene}`. Compare to the analogue examples: do similar pert/gene pairs in train look like a 'something happens' regime or a 'nothing happens' regime? Note: analogue Result labels in the examples are RANDOMIZED to remove vote bias — use them only to confirm the question is biologically plausible, not as a label vote.

5) Calibrated DE call
   Output an integer P_DE in [0, 100] using these anchors:
   90-100  direct, well-established BMDM regulation
   70-89   strong pathway link + same direction in analogues / Replogle
   50-69   plausible pathway link, BMDM context uncertain
   30-49   weak / indirect link, lean toward null
   10-29   active reason to expect NO effect (silent program, distance, paralog rescue)
    0-9   strongly contradicted"""


_DIR_STEPS = """Reasoning protocol (assume DE will happen; reason ONLY about direction):

1) Mechanism & analogue identification (same as DE prompt, but focused on direction)
   What is the functional class of `{pert}`? Do any example perts in the same class produce a consistent directional pattern across similar genes?

2) Activator vs repressor logic
   - Is `{pert}` (or its immediate downstream node) an ACTIVATOR or REPRESSOR of programs that include `{gene}`?
   - Apply: KD of an activator -> target DOWN. KD of a repressor -> target UP. KD of something that drives ISR/UPR/stress -> stress response genes (Atf4, Ddit3, Hspa5, Trib3) typically UP.

3) Cross-cell-type reference (Replogle K562/RPE1 prior)
   Replogle direction is a useful cross-species reference for CELL-AUTONOMOUS programs (translation, cell cycle, proteostasis, chromatin, ISR). It is unreliable for MACROPHAGE-SPECIFIC programs (TLR/NLR, NF-kB inflammatory, IFN-I, MHC-II). Decide which regime applies.

4) BMDM-specific overrides
   If the Replogle direction conflicts with a BMDM-specific consideration (e.g., the gene is a lineage-determined macrophage gene), document the override explicitly. Otherwise default to the Replogle direction.

5) Calibrated direction call
   Output an integer P_up_given_DE in [0, 100] using these anchors:
   90-100  `{pert}` clearly represses `{gene}` (KD releases -> UP)
   70-89   pathway-level evidence for derepression / stress-induced UP
   55-69   slight lean UP (analogues + Replogle agree)
   45-54   ambiguous direction
   30-44   slight lean DOWN
   11-29   pathway-level evidence for activation removal -> DOWN
    0-10  `{pert}` clearly activates `{gene}` (KD reduces -> DOWN)"""


_DE_OUTPUT = """OUTPUT FORMAT (STRICT — last line must match exactly):
Step 1 — Mechanism & analogue:  <1-3 lines>
Step 2 — BMDM specificity:      <1-3 lines>
Step 3 — Cascade simulation:    <1-3 lines>
Step 4 — Causal bridge:         <1-3 lines>
Step 5 — Final call:            <1 line>

P_DE: <integer 0-100>"""


_DIR_OUTPUT = """OUTPUT FORMAT (STRICT — last line must match exactly):
Step 1 — Mechanism & analogue:  <1-3 lines>
Step 2 — Activator/repressor:   <1-3 lines>
Step 3 — Cross-species ref:     <1-3 lines>
Step 4 — BMDM override:         <1-3 lines>
Step 5 — Final direction call:  <1 line>

P_up_given_DE: <integer 0-100>"""


def _format_replogle_for_de(prior: ReplogPrior, pert: str, gene: str) -> str:
    tier = prior.tier(pert, gene)
    if tier == 'none':
        return ("Cross-species Replogle prior: not available "
                "(perturbed gene has no human ortholog in Replogle K562+RPE1).")
    hpert = prior.m2h.get(pert, pert.upper())
    tops = prior.get_top_responders(pert, n=5)
    lines = [
        f"Cross-species Replogle prior (K562 + RPE1 averaged):",
        f"  Human ortholog of `{pert}` = `{hpert}`",
        f"  Top upregulated:   " + ', '.join(
            f"{t['mouse_symbol']} ({t['logfc']:+.2f})" for t in tops['up']),
        f"  Top downregulated: " + ', '.join(
            f"{t['mouse_symbol']} ({t['logfc']:+.2f})" for t in tops['down']),
    ]
    if tier == 'full':
        lf = prior.get_pair_logfc(pert, gene)
        hgene = prior.m2h.get(gene, gene.upper())
        lines.append(
            f"  Direct query: `{gene}` ortholog `{hgene}` "
            f"Replogle logFC = {lf:+.3f}")
    else:
        lines.append(f"  Direct query: target `{gene}` has no human ortholog "
                     f"in Replogle — use top-responder list above only.")
    return '\n'.join(lines)


def build_de_prompt(pert: str, gene: str, *,
                    prior: Optional[ReplogPrior] = None,
                    retriever: Optional[ExampleRetriever] = None,
                    desc: Optional[GeneDesc] = None,
                    kg: Optional[KGRetrieval] = None,
                    k_a: int = 5, k_c: int = 5,
                    exclude_query: bool = False,
                    seed: int = 42) -> str:
    prior = prior or ReplogPrior()
    kg = kg or KGRetrieval()
    retriever = retriever or ExampleRetriever(kg=kg)
    desc = desc or gene_desc_default()

    analog, contrast = retriever.retrieve_analog_contrast(
        pert, gene, task='de', k_a=k_a, k_c=k_c,
        exclude_query=exclude_query, seed=seed)
    ex_block = ExampleRetriever.format_block_analog_contrast(
        analog, contrast, task='de', seed=seed)

    pert_paths = kg.get_pathways(pert, top_n=3)
    gene_paths = kg.get_pathways(gene, top_n=3)

    body = [
        _DE_HEADER.format(pert=pert, gene=gene),
        '',
        '## Cell context (BMDM)',
        bmdm_block(),
        '',
        '## Query',
        f'  Perturbed gene (knocked down by CRISPRi): `{pert}`',
        f'    Description: {desc.get(pert, pathway_fallback=pert_paths)}',
        f'  Target gene (readout): `{gene}`',
        f'    Description: {desc.get(gene, pathway_fallback=gene_paths)}',
        '',
        '## Evidence cases from train (analogue + contrast)',
        f'These are {len(analog)} **analogue** cases (similar pert/gene pairs '
        f'where DE was observed) and {len(contrast)} **contrast** cases '
        f'(similar pairs where DE was NOT observed). Pairs were retrieved by '
        'STRING + Reactome similarity to the query (pert, target). Use them '
        'to anchor mechanism reasoning; the mix of Yes/No outcomes is by '
        'construction, so do not vote — reason about which side the present '
        'case is closer to and why.',
        ex_block,
        '',
        '## ' + _format_replogle_for_de(prior, pert, gene),
        '',
        _DE_STEPS.format(pert=pert, gene=gene),
        '',
        _DE_OUTPUT,
    ]
    return '\n'.join(body)


def build_dir_prompt(pert: str, gene: str, *,
                     prior: Optional[ReplogPrior] = None,
                     retriever: Optional[ExampleRetriever] = None,
                     desc: Optional[GeneDesc] = None,
                     kg: Optional[KGRetrieval] = None,
                     k_a: int = 5, k_c: int = 5,
                     exclude_query: bool = False,
                     seed: int = 42) -> str:
    prior = prior or ReplogPrior()
    kg = kg or KGRetrieval()
    retriever = retriever or ExampleRetriever(kg=kg)
    desc = desc or gene_desc_default()

    analog, contrast = retriever.retrieve_analog_contrast(
        pert, gene, task='dir', k_a=k_a, k_c=k_c,
        exclude_query=exclude_query, seed=seed)
    ex_block = ExampleRetriever.format_block_analog_contrast(
        analog, contrast, task='dir', seed=seed)

    pert_paths = kg.get_pathways(pert, top_n=3)
    gene_paths = kg.get_pathways(gene, top_n=3)

    body = [
        _DIR_HEADER.format(pert=pert, gene=gene),
        '',
        '## Cell context (BMDM)',
        bmdm_block(),
        '',
        '## Query',
        f'  Perturbed gene (knocked down by CRISPRi): `{pert}`',
        f'    Description: {desc.get(pert, pathway_fallback=pert_paths)}',
        f'  Target gene (readout): `{gene}`',
        f'    Description: {desc.get(gene, pathway_fallback=gene_paths)}',
        '',
        '## Evidence cases from train (analogue + contrast)',
        f'These are {len(analog)} **analogue** cases (similar pert/gene pairs '
        f'where the target went UP) and {len(contrast)} **contrast** cases '
        f'(similar pairs where it went DOWN). Pairs where DE did not happen '
        f'are excluded entirely — DIR is conditional on DE. The mix of '
        'Increase/Decrease is by construction; reason about which direction '
        'the present case is closer to and why.',
        ex_block,
        '',
        '## ' + _format_replogle_for_de(prior, pert, gene),
        '',
        _DIR_STEPS.format(pert=pert, gene=gene),
        '',
        _DIR_OUTPUT,
    ]
    return '\n'.join(body)


def estimate_tokens(text: str) -> int:
    return len(text) // 4
