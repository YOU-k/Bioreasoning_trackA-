"""End-to-end Track A scaffolding:
   1. build_all_prompts(test.csv)            → 1813 prompt strings
   2. (external) run GPT-OSS-120B × 3 seeds per prompt
   3. assemble_submission(outputs)           → submission.csv + zip

This module does NOT call any LLM directly — it only builds prompts and
assembles outputs. Inference is left to the user's GPU/API call.
"""
from __future__ import annotations
import csv, json, os, time
from pathlib import Path
from .replogle_prior import ReplogPrior
from .prompt_builder import build_prompt, estimate_tokens
from .output_parser import parse

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
                        model_name: str = 'gpt-oss-120b'):
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
            # Per Track A spec: final prediction = mean of the per-seed
            # prediction_up / prediction_down columns directly.
            final_up = sum(seed_results[s].p_up for s in seeds) / len(seeds)
            final_dn = sum(seed_results[s].p_down for s in seeds) / len(seeds)
            # tokens (sum across seeds)
            tok_json = outputs_dir / 'tokens' / f"{rid}.json"
            if tok_json.exists():
                d = json.loads(tok_json.read_text())
                total_tok = sum(int(d.get(str(s), 0)) for s in seeds)
            else:
                total_tok = 0
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
                'tokens_used': total_tok,
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
