"""End-to-end Track A scaffolding:
   1. build_all_prompts(test.csv)            → 1813 prompt strings
   2. (external) run GPT-OSS-120B × 3 seeds per prompt
   3. assemble_submission(outputs)           → submission.csv + zip

This module does NOT call any LLM directly — it only builds prompts and
assembles outputs. Inference is left to the user's GPU/API call.
"""
from __future__ import annotations
import csv, json, math, os, time
from pathlib import Path
from .replogle_prior import ReplogPrior
from .prompt_builder import build_prompt
from .prompt_builder_v3 import build_track_a_prompt, estimate_tokens
from .output_parser import parse


# Harmony developer-role system prompt baked into the local GPT-OSS-120B
# inference path on the LLM server (origin/sync/a15-submit-v3). We mirror it
# here so prompt_tokens can be computed identically on this host.
_LOCAL_DEV_INSTRUCTIONS = (
    "Reasoning: low\n"
    "Follow the user's instructions exactly.\n"
    "Do not reveal scratch work, drafts, or chain-of-thought.\n"
    "Write only the final answer block requested by the user.\n"
    "Stop immediately after the final numeric line."
)


def _logit(p: float, eps: float = 1e-6) -> float:
    p = min(1 - eps, max(eps, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def fuse_q_r_logit(q_per_seed: list[float], r_per_seed: list[float]
                   ) -> tuple[float, float, float, float]:
    """3-seed fusion via logit-averaging of q=P(DE) and r=P(up|DE) separately.

    Returns (q_final, r_final, p_up_final, p_down_final).

    Rationale (see discussion/next_paradigm_gpt.md §3): averaging p_up / p_down
    directly lets a single extreme seed pollute BOTH DE and DIR; fusing in
    logit space on q and r independently keeps the two AUROCs decoupled."""
    q = _sigmoid(sum(_logit(v) for v in q_per_seed) / len(q_per_seed))
    r = _sigmoid(sum(_logit(v) for v in r_per_seed) / len(r_per_seed))
    return q, r, q * r, q * (1 - r)


def hybrid_direction(r_llm: float, pert: str, gene: str,
                     replogle_prior, alpha: float = 0.45,
                     non_full_default: float = 0.58) -> tuple[float, str]:
    """Replace the LLM's r=P(up|DE) with a hybrid that anchors on Replogle.

    Empirically (attempts 09 + 11), on test-condition data (probe60_rare_gene)
    where the readout gene is unseen in train, the LLM's direction call is
    near-random (DIR-AUROC ≈ 0.48). Replogle's direct ortholog logFC sign is
    a much stronger direction signal (DIR-AUROC ≈ 0.57 alone). Blending
    captures the LLM's contribution while anchoring on Replogle.

    For rows without a Replogle full-tier match, the LLM's r is also
    near-random; we fall back to the train direction prior (up:down ≈ 2.2:1).

    Returns (r_hybrid, source_tag) where source_tag is 'replogle_blend' or
    'prior_fallback' for telemetry / per-row inspection.
    """
    tier = replogle_prior.tier(pert, gene)
    if tier == 'full':
        lf = replogle_prior.get_pair_logfc(pert, gene)
        r_replogle = _sigmoid(3.0 * lf)
        r_hybrid = alpha * r_llm + (1 - alpha) * r_replogle
        return r_hybrid, 'replogle_blend'
    return non_full_default, 'prior_fallback'

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'


def build_all_prompts(test_csv: str | Path = DATA/'test.csv',
                      out_dir: str | Path = ROOT/'attempts/02_baseline_prompts/prompts',
                      use_kg: bool = False) -> dict:
    """Build per-row prompts for every row in test.csv.

    Args:
        use_kg: include Layer 2 (KG mechanism) and Layer 3 (cell-type guide)
                in addition to Layer 1 (Replogle prior). attempt 02 = False,
                attempt 03+ = True.

    Returns a dict summary {id: {pert, gene, tier, n_tokens, prompt_path}}.
    """
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    prior = ReplogPrior()
    kg = None
    if use_kg:
        from .kg_retrieval import KGRetrieval
        kg = KGRetrieval()
    summary = {}
    t0 = time.time()
    with open(test_csv) as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows):
        rid, pert, gene = row['id'], row['pert'], row['gene']
        prompt = build_prompt(pert, gene, prior, kg=kg, use_kg=use_kg)
        path = out_dir / f"{rid}.txt"
        with open(path, 'w') as fh: fh.write(prompt)
        summary[rid] = {
            'pert': pert, 'gene': gene,
            'tier': prior.tier(pert, gene),
            'n_chars': len(prompt),
            'n_tokens_est': estimate_tokens(prompt),
        }
    with open(out_dir/'_summary.json', 'w') as fh:
        json.dump(summary, fh, indent=1)
    print(f"Built {len(summary)} prompts in {time.time()-t0:.0f}s -> {out_dir}")
    tiers = {'full':0,'pert_only':0,'none':0}
    tok = []
    for s in summary.values():
        tiers[s['tier']] += 1
        tok.append(s['n_tokens_est'])
    print(f"  tier distribution: {tiers}")
    print(f"  prompt tokens: min={min(tok)}, median={sorted(tok)[len(tok)//2]}, max={max(tok)} (budget 4096)")
    return summary


def assemble_submission(outputs_dir: str | Path,
                        seeds: tuple = (42, 43, 44),
                        out_path: str | Path = ROOT/'submission.csv',
                        model_name: str = 'gpt-oss-120b',
                        apply_hybrid_direction: bool = True,
                        hybrid_alpha: float = 0.45,
                        hybrid_non_full_default: float = 0.58):
    """Read per-seed LLM outputs from {outputs_dir}/{seed}/{id}.txt and
    assemble submission.csv with required Track A columns.

    Expected structure under outputs_dir:
       outputs_dir/42/{id}.txt   <- raw LLM output (string), seed 42
       outputs_dir/43/{id}.txt   <- raw LLM output, seed 43
       outputs_dir/44/{id}.txt
       outputs_dir/tokens/{id}.json with {"42": n42, "43": n43, "44": n44}
    """
    outputs_dir = Path(outputs_dir)
    test_csv = DATA / 'test.csv'
    out_rows = []
    with open(test_csv) as f:
        for row in csv.DictReader(f):
            rid = row['id']
            seed_results = {}
            tokens_per_seed = {}
            for seed in seeds:
                txt_path = outputs_dir / str(seed) / f"{rid}.txt"
                raw = txt_path.read_text() if txt_path.exists() else ""
                p = parse(raw)
                seed_results[seed] = p
            # 3-seed fusion: logit-average q=P(DE) and r=P(up|DE) separately,
            # then p_up=q*r, p_down=q*(1-r). See fuse_q_r_logit docstring.
            q_seeds = [seed_results[s].p_de for s in seeds]
            r_seeds = [seed_results[s].p_up_given_de for s in seeds]
            q_final, r_llm_final, _pup0, _pdn0 = fuse_q_r_logit(q_seeds, r_seeds)

            # Hybrid direction (probe60 finding: LLM r is near-random on
            # test-condition data; Replogle direct sign is stronger).
            if apply_hybrid_direction:
                from .replogle_prior import ReplogPrior
                # Lazy-init prior; cache via function attr to avoid reload per row
                if not hasattr(assemble_submission, '_prior'):
                    assemble_submission._prior = ReplogPrior()
                r_final, _src = hybrid_direction(
                    r_llm_final, row['pert'], row['gene'],
                    assemble_submission._prior,
                    alpha=hybrid_alpha,
                    non_full_default=hybrid_non_full_default)
            else:
                r_final = r_llm_final
            final_up = q_final * r_final
            final_dn = q_final * (1 - r_final)
            # tokens (sum across seeds)
            tok_json = outputs_dir / 'tokens' / f"{rid}.json"
            if tok_json.exists():
                d = json.loads(tok_json.read_text())
                total_tok = sum(int(d.get(str(s), 0)) for s in seeds)
            else:
                total_tok = 0

            # Per-call prompt_tokens — Kaggle validates against the 4096 cap.
            # Rebuild the shipped prompt for this row and estimate tokens.
            # The LLM-server runner uses the actual GPT-OSS tokenizer; this
            # fallback rough-counts (len(text)//4) is good enough for the
            # offline-built submission CSV column.
            try:
                _prompt_text = build_track_a_prompt(row['pert'], row['gene'])
                _prompt_tokens_per_call = (estimate_tokens(_prompt_text)
                                           + estimate_tokens(_LOCAL_DEV_INSTRUCTIONS))
            except Exception:
                _prompt_tokens_per_call = 0
            _prompt_total = _prompt_tokens_per_call * len(seeds)
            _completion_tokens_per_call = (max(0, total_tok - _prompt_total)
                                           // max(1, len(seeds)))
            out_rows.append({
                'id': rid,
                'prediction_up': round(final_up, 6),
                'prediction_down': round(final_dn, 6),
                'prediction_up_seed42': round(seed_results[42].p_up, 6),
                'prediction_down_seed42': round(seed_results[42].p_down, 6),
                'prediction_up_seed43': round(seed_results[43].p_up, 6),
                'prediction_down_seed43': round(seed_results[43].p_down, 6),
                'prediction_up_seed44': round(seed_results[44].p_up, 6),
                'prediction_down_seed44': round(seed_results[44].p_down, 6),
                'reasoning_trace_seed42': seed_results[42].reasoning or 'none',
                'reasoning_trace_seed43': seed_results[43].reasoning or 'none',
                'reasoning_trace_seed44': seed_results[44].reasoning or 'none',
                'prompt_tokens': _prompt_tokens_per_call,   # per-call (≤4096 cap, what Kaggle validates)
                'completion_tokens': _completion_tokens_per_call,
                'tokens_used': total_tok,                  # sum across all 3 seeds (legacy spec column)
                'model_name': model_name,
            })
    fieldnames = list(out_rows[0].keys())
    with open(out_path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    print(f"Wrote {len(out_rows)} rows -> {out_path}")
    return out_path
