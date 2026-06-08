"""Sample N random train rows, run DeepSeek, compute competition metric.

Metric = (DE-AUROC + DIR-AUROC) / 2
  - DE-AUROC : binary up|down vs none; score = P_DE / 100
  - DIR-AUROC: binary up vs down on DE rows; score = P_up_given_DE / 100

Outputs to attempts/03_kg_celltype/test_deepseek_v2/eval_metric/{id}.json
Reads DEEPSEEK_API_KEY from /data3/yy/key.env.
"""
from __future__ import annotations
import argparse, asyncio, csv, json, random, sys, time
from pathlib import Path
import openai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.prompt_builder import build_prompt
from pipeline.replogle_prior import ReplogPrior
from pipeline.kg_retrieval import KGRetrieval
from pipeline.output_parser import parse

OUT_DIR = ROOT / 'attempts/03_kg_celltype/test_deepseek_v2/eval_metric'
KEY_FILE = Path('/data3/yy/key.env')


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


async def run_one(sem, client, row, prior, kg, max_tokens):
    rid = row['id']
    out_path = OUT_DIR / f'{rid}.json'
    if out_path.exists():
        return json.loads(out_path.read_text())
    pert, gene = row['pert'], row['gene']
    prompt = build_prompt(pert, gene, prior=prior, kg=kg, use_kg=True)
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
        'id': rid, 'true_label': row['label'],
        'elapsed_sec': round(elapsed, 1),
        'prompt_tokens': u.prompt_tokens,
        'reasoning_tokens': getattr(getattr(u, 'completion_tokens_details', None),
                                    'reasoning_tokens', None),
        'completion_tokens': u.completion_tokens,
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
    if not pos or not neg:
        return None
    hits = 0.0
    for p in pos:
        for q in neg:
            if p > q: hits += 1
            elif p == q: hits += 0.5
    return hits / (len(pos) * len(neg))


def report(rows, label_prefix=''):
    valid = [r for r in rows if r.get('parsed', {}).get('parse_status') == 'ok']
    n_failed = len(rows) - len(valid)
    print(f'{label_prefix}evaluable rows: {len(valid)}/{len(rows)}  (parse-fails: {n_failed})')
    tally = {'up': 0, 'down': 0, 'none': 0}
    for r in valid:
        tally[r['true_label']] += 1
    print(f'{label_prefix}true labels: up={tally["up"]}  down={tally["down"]}  none={tally["none"]}')

    y_de = [1 if r['true_label'] in ('up', 'down') else 0 for r in valid]
    s_de = [r['parsed']['P_DE'] / 100 for r in valid]
    de = auroc(y_de, s_de)

    dir_rows = [r for r in valid if r['true_label'] in ('up', 'down')]
    y_dir = [1 if r['true_label'] == 'up' else 0 for r in dir_rows]
    s_dir = [r['parsed']['P_up_given_DE'] / 100 for r in dir_rows]
    drc = auroc(y_dir, s_dir)

    print(f'{label_prefix}DE-AUROC  = {de:.3f}  (n_pos={sum(y_de)}, n_neg={len(y_de)-sum(y_de)})')
    if drc is not None:
        print(f'{label_prefix}DIR-AUROC = {drc:.3f}  (n_pos={sum(y_dir)}, n_neg={len(y_dir)-sum(y_dir)})')
        print(f'{label_prefix}COMBINED  = {(de + drc) / 2:.3f}')
    else:
        print(f'{label_prefix}DIR-AUROC: too few up/down samples')


async def main_async(args):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = openai.AsyncOpenAI(
        api_key=load_key(), base_url='https://api.deepseek.com/v1', timeout=600,
    )
    prior, kg = ReplogPrior(), KGRetrieval()
    picks = pick_random(args.n, args.seed)
    print(f'sampled {len(picks)} random train rows (seed={args.seed})')
    print(f'  label dist: up={sum(1 for r in picks if r["label"]=="up")}  '
          f'down={sum(1 for r in picks if r["label"]=="down")}  '
          f'none={sum(1 for r in picks if r["label"]=="none")}')
    print(f'concurrency={args.concurrency}, max_tokens={args.max_tokens}')
    print()

    sem = asyncio.Semaphore(args.concurrency)
    t0 = time.time()
    tasks = [run_one(sem, client, row, prior, kg, args.max_tokens) for row in picks]
    done = 0
    results = []
    for fut in asyncio.as_completed(tasks):
        rec = await fut
        results.append(rec)
        done += 1
        if done % 5 == 0 or done == len(tasks):
            print(f'  [{done}/{len(tasks)}] t={time.time()-t0:.0f}s')
    print(f'all done in {time.time()-t0:.0f}s')

    print()
    print('=== METRIC ON THIS RANDOM SAMPLE ===')
    report(results, '  ')

    # also pool with existing stratified 15 if present
    strat_dir = ROOT / 'attempts/03_kg_celltype/test_deepseek_v2/train_gt'
    if strat_dir.exists():
        strat = []
        for f in sorted(strat_dir.glob('*.json')):
            d = json.loads(f.read_text())
            strat.append(d)
        if strat:
            print()
            print('=== METRIC ON POOLED (random + earlier stratified 15) ===')
            report(results + strat, '  ')


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=60)
    ap.add_argument('--seed', type=int, default=123)
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--max-tokens', type=int, default=3000)
    return ap.parse_args()


if __name__ == '__main__':
    asyncio.run(main_async(parse_args()))
