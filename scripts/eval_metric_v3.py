"""Attempt-05 validation: paper-faithful analog+contrast retrieval on the
same 60 random train rows (seed=123) used to grade attempts 03 / 04.

Differs from eval_metric_v2.py only in output directory and default max_tokens
(attempt 04 hit the 3000 cap on 9/60 DIR calls).
"""
from __future__ import annotations
import argparse, asyncio, csv, json, random, sys, time
from pathlib import Path
import openai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.prompt_builder_v2 import build_de_prompt, build_dir_prompt
from pipeline.replogle_prior import ReplogPrior
from pipeline.kg_retrieval import KGRetrieval
from pipeline.retrieve_examples import ExampleRetriever
from pipeline.gene_desc import default as gene_desc_default
from pipeline.output_parser import parse

KEY_FILE = Path('/data3/yy/key.env')
OUT_DIR = ROOT / 'attempts/05_paper_faithful/outputs/eval60'


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


async def run_one(sem, client, task_kind, row, prompt, max_tokens):
    rid = row['id']
    out_path = OUT_DIR / task_kind / f'{rid}.json'
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
            return {'id': rid, 'true_label': row['label'], 'task': task_kind, 'error': str(e)}
        elapsed = time.time() - t0
    msg = resp.choices[0].message
    u = resp.usage
    parsed = parse(msg.content or '')
    rec = {
        'id': rid,
        'task': task_kind,
        'true_label': row['label'],
        'elapsed_sec': round(elapsed, 1),
        'prompt_tokens': u.prompt_tokens,
        'completion_tokens': u.completion_tokens,
        'reasoning_tokens': getattr(getattr(u, 'completion_tokens_details', None),
                                    'reasoning_tokens', None),
        'content': msg.content or '',
        'reasoning_content': getattr(msg, 'reasoning_content', '') or '',
        'parsed': {
            'P_DE': int(round(parsed.p_de * 100)) if task_kind == 'de' else None,
            'P_up_given_DE': int(round(parsed.p_up_given_de * 100)) if task_kind == 'dir' else None,
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = openai.AsyncOpenAI(
        api_key=load_key(), base_url='https://api.deepseek.com/v1', timeout=600,
    )

    prior = ReplogPrior()
    kg = KGRetrieval()
    retriever = ExampleRetriever(kg=kg)
    desc = gene_desc_default()

    picks = pick_random(args.n, args.seed)
    print(f'sampled {len(picks)} random train rows (seed={args.seed})')
    print(f'  label dist: '
          f'up={sum(1 for r in picks if r["label"]=="up")}  '
          f'down={sum(1 for r in picks if r["label"]=="down")}  '
          f'none={sum(1 for r in picks if r["label"]=="none")}')
    print()

    tasks = []
    for row in picks:
        pert, gene = row['pert'], row['gene']
        de_prompt = build_de_prompt(pert, gene, prior=prior, kg=kg,
                                    retriever=retriever, desc=desc,
                                    exclude_query=True, seed=42)
        dir_prompt = build_dir_prompt(pert, gene, prior=prior, kg=kg,
                                      retriever=retriever, desc=desc,
                                      exclude_query=True, seed=42)
        tasks.append(('de', row, de_prompt))
        tasks.append(('dir', row, dir_prompt))

    print(f'queued {len(tasks)} calls (2 per row, concurrency={args.concurrency}, '
          f'max_tokens={args.max_tokens})')

    sem = asyncio.Semaphore(args.concurrency)
    futures = [run_one(sem, client, kind, row, prompt, args.max_tokens)
               for kind, row, prompt in tasks]

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

    de_by_id = {r['id']: r for r in results if r.get('task') == 'de'}
    dir_by_id = {r['id']: r for r in results if r.get('task') == 'dir'}

    rows = []
    for row in picks:
        rid = row['id']
        de = de_by_id.get(rid, {})
        dr = dir_by_id.get(rid, {})
        p_de = de.get('parsed', {}).get('P_DE')
        p_up_c = dr.get('parsed', {}).get('P_up_given_DE')
        de_status = de.get('parsed', {}).get('parse_status', 'missing')
        dir_status = dr.get('parsed', {}).get('parse_status', 'missing')
        rows.append({
            'id': rid,
            'true': row['label'],
            'P_DE': p_de,
            'P_up_given_DE': p_up_c,
            'de_status': de_status,
            'dir_status': dir_status,
        })

    print()
    print('=== Per-row results ===')
    print(f'{"id":<28} {"true":<5} {"P_DE":>5} {"P_up":>5} de/dir status')
    for r in rows:
        pde = '?' if r['P_DE'] is None else str(r['P_DE'])
        pup = '?' if r['P_up_given_DE'] is None else str(r['P_up_given_DE'])
        print(f'{r["id"]:<28} {r["true"]:<5} {pde:>5} {pup:>5} '
              f'{r["de_status"]}/{r["dir_status"]}')

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
    print('  Attempt 03 (one prompt, KG+celltype):  DE=0.654 DIR=0.451 COMBINED=0.552')
    print('  Attempt 04 (two prompts, RANDOM lbl):  DE=0.601 DIR=0.679 COMBINED=0.640')


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=60)
    ap.add_argument('--seed', type=int, default=123)
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--max-tokens', type=int, default=6000)
    return ap.parse_args()


if __name__ == '__main__':
    asyncio.run(main_async(parse_args()))
