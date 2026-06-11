#!/usr/bin/env python3
"""Validate that a GPT-OSS chat endpoint is applying the Harmony template.

This script compares server-reported `prompt_tokens` against local token counts
from the same gpt-oss tokenizer after rendering the Harmony chat template.

Typical use:

  export LLM_BASE_URL=http://your-vllm-server:8000/v1
  export LLM_API_KEY=dummy
  python scripts/check_gptoss_harmony_server.py --model gpt-oss-120b

Optional:
  --track-a-sample    also probe a real Track-A prompt rendered as a user message
  --local-only        skip the network request and print only local counts
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import openai
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


DEFAULT_LOCAL_MODEL = Path('/workspace/volume/data/yy/gpt-oss-120b')


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='gpt-oss-120b', help='remote model id')
    ap.add_argument('--local-model', type=Path, default=DEFAULT_LOCAL_MODEL,
                    help='local gpt-oss model path used for tokenizer/template checks')
    ap.add_argument('--base-url', default=os.environ.get('LLM_BASE_URL', 'http://localhost:8000/v1'))
    ap.add_argument('--api-key', default=os.environ.get('LLM_API_KEY', 'dummy'))
    ap.add_argument('--timeout', type=int, default=120)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--max-tokens', type=int, default=16,
                    help='small completion cap for the probe request')
    ap.add_argument('--track-a-sample', action='store_true',
                    help='also probe one real Track-A prompt as a user message')
    ap.add_argument('--pert', default='Aars')
    ap.add_argument('--gene', default='Atf4')
    ap.add_argument('--local-only', action='store_true',
                    help='render local token counts only; do not call the server')
    ap.add_argument('--out', type=Path, default=None,
                    help='optional JSON output path')
    return ap.parse_args()


def build_cases(args) -> list[dict]:
    cases = [
        {
            'name': 'user_only_minimal',
            'messages': [
                {
                    'role': 'user',
                    'content': 'Reply with exactly OK and nothing else.',
                }
            ],
            'production_like': True,
        },
        {
            'name': 'developer_plus_user_minimal',
            'messages': [
                {
                    'role': 'developer',
                    'content': (
                        'Reasoning: low\n'
                        'Reply with exactly OK and nothing else.'
                    ),
                },
                {
                    'role': 'user',
                    'content': 'Return exactly: OK',
                },
            ],
            'production_like': False,
        },
    ]

    if args.track_a_sample:
        from pipeline.gene_desc import default as gene_desc_default
        from pipeline.kg_retrieval import KGRetrieval
        from pipeline.prompt_builder_v3 import build_track_a_prompt
        from pipeline.replogle_prior import ReplogPrior
        from pipeline.retrieve_examples import ExampleRetriever

        prior = ReplogPrior()
        kg = KGRetrieval()
        retriever = ExampleRetriever(kg=kg)
        desc = gene_desc_default()
        prompt = build_track_a_prompt(
            args.pert,
            args.gene,
            prior=prior,
            kg=kg,
            retriever=retriever,
            desc=desc,
            exclude_query=False,
            seed=args.seed,
        )
        cases.append(
            {
                'name': f'track_a_sample_{args.pert}_{args.gene}',
                'messages': [{'role': 'user', 'content': prompt}],
                'production_like': True,
            }
        )
    return cases


def local_counts(tokenizer, messages: list[dict]) -> dict:
    rendered = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    rendered_tokens = len(tokenizer.encode(rendered))
    concat_text = '\n\n'.join(str(m.get('content', '')) for m in messages)
    concat_tokens = len(tokenizer.encode(concat_text))
    last_user = next((m['content'] for m in reversed(messages) if m.get('role') == 'user'), '')
    last_user_tokens = len(tokenizer.encode(last_user))
    return {
        'harmony_rendered_tokens': rendered_tokens,
        'plain_concat_tokens': concat_tokens,
        'last_user_tokens': last_user_tokens,
        'rendered_prefix': rendered[:800],
    }


def verdict(local: dict, server_prompt_tokens: int | None) -> str:
    if server_prompt_tokens is None:
        return 'no_usage_reported'
    if server_prompt_tokens == local['harmony_rendered_tokens']:
        return 'match_harmony'
    if server_prompt_tokens == local['last_user_tokens']:
        return 'likely_raw_user_only'
    if server_prompt_tokens == local['plain_concat_tokens']:
        return 'likely_plain_concat_not_harmony'
    return 'mismatch'


def run_remote_case(client, args, case: dict) -> dict:
    req = dict(
        model=args.model,
        messages=case['messages'],
        temperature=1.0,
        top_p=1.0,
        seed=args.seed,
    )
    if args.max_tokens and args.max_tokens > 0:
        req['max_tokens'] = args.max_tokens
    resp = client.chat.completions.create(**req)
    usage = getattr(resp, 'usage', None)
    msg = resp.choices[0].message
    return {
        'content': msg.content or '',
        'prompt_tokens': getattr(usage, 'prompt_tokens', None) if usage else None,
        'completion_tokens': getattr(usage, 'completion_tokens', None) if usage else None,
        'total_tokens': getattr(usage, 'total_tokens', None) if usage else None,
    }


def main():
    args = parse_args()
    if not args.local_model.exists():
        raise SystemExit(f'local model path not found: {args.local_model}')

    tokenizer = AutoTokenizer.from_pretrained(str(args.local_model), trust_remote_code=True)
    cases = build_cases(args)
    results = []

    client = None
    if not args.local_only:
        client = openai.OpenAI(
            api_key=args.api_key,
            base_url=args.base_url,
            timeout=args.timeout,
        )

    print(f'local_model = {args.local_model}')
    if not args.local_only:
        print(f'base_url    = {args.base_url}')
        print(f'remote_model = {args.model}')
    print()

    for case in cases:
        local = local_counts(tokenizer, case['messages'])
        row = {
            'name': case['name'],
            'production_like': case['production_like'],
            'local': local,
        }
        print(f'[{case["name"]}]')
        print(f'  local harmony tokens : {local["harmony_rendered_tokens"]}')
        print(f'  local plain concat   : {local["plain_concat_tokens"]}')
        print(f'  local last user only : {local["last_user_tokens"]}')

        if client is not None:
            try:
                remote = run_remote_case(client, args, case)
                row['remote'] = remote
                row['verdict'] = verdict(local, remote['prompt_tokens'])
                print(f'  server prompt_tokens : {remote["prompt_tokens"]}')
                print(f'  server completion    : {remote["completion_tokens"]}')
                print(f'  verdict              : {row["verdict"]}')
                tail = (remote['content'] or '').strip().splitlines()[-3:]
                if tail:
                    print('  response tail:')
                    for line in tail:
                        print(f'    > {line}')
            except Exception as e:
                row['remote_error'] = repr(e)
                row['verdict'] = 'request_failed'
                print(f'  remote error         : {e}')
        else:
            row['verdict'] = 'local_only'
        print()
        results.append(row)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f'wrote {args.out}')


if __name__ == '__main__':
    main()
