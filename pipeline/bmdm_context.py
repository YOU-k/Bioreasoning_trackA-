"""Rich BMDM cell-state context paragraph for VCWorld-style prompts.

The single text block here is the analogue of VCWorld's per-cell-line
description. We supply baseline transcriptional state, expressed programs,
silent programs, and known sensitivities — so the LLM has real anchor
points rather than just "mouse macrophage".
"""

BMDM_CONTEXT = """\
Bone marrow-derived macrophages (BMDMs) are mouse primary myeloid cells \
differentiated in vitro from femoral/tibial bone marrow with M-CSF (CSF1) for \
6-7 days, then plated at confluence and assayed. They are non-dividing \
(post-mitotic) at the time of perturbation, MSS, of mixed C57BL/6 background \
unless otherwise specified, and uninfected/uncoligated (no LPS, no IFN, no IL4).

Baseline transcriptional state:
- High expression of myeloid lineage TFs (Cebpb, Spi1/PU.1, Mafb, Klf4) and \
M-CSF response genes (Csf1r, Mertk, Mafb).
- High constitutive expression of TLR/NLR sensors (Tlr2, Tlr4, Nlrp3), \
inflammasome components (Casp1, Pycard), MHC-II machinery (H2-Aa, Cd74), \
phagosomal / lysosomal genes (Lamp1, Lamp2, Lyz1/Lyz2, Ctss).
- High baseline ribosomal, ER, and proteostasis machinery (Rpl/Rps family, \
Hspa5/Bip, Calr, Pdia3/Pdia6, Eif2s1/2/3, Eef1a1).
- High baseline ISR / amino acid sensing (Atf4 readily inducible, Ddit3/CHOP, \
Trib3, Asns), making them sensitive to translation, amino-acid, and ER stress.

Silent or low-baseline programs (KD of upstream regulators in these \
programs will usually NOT produce a measurable DE signal within 24-72h):
- Cell cycle / mitosis (Mki67, Ccnb1, Ccnd1, Cdk1, Cdk14, Aurka, Foxm1) — \
BMDMs are post-mitotic.
- Adaptive immunity (Cd3, Cd4, Cd8, Tcr loci, Igh loci) — wrong lineage.
- Neuronal, epithelial, hepatic markers (Tubb3, Krt8/18, Alb) — wrong lineage.
- Many gametogenic / developmental TFs (Sox2, Pou5f1, T/Bra) — wrong context.

Inducible programs (the ones that produce strong DE upon the right trigger):
- IFN-I axis (Stat1, Stat2, Irf3/Irf7, Isg15, Ifit1/2/3, Mx1, Oas family, \
Rsad2) — only induced by IFN or RIG-I/MDA5 sensing.
- NF-kB inflammatory (Tnf, Il6, Il1b, Cxcl1, Ccl2, Nfkbia) — induced by \
TLR4/MyD88/TRIF or TNFR triggering.
- ISR (Atf4, Ddit3, Trib3, Asns, Ppp1r15a) — induced by translation stress \
(eIF2alpha phosphorylation via GCN2, PERK, PKR, HRI).
- Heat shock / proteostasis (Hspa1a, Hspa1b, Dnajb1) — induced by misfolding.
- Mitophagy / autophagy (Pink1, Nbr1, Sqstm1) — induced by organelle damage.

Cross-cell-type transfer notes vs Replogle K562/RPE1 priors:
- Universal / cell-autonomous programs (translation, ISR, ribosome \
biogenesis, proteostasis, cell-cycle in dividing cells, generic chromatin) \
transfer well in direction.
- Macrophage-specific programs (TLR/NLR signalling, IFN-I, NF-kB \
inflammatory, MHC-II) are EITHER stronger in BMDM (lineage richly expresses \
them) OR weaker (K562 leukemia partially co-opts them). Replogle direction \
is unreliable here; lean on BMDM-specific knowledge.

Perturbation modality: CRISPRi via dCas9-KRAB targeting the TSS of the \
perturbed gene, ~24-72h knockdown window, 60-90% knockdown efficiency. \
Readout: scRNA-seq, log-normalized, pseudobulked per perturbation. DE call: \
FDR<5% AND |shrunken log2 fold-change| >= log2(1.5) (~0.585)."""


def bmdm_block() -> str:
    """Return the BMDM cell-state paragraph (used in DE and DIR prompts)."""
    return BMDM_CONTEXT
