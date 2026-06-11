"""Track-A single-call eval. Output dir is parameterized by --out-attempt.

Used by attempt 06 (--out-attempt 06_track_a_single_call) and
attempt 07 (--out-attempt 07_no_anchors). One LLM call per (pert, gene)
emits BOTH integers (P_DE + P_up_given_DE).
"""
from __future__ import annotations
import argparse, asyncio, csv, json, random, sys, time
from pathlib import Path
import openai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.prompt_builder_v3 import build_track_a_prompt
from pipeline.replogle_prior import ReplogPrior
from pipeline.kg_retrieval import KGRetrieval
from pipeline.retrieve_examples import ExampleRetriever
from pipeline.gene_desc import default as gene_desc_default
from pipeline.output_parser import parse

KEY_FILE = Path('/data3/yy/key.env')
# OUT_DIR is set in main_async from --out-attempt


def load_key() -> str:
    for line in KEY_FILE.read_text().splitlines():
        if line.startswith('DEEPSEEK_API_KEY='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('no key')


def pick_random(n: int, seed: int):
    rng = random.Random(seed)
    rows = list(csv.DictReader(open(ROOT / 'data/train.csv')))
    rng.shuffle(rows)
    return rows[:n]


def pick_rare_gene(n: int, seed: int, label_targets=(23, 12, 25)):
    """Sample n train rows where the readout gene appears 2-4x in train
    (test-mimic on the gene axis). Stratify labels (up, down, none) to
    `label_targets` for apples-to-apples vs eval60 (default 23/12/25)."""
    from collections import Counter
    rows = list(csv.DictReader(open(ROOT / 'data/train.csv')))
    gene_count = Counter(r['gene'] for r in rows)
    candidates = [r for r in rows if 2 <= gene_count[r['gene']] <= 4]
    by_label = {'up': [], 'down': [], 'none': []}
    for r in candidates:
        by_label[r['label']].append(r)
    rng = random.Random(seed)
    for lbl in by_label:
        rng.shuffle(by_label[lbl])
    n_up, n_down, n_none = label_targets
    picks = (by_label['up'][:n_up] + by_label['down'][:n_down]
             + by_label['none'][:n_none])
    rng.shuffle(picks)
    return picks


async def run_one(sem, client, row, prompt, max_tokens, out_dir):
    rid = row['id']
    out_path = out_dir / 'single' / f'{rid}.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        return json.loads(out_path.read_text())
    async with sem:
        t0 = time.time()
        try:
            resp = await client.chat.completions.create(
                model='deepseek-reasoner',
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=max_tokens,
            )
        except Exception as e:
            return {'id': rid, 'true_label': row['label'], 'error': str(e)}
        elapsed = time.time() - t0
    msg = resp.choices[0].message
    u = resp.usage
    parsed = parse(msg.content or '')
    rec = {
        'id': rid,
        'true_label': row['label'],
        'elapsed_sec': round(elapsed, 1),
        'prompt_tokens': u.prompt_tokens,
        'completion_tokens': u.completion_tokens,
        'reasoning_tokens': getattr(getattr(u, 'completion_tokens_details', None),
                                    'reasoning_tokens', None),
        'content': msg.content or '',
        'reasoning_content': getattr(msg, 'reasoning_content', '') or '',
        'parsed': {
            'P_DE': int(round(parsed.p_de * 100)),
            'P_up_given_DE': int(round(parsed.p_up_given_de * 100)),
            'parse_status': parsed.parse_status,
        },
    }
    out_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec


def auroc(y, s):
    pos = [s[i] for i in range(len(y)) if y[i] == 1]
    neg = [s[i] for i in range(len(y)) if y[i] == 0]
    if not pos or not neg: return None
    h = 0.0
    for p in pos:
        for q in neg:
            if p > q: h += 1
            elif p == q: h += 0.5
    return h / (len(pos) * len(neg))


async def main_async(args):
    out_dir = ROOT / f'attempts/{args.out_attempt}/outputs/{args.probe_subdir}'
    out_dir.mkdir(parents=True, exist_ok=True)
    client = openai.AsyncOpenAI(
        api_key=load_key(), base_url='https://api.deepseek.com/v1', timeout=600,
    )
    print(f'output dir: {out_dir}')

    prior = ReplogPrior()
    kg = KGRetrieval()
    retriever = ExampleRetriever(kg=kg)
    desc = gene_desc_default()

    if args.probe == 'random':
        picks = pick_random(args.n, args.seed)
        print(f'sampled {len(picks)} random train rows (seed={args.seed})')
    elif args.probe == 'rare_gene':
        picks = pick_rare_gene(args.n, args.seed)
        print(f'sampled {len(picks)} rare-gene train rows '
              f'(seed={args.seed}, gene appears 2-4x in train)')
    else:
        raise SystemExit(f'unknown probe: {args.probe!r}')
    print(f'  label dist: '
          f'up={sum(1 for r in picks if r["label"]=="up")}  '
          f'down={sum(1 for r in picks if r["label"]=="down")}  '
          f'none={sum(1 for r in picks if r["label"]=="none")}')
    print()

    tasks = []
    for row in picks:
        prompt = build_track_a_prompt(
            row['pert'], row['gene'], prior=prior, kg=kg,
            retriever=retriever, desc=desc,
            exclude_query=True, seed=42,
            k_a=args.k_a, k_c=args.k_c,
            include_bmdm_context=args.with_bmdm_context,
            include_decision_rules=not args.no_decision_rules,
            include_reasoning_protocol=not args.no_reasoning_protocol,
            enrich_examples=args.enrich_examples,
            hide_example_labels=args.hide_example_labels)
        tasks.append((row, prompt))

    print(f'queued {len(tasks)} calls (1 per row, concurrency={args.concurrency}, '
          f'max_tokens={args.max_tokens})')

    sem = asyncio.Semaphore(args.concurrency)
    futures = [run_one(sem, client, row, prompt, args.max_tokens, out_dir)
               for row, prompt in tasks]

    t0 = time.time()
    done = 0
    results = []
    for fut in asyncio.as_completed(futures):
        rec = await fut
        results.append(rec)
        done += 1
        if done % 10 == 0 or done == len(futures):
            print(f'  [{done}/{len(futures)}] t={time.time()-t0:.0f}s')
    print(f'all done in {time.time()-t0:.0f}s')

    by_id = {r['id']: r for r in results}
    rows = []
    for row in picks:
        rec = by_id.get(row['id'], {})
        parsed = rec.get('parsed', {})
        rows.append({
            'id': row['id'],
            'true': row['label'],
            'P_DE': parsed.get('P_DE'),
            'P_up_given_DE': parsed.get('P_up_given_DE'),
            'status': parsed.get('parse_status', 'missing'),
        })

    print()
    print('=== Per-row results ===')
    print(f'{"id":<28} {"true":<5} {"P_DE":>5} {"P_up":>5} status')
    for r in rows:
        pde = '?' if r['P_DE'] is None else str(r['P_DE'])
        pup = '?' if r['P_up_given_DE'] is None else str(r['P_up_given_DE'])
        print(f'{r["id"]:<28} {r["true"]:<5} {pde:>5} {pup:>5} {r["status"]}')

    valid = [r for r in rows if r['P_DE'] is not None and r['P_up_given_DE'] is not None]
    print()
    print(f'valid rows for metric: {len(valid)}/{len(rows)}')

    y_de = [1 if r['true'] in ('up', 'down') else 0 for r in valid]
    s_de = [r['P_DE'] / 100 for r in valid]
    de_auc = auroc(y_de, s_de)

    dir_rows = [r for r in valid if r['true'] in ('up', 'down')]
    y_dir = [1 if r['true'] == 'up' else 0 for r in dir_rows]
    s_dir = [r['P_up_given_DE'] / 100 for r in dir_rows]
    drc = auroc(y_dir, s_dir)

    print()
    print('=== METRIC ===')
    print(f'DE-AUROC  = {de_auc:.3f}  (n_pos={sum(y_de)}, n_neg={len(y_de) - sum(y_de)})')
    if drc is not None:
        print(f'DIR-AUROC = {drc:.3f}  (n_pos={sum(y_dir)}, n_neg={len(y_dir) - sum(y_dir)})')
        print(f'COMBINED  = {(de_auc + drc) / 2:.3f}')
    print()
    print('=== Reference on same 60 rows ===')
    print('  Attempt 03 (one prompt, KG+celltype):       DE=0.654 DIR=0.451 COMBINED=0.552')
    print('  Attempt 04 (two prompts, RANDOM labels):    DE=0.601 DIR=0.679 COMBINED=0.640')
    print('  Attempt 05 (two prompts, REAL labels):      DE=0.610 DIR=0.665 COMBINED=0.637')
    print('  Attempt 06 (single call + prescr. anchors): DE=0.559 DIR=0.611 COMBINED=0.585')


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=60)
    ap.add_argument('--seed', type=int, default=123)
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--max-tokens', type=int, default=6000)
    ap.add_argument('--out-attempt', type=str, default='07_no_anchors',
                    help='attempt folder under attempts/ to write outputs to')
    ap.add_argument('--probe', choices=['random', 'rare_gene'], default='random',
                    help='which sample to use')
    ap.add_argument('--probe-subdir', type=str, default='eval60',
                    help='subfolder under outputs/ for this probe (e.g. eval60, probe60)')
    ap.add_argument('--with-bmdm-context', action='store_true',
                    help='include the 723-token BMDM cell context paragraph '
                         '(A12 finding: dropping it lifts probe60 Combined; off by default)')
    ap.add_argument('--no-decision-rules', action='store_true',
                    help='ablate the R1-R5 Decision rules block (~250 tokens)')
    ap.add_argument('--no-reasoning-protocol', action='store_true',
                    help='ablate the A1-B2 step-by-step reasoning protocol (~200 tokens)')
    ap.add_argument('--enrich-examples', action='store_true',
                    help='render each evidence case with inline Hagai |logFC| + Replogle logFC')
    ap.add_argument('--k-a', type=int, default=5,
                    help='# of analog examples (DE-observed pairs); current ship=5')
    ap.add_argument('--k-c', type=int, default=5,
                    help='# of contrast examples (DE-not-observed pairs); current ship=5')
    ap.add_argument('--hide-example-labels', action='store_true',
                    help='Test α: render evidence cases without their Result line')
    return ap.parse_args()


if __name__ == '__main__':
    asyncio.run(main_async(parse_args()))
