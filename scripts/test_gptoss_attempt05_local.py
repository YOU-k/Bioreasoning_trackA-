#!/usr/bin/env python3
"""Local GPT-OSS smoke test for Attempt 05 prompts.

Builds one DE prompt and one DIR prompt for a single (pert, gene) pair,
runs them once each through local vLLM GPT-OSS-120B, and saves prompts +
raw outputs under attempts/05_paper_faithful/outputs/smoke_local/.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

from pipeline.gene_desc import default as gene_desc_default
from pipeline.kg_retrieval import KGRetrieval
from pipeline.output_parser import parse
from pipeline.prompt_builder_v2 import build_de_prompt, build_dir_prompt
from pipeline.replogle_prior import ReplogPrior
from pipeline.retrieve_examples import ExampleRetriever


DEFAULT_MODEL = Path('/workspace/volume/data/yy/gpt-oss-120b')
DEFAULT_OUT = ROOT / 'attempts/05_paper_faithful/outputs/smoke_local'
PATTERNS = {
    'de': re.compile(r'P_?DE\s*[:=]\s*([0-9]{1,3})', re.IGNORECASE),
    'dir': re.compile(r'P_?up_?given_?DE\s*[:=]\s*([0-9]{1,3})', re.IGNORECASE),
}


def build_prompts(pert: str, gene: str) -> dict[str, str]:
    prior = ReplogPrior()
    kg = KGRetrieval()
    retriever = ExampleRetriever(kg=kg)
    desc = gene_desc_default()
    return {
        'de': build_de_prompt(
            pert, gene, prior=prior, kg=kg, retriever=retriever,
            desc=desc, exclude_query=False, seed=42,
        ),
        'dir': build_dir_prompt(
            pert, gene, prior=prior, kg=kg, retriever=retriever,
            desc=desc, exclude_query=False, seed=42,
        ),
    }


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pert', default='Aars')
    ap.add_argument('--gene', default='Atf4')
    ap.add_argument('--model', type=Path, default=DEFAULT_MODEL)
    ap.add_argument('--out-dir', type=Path, default=DEFAULT_OUT)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--max-model-len', type=int, default=4096)
    ap.add_argument('--max-tokens', type=int, default=1200)
    ap.add_argument('--gpu-memory-utilization', type=float, default=0.92)
    ap.add_argument('--tensor-parallel-size', type=int, default=1)
    return ap.parse_args()


def main():
    args = parse_args()
    if not args.model.exists():
        raise SystemExit(f'model path not found: {args.model}')

    out_dir = args.out_dir / f'{args.pert}_{args.gene}'
    out_dir.mkdir(parents=True, exist_ok=True)

    prompts = build_prompts(args.pert, args.gene)
    tok = AutoTokenizer.from_pretrained(str(args.model), trust_remote_code=True)
    for kind, prompt in prompts.items():
        n_tok = len(tok(prompt)['input_ids'])
        print(f'{kind} input_tokens={n_tok}')
        (out_dir / f'{kind}_prompt.txt').write_text(prompt)

    os.environ.pop('LD_PRELOAD', None)
    os.environ['VLLM_WORKER_MULTIPROC_METHOD'] = 'spawn'
    os.environ['PYTORCH_ALLOC_CONF'] = 'expandable_segments:True'

    llm = LLM(
        model=str(args.model),
        trust_remote_code=True,
        quantization='mxfp4',
        kv_cache_dtype='fp8',
        gpu_memory_utilization=args.gpu_memory_utilization,
        max_model_len=args.max_model_len,
        tensor_parallel_size=args.tensor_parallel_size,
        max_num_seqs=1,
        dtype='bfloat16',
    )
    sampling = SamplingParams(
        temperature=1.0,
        top_p=1.0,
        seed=args.seed,
        max_tokens=args.max_tokens,
    )

    t0 = time.time()
    outputs = llm.generate([prompts['de'], prompts['dir']], sampling)
    elapsed = round(time.time() - t0, 1)
    print(f'elapsed_sec={elapsed}')

    summary = {
        'pert': args.pert,
        'gene': args.gene,
        'seed': args.seed,
        'elapsed_sec': elapsed,
        'max_model_len': args.max_model_len,
        'max_tokens': args.max_tokens,
        'tensor_parallel_size': args.tensor_parallel_size,
        'results': {},
    }

    for kind, output in zip(['de', 'dir'], outputs):
        text = output.outputs[0].text
        out_tok = len(output.outputs[0].token_ids)
        parsed = parse(text)
        match = PATTERNS[kind].search(text)
        extracted = int(match.group(1)) if match else None

        (out_dir / f'{kind}_output.txt').write_text(text)
        summary['results'][kind] = {
            'output_tokens': out_tok,
            'parse_status': parsed.parse_status,
            'extracted_value': extracted,
            'tail': text.rstrip().splitlines()[-10:],
        }

        print(f'== {kind.upper()} ==')
        print(f'output_tokens={out_tok}')
        print(f'parse_status={parsed.parse_status}')
        print(f'extracted_value={extracted}')
        print('last_10_lines:')
        for line in summary['results'][kind]['tail']:
            print(line)
        print('---')

    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
