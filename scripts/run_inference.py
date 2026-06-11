"""Run GPT-OSS-120B over the 1813 question-specific prompts × 3 seeds.

This path assumes an OpenAI-compatible chat endpoint that already applies the
model's native Harmony/chat template for gpt-oss. Track A's 4,096-token limit
applies to the INPUT PROMPT only; `max_tokens` here is purely a completion cap.

Saves outputs as:

  outputs/{seed}/{id}.txt        raw LLM completion text
  outputs/tokens/{id}.json       {"42": n_42, "43": n_43, "44": n_44}

Resumes automatically: existing output files are skipped.

Track A rules enforced:
  - temperature = 1.0, top_p = 1.0  (binding per competition rules)
  - seeds 42, 43, 44
  - Each prompt ≤ 4,096 input tokens (build_prompt enforces budget)

Usage (assuming vLLM-style server with OpenAI-compatible API):
  export LLM_BASE_URL=http://your-server:8000/v1
  export LLM_API_KEY=anything
  python scripts/run_inference.py --model gpt-oss-120b --concurrency 8
"""
from __future__ import annotations
import argparse, asyncio, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / 'attempts/12_cleaner_prompt/prompts'
DEFAULT_OUT = ROOT / 'attempts/12_cleaner_prompt/outputs'


async def run_one(client, model, prompt_text, seed, max_tokens):
    """Single completion call. Returns (text, tokens_used)."""
    try:
        req = dict(
            model=model,
            messages=[{'role': 'user', 'content': prompt_text}],
            temperature=1.0,
            top_p=1.0,
            seed=seed,
        )
        if max_tokens and max_tokens > 0:
            req['max_tokens'] = max_tokens
        resp = await client.chat.completions.create(**req)
        text = resp.choices[0].message.content or ''
        toks = (getattr(resp.usage, 'total_tokens', 0)
                if resp.usage else 0)
        return text, toks
    except Exception as e:
        return f'ERROR: {e}', 0


async def worker(name, queue, client, model, max_tokens, out_dir, tokens_dir, seed_keys):
    """Pull (id, prompt_path) from queue, run all seeds, save outputs."""
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break
        rid, prompt_path = item
        prompt_text = Path(prompt_path).read_text()
        # tokens_used aggregator
        toks = {}
        try:
            old = json.loads((tokens_dir / f'{rid}.json').read_text())
            toks.update({str(k): int(v) for k, v in old.items()})
        except Exception:
            pass
        for seed in seed_keys:
            seed_dir = out_dir / str(seed)
            seed_dir.mkdir(parents=True, exist_ok=True)
            out_path = seed_dir / f'{rid}.txt'
            if out_path.exists() and out_path.stat().st_size > 0:
                continue
            text, t = await run_one(client, model, prompt_text, seed, max_tokens)
            out_path.write_text(text)
            toks[str(seed)] = int(t)
        (tokens_dir / f'{rid}.json').write_text(json.dumps(toks))
        queue.task_done()


async def main_async(args):
    import openai
    client = openai.AsyncOpenAI(
        base_url=os.environ.get('LLM_BASE_URL', 'http://localhost:8000/v1'),
        api_key=os.environ.get('LLM_API_KEY', 'dummy'),
        timeout=args.timeout,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    tokens_dir = out_dir / 'tokens'
    tokens_dir.mkdir(exist_ok=True)

    prompts = sorted(PROMPTS_DIR.glob('*.txt'))
    if args.limit:
        prompts = prompts[: args.limit]
    print(f'queueing {len(prompts)} prompts × {len(args.seeds)} seeds = '
          f'{len(prompts) * len(args.seeds)} calls')

    queue: asyncio.Queue = asyncio.Queue()
    for p in prompts:
        rid = p.stem
        queue.put_nowait((rid, str(p)))

    workers = [
        asyncio.create_task(
            worker(f'w{i}', queue, client, args.model, args.max_tokens,
                   out_dir, tokens_dir, args.seeds)
        )
        for i in range(args.concurrency)
    ]
    for _ in range(args.concurrency):
        queue.put_nowait(None)

    t0 = time.time()
    last_report = t0
    while True:
        done = sum(
            1 for p in prompts
            if all((out_dir / str(s) / f'{p.stem}.txt').exists() for s in args.seeds)
        )
        if done == len(prompts):
            break
        if time.time() - last_report > args.report_every:
            print(f'  [t={time.time()-t0:.0f}s] {done}/{len(prompts)} prompts complete')
            last_report = time.time()
        await asyncio.sleep(5)

    await queue.join()
    for w in workers:
        w.cancel()
    print(f'all done in {time.time()-t0:.0f}s')


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True, help='model id understood by the endpoint')
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 43, 44])
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument(
        '--max-tokens', type=int, default=0,
        help=('optional completion cap only; 0 disables the explicit cap. '
              'Track A limits prompt tokens, not response tokens')
    )
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--report-every', type=int, default=30, help='seconds between progress prints')
    ap.add_argument('--limit', type=int, default=0, help='for smoke test: only run first N prompts')
    ap.add_argument('--out', type=str, default=str(DEFAULT_OUT))
    return ap.parse_args()


if __name__ == '__main__':
    asyncio.run(main_async(parse_args()))
