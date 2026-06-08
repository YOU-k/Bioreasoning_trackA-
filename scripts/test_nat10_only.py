"""Quick: re-run only the 2 hard cases (Nat10_Sdf2l1, Aars_Atf4) with format-fixed prompt."""
import json, sys, time
from pathlib import Path
import openai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.prompt_builder import build_prompt
from pipeline.replogle_prior import ReplogPrior
from pipeline.kg_retrieval import KGRetrieval
from pipeline.output_parser import parse

key = [l for l in Path('/data3/yy/key.env').read_text().splitlines() if l.startswith('DEEPSEEK_API_KEY=')][0].split('=', 1)[1].strip()
client = openai.OpenAI(api_key=key, base_url='https://api.deepseek.com/v1', timeout=600)
prior, kg = ReplogPrior(), KGRetrieval()

for rid in ['Aars_Atf4', 'Nat10_Sdf2l1']:
    pert, gene = rid.split('_', 1)
    prompt = build_prompt(pert, gene, prior=prior, kg=kg, use_kg=True)
    t0 = time.time()
    resp = client.chat.completions.create(
        model='deepseek-reasoner',
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=3000,
    )
    msg = resp.choices[0].message
    u = resp.usage
    print(f'{rid:<20} elapsed={time.time()-t0:.1f}s  '
          f'p_tok={u.prompt_tokens}  r_tok={u.completion_tokens_details.reasoning_tokens}  '
          f'a_tok={u.completion_tokens - u.completion_tokens_details.reasoning_tokens}')
    parsed = parse(msg.content)
    print(f'   parse_status={parsed.parse_status}  P_DE={int(parsed.p_de*100)}  P_up={int(parsed.p_up_given_de*100)}')
    print(f'   content tail:')
    for l in (msg.content or '').splitlines()[-4:]:
        print(f'     > {l}')
    print()
    out_dir = ROOT / 'attempts/03_kg_celltype/test_deepseek_v2/retest'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f'{rid}.json').write_text(json.dumps({
        'id': rid, 'prompt': prompt, 'content': msg.content,
        'reasoning_content': getattr(msg, 'reasoning_content', '') or '',
        'prompt_tokens': u.prompt_tokens,
        'reasoning_tokens': u.completion_tokens_details.reasoning_tokens,
        'completion_tokens': u.completion_tokens,
        'parsed': {'P_DE': int(parsed.p_de*100), 'P_up_given_DE': int(parsed.p_up_given_de*100),
                   'parse_status': parsed.parse_status},
    }, indent=2, ensure_ascii=False))
