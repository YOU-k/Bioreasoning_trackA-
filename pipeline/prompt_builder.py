"""Per-question Track A prompt builder.

Designed to:
  - Stay under 4096 input tokens
  - Output two 0-100 integers (P_DE, P_up_given_DE), parsed downstream
  - Force the disconfirming step (anti yes-bias)
  - Inject Replogle DIR prior when available (compresses cross-species CRISPRi
    evidence into ≤15 lines)
"""
from __future__ import annotations
from typing import Optional
from .replogle_prior import ReplogPrior
from .kg_retrieval import KGRetrieval
from .celltype_guide import rules_block, per_query_tag_block


_SYSTEM = """You are a perturbation-response analyst for a mouse BMDM (bone marrow-derived macrophage) CRISPRi Perturb-seq study. The study knocks down one gene at a time and measures bulk-averaged scRNA-seq response.

You will receive ONE (perturbed_gene, target_gene) pair. Decide:
  (a) P_DE: probability the target gene is significantly differentially expressed (FDR<5% AND |log2FC|>=log2(1.5)≈0.585)
  (b) P_up_given_DE: if DE, probability it is upregulated rather than downregulated

Both outputs are integers in [0, 100]. Output the two numbers on the LAST TWO lines, nothing after."""


_CONTEXT = """## Experimental context (binding)
- Cell type: mouse BMDM (in vitro, primary cells, no co-culture).
- Perturbation: CRISPRi via dCas9-KRAB (transcriptional repression, 24-72h window).
- Readout: scRNA-seq, log-normalized, pseudobulked per perturbation.
- DE definition: FDR<5% AND |shrunken log2 fold-change| >= log2(1.5).
- Gene nomenclature: MOUSE (e.g., Stat1 not STAT1; Riken IDs like 1500011B03Rik are mouse-specific lncRNAs/uncharacterized).
- Macrophage-relevant biology to weight high: TLR/NFkB signalling, IFN/STAT axis, ISR (Atf4/Ddit3), inflammasome, ribosomal/proteostasis machinery, MHC-II and antigen presentation.
- Systemic / organ-level effects are ABSENT (cells are in vitro). Any effect must be cell-autonomous."""


_DISCONFIRMER_BLOCK = """## Mandatory disconfirming check (do NOT skip)
Before deciding the target gene is DE (P_DE > 50), find at least TWO reasons it might NOT be DE. Choose from:
  (a) Pathway distance: is target_gene >2 hops from perturbed_gene in known mouse GRN / PPI / Reactome? If yes, transcriptional effect within 24-72h is unlikely.
  (b) Paralog compensation: does perturbed_gene have a closely related mouse paralog that may buffer KD?
  (c) Expression floor: is target_gene's baseline expression in BMDM low/below the DE pipeline's reliable-detection threshold? If yes, fold-change is noisy and the row likely ends up "none".
  (d) BMDM specificity: is the target_gene known to respond only in non-macrophage contexts (T cell, neuron, epithelium)?
If you cannot find two concerns, explicitly write: "No serious disconfirmer found" and explain why each of (a)/(b)/(c)/(d) is inapplicable. Otherwise downweight P_DE."""


_OUTPUT_ANCHORS = """## Output format (STRICT — last two lines must match exactly)
Reasoning: write 4-8 short lines covering Mechanism / Direction / Disconfirmer / Final-call.

Anchors for P_DE (probability the target is DE):
  90-100: known direct regulatory link in mouse BMDM (literature or pathway DB)
  70-89:  clear pathway connection, target known to respond to similar KDs
  50-69:  pathway-level evidence but BMDM-context uncertain
  30-49:  weak prior, slight lean toward null
  10-29:  active reason to expect NO effect (paralog, distance, low expression)
  0-9:    contradicted by mouse data

Anchors for P_up_given_DE (probability of up rather than down, conditional on DE):
  90-100: perturbed_gene is a known repressor of target_gene -> KD releases repression -> up
  60-89:  partial / pathway-level evidence for derepression
  40-59:  ambiguous direction
  11-39:  partial evidence for activation -> KD reduces -> down
  0-10:   perturbed_gene is a known activator -> KD reduces -> down

P_DE: <integer 0-100>
P_up_given_DE: <integer 0-100>"""


