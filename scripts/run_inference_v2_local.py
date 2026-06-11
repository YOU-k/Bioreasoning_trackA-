#!/usr/bin/env python3
"""Local GPT-OSS inference for Attempt 04/05 two-prompt pipeline.

Legacy script for historical two-prompt experiments. Note: gpt-oss should be
used through its Harmony/chat template; this script is kept for archival
reproducibility and is not the recommended Track-A path.

Runs DE and DIR prompts separately for test rows and writes:
  <out>/de/<seed>/<id>.txt
  <out>/dir/<seed>/<id>.txt
  <out>/de/tokens/<id>.json
  <out>/dir/tokens/<id>.json
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

from vllm import LLM, SamplingParams

from pipeline.gene_desc import default as gene_desc_default
from pipeline.kg_retrieval import KGRetrieval
from pipeline.prompt_builder_v2 import build_de_prompt, build_dir_prompt
from pipeline.replogle_prior import ReplogPrior
from pipeline.retrieve_examples import ExampleRetriever


DEFAULT_MODEL = Path('/workspace/volume/data/yy/gpt-oss-120b')
DEFAULT_OUT = ROOT / 'attempts/05_paper_faithful/outputs/local_test'


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
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--seeds', type=int, nargs='+', default=[42])
    ap.add_argument('--max-model-len', type=int, default=16384)
    ap.add_argument('--max-tokens-de', type=int, default=1200)
    ap.add_argument('--max-tokens-dir', type=int, default=1200)
    ap.add_argument('--gpu-memory-utilization', type=float, default=0.92)
    ap.add_argument('--tensor-parallel-size', type=int, default=2)
    ap.add_argument('--max-num-seqs', type=int, default=2)
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
            'de_prompt': build_de_prompt(
                pert, gene, prior=prior, kg=kg, retriever=retriever,
                desc=desc, exclude_query=False, seed=42,
            ),
            'dir_prompt': build_dir_prompt(
                pert, gene, prior=prior, kg=kg, retriever=retriever,
                desc=desc, exclude_query=False, seed=42,
            ),
        })
    return jobs


def run_task(llm: LLM, jobs: list[dict], out_dir: Path, task: str, seed: int,
             max_tokens: int, max_num_seqs: int) -> None:
    task_dir = out_dir / task / str(seed)
    task_dir.mkdir(parents=True, exist_ok=True)
    tokens_dir = out_dir / task / 'tokens'
    tokens_dir.mkdir(parents=True, exist_ok=True)

    pending = []
    for job in jobs:
        out_path = task_dir / f"{job['id']}.txt"
        if out_path.exists() and out_path.stat().st_size > 0:
            continue
        pending.append(job)

    if not pending:
        print(f'{task} seed {seed}: all outputs already exist, skipping')
        return

    sampling = SamplingParams(
        temperature=1.0,
        top_p=1.0,
        seed=seed,
        max_tokens=max_tokens,
    )

    print(f'{task} seed {seed}: generating {len(pending)} rows')
    t0 = time.time()
    done = 0
    for batch in batch_items(pending, max_num_seqs):
        prompts = [job[f'{task}_prompt'] for job in batch]
        outputs = llm.generate(prompts, sampling)
        for job, output in zip(batch, outputs):
            out_path = task_dir / f"{job['id']}.txt"
            out_path.write_text(output.outputs[0].text)
            tok_path = tokens_dir / f"{job['id']}.json"
            toks = load_tokens(tok_path)
            toks[str(seed)] = len(output.outputs[0].token_ids)
            save_tokens(tok_path, toks)
            done += 1
        print(f'  {task} seed {seed}: {done}/{len(pending)} done')
    print(f'{task} seed {seed}: done in {time.time() - t0:.1f}s')


def main():
    args = parse_args()
    if not args.model.exists():
        raise SystemExit(f'model path not found: {args.model}')

    jobs = build_jobs(args.limit)
    print(f'built {len(jobs)} jobs')

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
    )

    for seed in args.seeds:
        run_task(llm, jobs, args.out, 'de', seed, args.max_tokens_de, args.max_num_seqs)
        run_task(llm, jobs, args.out, 'dir', seed, args.max_tokens_dir, args.max_num_seqs)


if __name__ == '__main__':
    main()
