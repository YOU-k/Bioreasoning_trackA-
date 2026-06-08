"""Round 2: re-run 6 test prompts (trimmed builder) + 15 train ground-truth rows.

Goals:
  1) Confirm trimming Replogle 3-line note + "Reasoning: write..." line
     does NOT degrade output quality on the 6 known cases.
  2) Stratified train sample (5 up / 5 down / 5 none) — convert P_DE,
     P_up_given_DE into (prob_up, prob_down, prob_none) and compare to label.

Reads DEEPSEEK_API_KEY from /data3/yy/key.env.
Outputs:  attempts/03_kg_celltype/test_deepseek_v2/{kind}/{id}.json
"""
from __future__ import annotations
import csv, json, random, sys, time
from pathlib import Path
import openai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.prompt_builder import build_prompt
from pipeline.replogle_prior import ReplogPrior
from pipeline.kg_retrieval import KGRetrieval
from pipeline.output_parser import parse

KEY_FILE = Path('/data3/yy/key.env')
OUT_DIR = ROOT / 'attempts/03_kg_celltype/test_deepseek_v2'

RETEST_IDS = [
    'Actb_Actn1', 'Aars_Atf4', 'Ppie_Cat',
    'Nat10_Sdf2l1', 'Wdr82_Gm31522', 'Map3k8_Cdk14',
]