def _format_replogle_block(prior: ReplogPrior, pert: str, gene: str) -> str:
    """Build a tight Replogle prior block (≤500 tokens)."""
    tier = prior.tier(pert, gene)
    if tier == 'none':
        return "## Cross-species CRISPRi prior\nNot available (perturbed gene has no clear human ortholog in Replogle K562+RPE1).\n"

    hpert = prior.m2h.get(pert, pert.upper())
    tops = prior.get_top_responders(pert, n=5)

    lines = [
        "## Cross-species CRISPRi prior (Replogle K562 + RPE1, averaged)",
        f"Note: K562 (leukemia) and RPE1 (epithelial) are NOT macrophages. Treat as DIR prior",
        f"only; DE detection in BMDM is poorly conserved (calibrated DIR-AUROC=0.66, DE-AUROC=0.54).",
        f"",
        f"Human ortholog of perturbed gene `{pert}` = `{hpert}`.",
        f"In Replogle CRISPRi, KD of {hpert}:",
        f"  Top upregulated:   " + ", ".join(f"{t['mouse_symbol']} (logFC={t['logfc']:+.2f})" for t in tops['up']),
        f"  Top downregulated: " + ", ".join(f"{t['mouse_symbol']} (logFC={t['logfc']:+.2f})" for t in tops['down']),
    ]
    if tier == 'full':
        lf = prior.get_pair_logfc(pert, gene)
        hgene = prior.m2h.get(gene, gene.upper())
        sign = '+' if lf >= 0 else ''
        # rough confidence based on magnitude
        if abs(lf) < 0.05:
            interp = "near zero — Replogle says NO clear effect (could be none, could be BMDM-specific)"
        elif abs(lf) < 0.2:
            interp = "weak signal — borderline, weight against false-DE"
        elif abs(lf) < 0.5:
            interp = "moderate signal — likely DE if conserved across cell types"
        else:
            interp = "strong signal — Replogle is confident; direction likely transfers"
        direction = "up" if lf > 0 else "down"
        lines += [
            f"",
            f"  Direct query: human ortholog `{hgene}` of target `{gene}`:",
            f"  Replogle logFC = {sign}{lf:.3f}  ({interp}; if DE, direction={direction})",
        ]
    else:
        lines += [
            f"",
            f"  Target gene `{gene}` has no clear human ortholog (Riken/mouse-specific)",
            f"  -> only the top responder list above is informative.",
        ]
    return "\n".join(lines) + "\n"


def _format_kg_block(kg: KGRetrieval, pert: str, gene: str,
                     name_max_chars: int = 75) -> str:
    """Layer 2: Mouse KG mechanism context (pathways + PPI shortest path).
    ~150-200 tokens per query."""
    def trim(name: str) -> str:
        return name if len(name) <= name_max_chars else name[:name_max_chars - 1] + "..."

    pert_paths = kg.get_pathways(pert, top_n=3)
    gene_paths = kg.get_pathways(gene, top_n=3)
    shared = kg.shared_pathways(pert, gene)[:3]
    path = kg.shortest_path(pert, gene, max_depth=3)

    lines = ["## Mouse KG mechanism context (Reactome + STRING ≥700)"]
    if pert_paths:
        lines.append(f"Pert `{pert}` Reactome pathways:")
        for p in pert_paths:
            lines.append(f"  - {trim(p)}")
    else:
        lines.append(f"Pert `{pert}`: no Reactome mouse annotation (use mechanistic knowledge)")
    if gene_paths:
        lines.append(f"Target `{gene}` Reactome pathways:")
        for p in gene_paths:
            lines.append(f"  - {trim(p)}")
    else:
        lines.append(f"Target `{gene}`: no Reactome mouse annotation (use mechanistic knowledge)")
    if shared:
        lines.append("Shared pathways:")
        for p in shared:
            lines.append(f"  - {trim(p)}")
    if path is None:
        lines.append("PPI shortest path (STRING ≥700, depth ≤3): NONE — no direct mechanistic link")
    elif len(path) == 2:
        lines.append(f"PPI shortest path: `{pert}` <-> `{gene}` (DIRECT, 1 edge)")
    else:
        chain = " -> ".join(f"`{n}`" for n in path)
        lines.append(f"PPI shortest path ({len(path)-1} hops): {chain}")
    return "\n".join(lines)


def build_prompt(pert: str, gene: str,
                 prior: Optional[ReplogPrior] = None,
                 kg: Optional[KGRetrieval] = None,
                 use_kg: bool = True) -> str:
    """Build the full per-question prompt for Track A.

    Layers:
      1. Replogle scalar prior  (always)
      2. KG mechanism context   (if use_kg)
      3. Cell-type translation guide + per-query tags  (if use_kg)
    """
    if prior is None:
        prior = ReplogPrior()
    if use_kg and kg is None:
        kg = KGRetrieval()

    body = [
        _SYSTEM,
        "",
        _CONTEXT,
        "",
        "## Query",
        f"  Perturbed gene (knocked down): `{pert}`",
        f"  Target gene (readout): `{gene}`",
        "",
        _format_replogle_block(prior, pert, gene),
    ]
    if use_kg:
        body += [
            _format_kg_block(kg, pert, gene),
            "",
            rules_block(),
            "",
            per_query_tag_block(
                pert, gene,
                kg.get_pathways(pert, top_n=20),  # use more for accurate tag
                kg.get_pathways(gene, top_n=20),
            ),
            "",
        ]
    body += [
        _DISCONFIRMER_BLOCK,
        "",
        _OUTPUT_ANCHORS,
    ]
    return "\n".join(body)


# Rough token estimate
def estimate_tokens(text: str) -> int:
    """Rough char/4 estimate (close enough for English+code)."""
    return len(text) // 4
