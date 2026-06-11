#!/usr/bin/env python3
"""Local GPT-OSS inference for Track-A compliant single-call prompt.

Uses gpt-oss through its Harmony chat template by default. Track A's 4,096
token rule applies to the input prompt only; completion length is not the same
constraint and is treated here as an optional safety cap.

Writes:
  <out>/<seed>/<id>.txt
  <out>/tokens/<id>.json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

from pipeline.gene_desc import default as gene_desc_default
from pipeline.kg_retrieval import KGRetrieval
from pipeline.prompt_builder_v3 import build_track_a_prompt
from pipeline.replogle_prior import ReplogPrior
from pipeline.retrieve_examples import ExampleRetriever


DEFAULT_MODEL = Path('/workspace/volume/data/yy/gpt-oss-120b')
DEFAULT_OUT = ROOT / 'attempts/12_cleaner_prompt/outputs/local_vllm'
DEVELOPER_INSTRUCTIONS = (
    "Reasoning: low\n"
    "Follow the user's instructions exactly.\n"
    "Do not reveal scratch work, drafts, or chain-of-thought.\n"
    "Write only the final answer block requested by the user.\n"
    "Stop immediately after the final numeric line."
)


def batch_items(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def load_tokens(path: Path) -> dict[str, int]:
    try:
        data = json.loads(path.read_text())
        return {str(k): int(v) for k, v in data.items()}
    except Exception:
        return {}


def save_tokens(path: Path, data: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', type=Path, default=DEFAULT_MODEL)
    ap.add_argument('--out', type=Path, default=DEFAULT_OUT)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 43, 44])
    ap.add_argument(
        '--max-model-len', type=int, default=3072,
        help='runtime context window for local vLLM; Track A still separately limits prompt tokens to 4096'
    )
    ap.add_argument(
        '--max-tokens', type=int, default=0,
        help='optional completion cap only; 0 disables the explicit cap'
    )
    ap.add_argument('--gpu-memory-utilization', type=float, default=0.70)
    ap.add_argument('--tensor-parallel-size', type=int, default=2)
    ap.add_argument('--max-num-seqs', type=int, default=1)
    ap.add_argument('--mode', choices=['raw', 'chat'], default='chat')
    ap.add_argument(
        '--enforce-eager',
        action='store_true',
        default=True,
        help='disable torch.compile/CUDAGraphs for more reliable local gpt-oss startup'
    )
    ap.add_argument(
        '--no-enforce-eager',
        dest='enforce_eager',
        action='store_false',
        help='re-enable compile/CUDAGraph path'
    )
    return ap.parse_args()


def build_jobs(limit: int):
    prior = ReplogPrior()
    kg = KGRetrieval()
    retriever = ExampleRetriever(kg=kg)
    desc = gene_desc_default()

    rows = list(csv.DictReader(open(ROOT / 'data' / 'test.csv')))
    if limit:
        rows = rows[:limit]

    jobs = []
    for row in rows:
        rid, pert, gene = row['id'], row['pert'], row['gene']
        jobs.append({
            'id': rid,
            'prompt': build_track_a_prompt(
                pert, gene, prior=prior, kg=kg, retriever=retriever,
                desc=desc, exclude_query=False, seed=42,
            ),
            'messages': [
                {'role': 'developer', 'content': DEVELOPER_INSTRUCTIONS},
                {'role': 'user', 'content': build_track_a_prompt(
                    pert, gene, prior=prior, kg=kg, retriever=retriever,
                    desc=desc, exclude_query=False, seed=42,
                )},
            ],
        })
    return jobs


def _count_prompt_tokens(tokenizer, job: dict, mode: str) -> int:
    if mode == 'chat':
        rendered = tokenizer.apply_chat_template(
            job['messages'],
            tokenize=False,
            add_generation_prompt=True,
        )
        return len(tokenizer.encode(rendered))
    return len(tokenizer.encode(job['prompt']))


def run_seed(llm: LLM, tokenizer, jobs: list[dict], out_dir: Path, seed: int,
             max_tokens: int, max_num_seqs: int, mode: str) -> None:
    seed_dir = out_dir / str(seed)
    seed_dir.mkdir(parents=True, exist_ok=True)
    tokens_dir = out_dir / 'tokens'
    tokens_dir.mkdir(parents=True, exist_ok=True)

    pending = []
    for job in jobs:
        out_path = seed_dir / f"{job['id']}.txt"
        if out_path.exists() and out_path.stat().st_size > 0:
            continue
        pending.append(job)

    if not pending:
        print(f'seed {seed}: all outputs already exist, skipping')
        return

    sampling_kwargs = dict(
        temperature=1.0,
        top_p=1.0,
        seed=seed,
    )
    if max_tokens and max_tokens > 0:
        sampling_kwargs['max_tokens'] = max_tokens
    sampling = SamplingParams(**sampling_kwargs)

    print(f'seed {seed}: generating {len(pending)} rows')
    t0 = time.time()
    done = 0
    for batch in batch_items(pending, max_num_seqs):
        if mode == 'chat':
            messages = [job['messages'] for job in batch]
            outputs = llm.chat(
                messages,
                sampling,
                chat_template_kwargs={'reasoning_effort': 'low'},
            )
        else:
            prompts = [job['prompt'] for job in batch]
            outputs = llm.generate(prompts, sampling)
        for job, output in zip(batch, outputs):
            out_path = seed_dir / f"{job['id']}.txt"
            out_path.write_text(output.outputs[0].text)
            tok_path = tokens_dir / f"{job['id']}.json"
            toks = load_tokens(tok_path)
            prompt_tokens = _count_prompt_tokens(tokenizer, job, mode)
            completion_tokens = len(output.outputs[0].token_ids)
            toks[str(seed)] = prompt_tokens + completion_tokens
            save_tokens(tok_path, toks)
            done += 1
        print(f'  seed {seed}: {done}/{len(pending)} done')
    print(f'seed {seed}: done in {time.time() - t0:.1f}s')


def main():
    args = parse_args()
    if not args.model.exists():
        raise SystemExit(f'model path not found: {args.model}')

    jobs = build_jobs(args.limit)
    print(f'built {len(jobs)} jobs')
    tokenizer = AutoTokenizer.from_pretrained(str(args.model), trust_remote_code=True)

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
        max_num_seqs=args.max_num_seqs,
        dtype='bfloat16',
        enforce_eager=args.enforce_eager,
    )

    for seed in args.seeds:
        run_seed(llm, tokenizer, jobs, args.out, seed, args.max_tokens, args.max_num_seqs, args.mode)


if __name__ == '__main__':
    main()
