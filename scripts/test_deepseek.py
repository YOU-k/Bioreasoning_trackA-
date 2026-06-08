"""Quick smoke test on DeepSeek reasoner with 6 hand-picked prompts.

Covers: full+strong-KG (1-hop), full+strong-KG (3-hop ISR axis),
        full+weak-Replogle, pert-only, none-tier, full+negative direction.

Reads DEEPSEEK_API_KEY from /data3/yy/key.env.
Saves outputs (reasoning + answer + tokens) under
    attempts/03_kg_celltype/test_deepseek/{id}.json
"""
from __future__ import annotations
import json, os, time
from pathlib import Path
import openai

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / 'attempts/03_kg_celltype/prompts'
OUT_DIR = ROOT / 'attempts/03_kg_celltype/test_deepseek'
KEY_FILE = Path('/data3/yy/key.env')


PICKS = [
    # (id, why)
    ('Actb_Actn1',     'full + DIRECT PPI (1-hop), moderate +logFC'),
    ('Aars_Atf4',      'full + ISR canonical (3-hop via Eif2s1), strong +logFC'),
    ('Ppie_Cat',       'full + weak Replogle (logFC ~ -0.06)'),
    ('Nat10_Sdf2l1',   'full + 2-hop PPI, negative direction (logFC=-0.34)'),
    ('Wdr82_Gm31522',  'pert-only (target is mouse-specific gene)'),
    ('Map3k8_Cdk14',   'none tier (pert has no human ortholog in Replogle)'),
]


def load_key() -> str:
    for line in KEY_FILE.read_text().splitlines():
        if line.startswith('DEEPSEEK_API_KEY='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('DEEPSEEK_API_KEY not found in /data3/yy/key.env')


def run_one(client, prompt_text: str, model: str, max_tokens: int):
    t0 = time.time()
    resp = client.chat.completions.create(
        model=model,
        messages=[{'role': 'user', 'content': prompt_text}],
        max_tokens=max_tokens,
    )
    elapsed = time.time() - t0
    msg = resp.choices[0].message
    return {
        'elapsed_sec': round(elapsed, 1),
        'reasoning_content': getattr(msg, 'reasoning_content', '') or '',
        'content': msg.content or '',
        'prompt_tokens': getattr(resp.usage, 'prompt_tokens', None),
        'completion_tokens': getattr(resp.usage, 'completion_tokens', None),
        'reasoning_tokens': getattr(getattr(resp.usage, 'completion_tokens_details', None),
                                   'reasoning_tokens', None),
        'total_tokens': getattr(resp.usage, 'total_tokens', None),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    api_key = load_key()
    client = openai.OpenAI(
        api_key=api_key,
        base_url='https://api.deepseek.com/v1',
        timeout=600,
    )
    model = 'deepseek-reasoner'

    print(f'model = {model}')
    print(f'output dir = {OUT_DIR}')
    print()

    for rid, why in PICKS:
        prompt_path = PROMPTS_DIR / f'{rid}.txt'
        if not prompt_path.exists():
            print(f'[skip] {rid} -- prompt file missing')
            continue
        out_path = OUT_DIR / f'{rid}.json'
        if out_path.exists():
            print(f'[skip] {rid} -- already done')
            continue
        prompt = prompt_path.read_text()
        prompt_chars = len(prompt)
        print(f'[run]  {rid:<22} ({why})')
        print(f'       prompt chars={prompt_chars} (~{prompt_chars//4} tokens)')
        try:
            result = run_one(client, prompt, model, max_tokens=2000)
        except Exception as e:
            print(f'       ERROR: {e}')
            continue
        result['id'] = rid
        result['why'] = why
        result['prompt'] = prompt
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        ans_tail = result['content'].strip().splitlines()[-3:] if result['content'].strip() else []
        print(f'       elapsed={result["elapsed_sec"]}s  '
              f'prompt_tok={result["prompt_tokens"]}  '
              f'reasoning_tok={result["reasoning_tokens"]}  '
              f'answer_tok={result["completion_tokens"]}')
        for line in ans_tail:
            print(f'       > {line}')
        print()


if __name__ == '__main__':
    main()