def load_key() -> str:
    for line in KEY_FILE.read_text().splitlines():
        if line.startswith('DEEPSEEK_API_KEY='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('DEEPSEEK_API_KEY not found')


def pick_train_sample(n_each: int = 5, seed: int = 42):
    rng = random.Random(seed)
    rows = list(csv.DictReader(open(ROOT / 'data/train.csv')))
    by_label = {'up': [], 'down': [], 'none': []}
    for r in rows:
        if r['label'] in by_label:
            by_label[r['label']].append(r)
    picks = []
    for label, lst in by_label.items():
        picks.extend(rng.sample(lst, n_each))
    return picks


def call_deepseek(client, prompt: str, max_tokens: int = 2000):
    t0 = time.time()
    resp = client.chat.completions.create(
        model='deepseek-reasoner',
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=max_tokens,
    )
    msg = resp.choices[0].message
    u = resp.usage
    return {
        'elapsed_sec': round(time.time() - t0, 1),
        'reasoning_content': getattr(msg, 'reasoning_content', '') or '',
        'content': msg.content or '',
        'prompt_tokens': u.prompt_tokens,
        'completion_tokens': u.completion_tokens,
        'reasoning_tokens': getattr(getattr(u, 'completion_tokens_details', None),
                                    'reasoning_tokens', None),
        'total_tokens': u.total_tokens,
    }


def main():
    api_key = load_key()
    client = openai.OpenAI(
        api_key=api_key, base_url='https://api.deepseek.com/v1', timeout=600,
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'retest').mkdir(exist_ok=True)
    (OUT_DIR / 'train_gt').mkdir(exist_ok=True)

    prior = ReplogPrior()
    kg = KGRetrieval()

    print('### PART 1: re-test 6 test rows with trimmed prompt')
    print('-' * 70)
    retest_summary = []
    for rid in RETEST_IDS:
        out_path = OUT_DIR / 'retest' / f'{rid}.json'
        if out_path.exists():
            print(f'[skip] {rid}')
            d = json.loads(out_path.read_text())
            retest_summary.append((rid, d))
            continue
        pert, gene = rid.split('_', 1)
        prompt = build_prompt(pert, gene, prior=prior, kg=kg, use_kg=True)
        prompt_chars = len(prompt)
        print(f'[run]  {rid:<22} prompt_chars={prompt_chars} (~{prompt_chars//4} tok)')
        try:
            result = call_deepseek(client, prompt)
        except Exception as e:
            print(f'   ERROR: {e}')
            continue
        result['id'] = rid
        result['prompt'] = prompt
        parsed = parse(result['content'])
        p_de = int(round(parsed.p_de * 100)) if parsed.parse_status != 'failed' else None
        p_up_given_de = int(round(parsed.p_up_given_de * 100)) if parsed.parse_status != 'failed' else None
        result['parsed'] = {'P_DE': p_de, 'P_up_given_DE': p_up_given_de,
                            'parse_status': parsed.parse_status}
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f'   tokens(p/r/a)={result["prompt_tokens"]}/{result["reasoning_tokens"]}/'
              f'{result["completion_tokens"]}  '
              f'parsed=P_DE:{p_de} P_up:{p_up_given_de}')
        retest_summary.append((rid, result))

    print()
    print('### PART 2: 15 train rows (5 up / 5 down / 5 none, stratified)')
    print('-' * 70)
    picks = pick_train_sample(5, seed=42)
    train_summary = []
    for row in picks:
        rid = row['id']
        out_path = OUT_DIR / 'train_gt' / f'{rid}.json'
        if out_path.exists():
            print(f'[skip] {rid}  label={row["label"]}')
            d = json.loads(out_path.read_text())
            train_summary.append((row, d))
            continue
        pert, gene, label = row['pert'], row['gene'], row['label']
        prompt = build_prompt(pert, gene, prior=prior, kg=kg, use_kg=True)
        print(f'[run]  {rid:<32} label={label}  prompt_chars={len(prompt)}')
        try:
            result = call_deepseek(client, prompt)
        except Exception as e:
            print(f'   ERROR: {e}')
            continue
        result['id'] = rid
        result['true_label'] = label
        result['prompt'] = prompt
        parsed = parse(result['content'])
        p_de = int(round(parsed.p_de * 100)) if parsed.parse_status != 'failed' else None
        p_up_given_de = int(round(parsed.p_up_given_de * 100)) if parsed.parse_status != 'failed' else None
        result['parsed'] = {'P_DE': p_de, 'P_up_given_DE': p_up_given_de,
                            'parse_status': parsed.parse_status}
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        # derived probs
        p_de_n = (p_de or 0) / 100
        p_up_c = (p_up_given_de or 0) / 100
        p_up = p_de_n * p_up_c
        p_dn = p_de_n * (1 - p_up_c)
        p_no = 1 - p_de_n
        print(f'   parsed=P_DE:{p_de} P_up_c:{p_up_given_de}  '
              f'-> p_up={p_up:.2f} p_dn={p_dn:.2f} p_none={p_no:.2f}  TRUE={label}')
        train_summary.append((row, result))

    print()
    print('### SUMMARY: trimmed-prompt re-test (compare to round 1)')
    print('-' * 70)
    print(f'{"id":<22} {"P_DE":>5} {"P_up":>5} {"p_tok":>7} {"r_tok":>7}')
    for rid, d in retest_summary:
        p = d['parsed']
        print(f'{rid:<22} {p["P_DE"]!s:>5} {p["P_up_given_DE"]!s:>5} '
              f'{d["prompt_tokens"]:>7} {d["reasoning_tokens"] or 0:>7}')

    print()
    print('### SUMMARY: ground-truth alignment (15 train rows)')
    print('-' * 70)
    print(f'{"id":<32} {"true":<5} {"P_DE":>5} {"P_up":>5}   {"p_up":>5} {"p_dn":>5} {"p_no":>5}  hit?')
    hit_de, hit_dir = 0, 0
    n_eval = 0
    for row, d in train_summary:
        p = d.get('parsed', {})
        pd, pu = p.get('P_DE'), p.get('P_up_given_DE')
        if pd is None or pu is None:
            continue
        n_eval += 1
        p_de_n = pd / 100
        p_up_c = pu / 100
        p_up = p_de_n * p_up_c
        p_dn = p_de_n * (1 - p_up_c)
        p_no = 1 - p_de_n
        # pick argmax
        argmax = max(zip(['up', 'down', 'none'], [p_up, p_dn, p_no]), key=lambda x: x[1])[0]
        hit_de_b = (argmax == 'none') == (row['label'] == 'none')
        hit_dir_b = (argmax == row['label'])
        hit_de += int(hit_de_b)
        hit_dir += int(hit_dir_b)
        marker = '✓' if hit_dir_b else ('=' if hit_de_b else '✗')
        print(f'{row["id"]:<32} {row["label"]:<5} {pd!s:>5} {pu!s:>5}   '
              f'{p_up:.2f}  {p_dn:.2f}  {p_no:.2f}  {marker}')
    print()
    if n_eval:
        print(f'argmax DE-vs-none accuracy : {hit_de}/{n_eval} = {hit_de/n_eval:.2%}')
        print(f'argmax 3-class accuracy   : {hit_dir}/{n_eval} = {hit_dir/n_eval:.2%}')
        print(f'  (chance baseline for 3-class given 5/5/5 split: 33.3%)')


if __name__ == '__main__':
    main()
