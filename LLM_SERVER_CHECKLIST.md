# LLM server checklist — diagnose 0.510 LB and re-submit

**Update 2026-06-12 ~06:30 UTC**: hybrid_off submission scored **0.564**
— +0.054 over v3 (hybrid ON). **Hybrid_direction is HURTING on real
test**, opposite of probe60 finding. Probe60 was systematically
optimistic (rare-gene rows still had structural footprint in train).
The runner Replogle blend + nf=0.58 constant for non-full rows was
destroying ranking on real test. **Pure LLM logit-fusion (no hybrid)
is our current real ceiling at 0.564.**

After the 2026-06-12 LB landing + diagnostic submissions, this is the
concrete checklist to run on the LLM server (`root@aipaas.miracle.ac.cn`,
`/workspace/volume/data/yy/Bioreasoning_trackA/`).

The two goals: (1) understand WHY 0.510 hybrid vs 0.564 hybrid-off, and
(2) test whether Hagai prompt block (which we never independently
verified on real test) is helping or hurting — same way Replogle hybrid
turned out to hurt.

---

## NEW: F experiment — re-run inference with `include_hagai_block=False`

Critical finding: hybrid_off scored 0.564 vs hybrid_on 0.510 on real
test. Replogle blend was hurting because K562/RPE1 → mouse-BMDM unseen-
gene transfer is unreliable. **Same risk applies to the Hagai prompt
block**: it's mouse-native data but LPS stimulation, not CRISPRi.
Probe60 said Hagai helps DE (+0.150 AUROC, A11). But A11 was tested with
hybrid_on, and we now know probe60 over-rated hybrid effects. Need to
independently verify Hagai on real test.

```bash
cd /workspace/volume/data/yy/Bioreasoning_trackA
git fetch origin && git pull --ff-only

# Confirm the new flag is in prompt_builder_v3:
grep -n include_hagai_block pipeline/prompt_builder_v3.py
# expected:
#   include_hagai_block: bool = True
#   if include_hagai_block:
#       body += ['## ' + _format_hagai(...), '']

# Re-run vLLM inference with the new prompt builder. The flag default is
# True (same as v3), so explicitly pass False:
python3 - <<'PY'
import csv, json, time
from pathlib import Path
from pipeline.prompt_builder_v3 import build_track_a_prompt

ROOT = Path('.')
test_rows = list(csv.DictReader(open(ROOT/'data/test.csv')))
prompts_dir = ROOT / 'attempts/15_retrieval_budget/prompts_no_hagai'
prompts_dir.mkdir(parents=True, exist_ok=True)

t0 = time.time()
for i, row in enumerate(test_rows):
    rid, pert, gene = row['id'], row['pert'], row['gene']
    p = build_track_a_prompt(
        pert, gene,
        exclude_query=False, seed=42,
        include_hagai_block=False,     # <-- the key flag
    )
    (prompts_dir / f'{rid}.txt').write_text(p)
print(f'built {len(test_rows)} prompts in {time.time()-t0:.0f}s -> {prompts_dir}')
PY

# Then run GPT-OSS-120B inference 3 seeds × 1813 rows (same harness
# you used for v3, just point to the new prompts directory).
# Output goes to attempts/15_retrieval_budget/outputs_no_hagai/{42,43,44}/{id}.txt
# Token file: attempts/15_retrieval_budget/outputs_no_hagai/tokens/{id}.json

# After inference completes, assemble with hybrid_off:
python3 - <<'PY'
from pipeline.runner import assemble_submission
from pathlib import Path
ROOT = Path('.')
assemble_submission(
    outputs_dir=ROOT/'attempts/15_retrieval_budget/outputs_no_hagai',
    out_path=ROOT/'attempts/15_retrieval_budget/no_hagai_hybrid_off/submission.csv',
    model_name='gpt-oss-120b',
    apply_hybrid_direction=False,     # <-- key: confirm hybrid stays off
)
PY

# Package zip and submit.
```

Expected outcome:
- If no-Hagai score ≥ 0.564 → Hagai was hurting on test (same as hybrid)
- If no-Hagai score < 0.564 → Hagai was helping; keep it but stay hybrid_off

### Cheaper alternative if you don't want to rerun 1813×3 GPT-OSS calls

We already submitted F.4 (r=0.5 constant) which directly measures
DE-AUROC = `2 * F.4_score - 0.5`. If DE-AUROC measured this way is high
(say >0.62), Hagai's DE signal is real; if it's near 0.5, Hagai might
not be doing real work either. Awaiting that score now.

---

## 0. Pull latest main + verify config

```bash
cd /workspace/volume/data/yy/Bioreasoning_trackA
git fetch origin
git log --oneline origin/main | head -5
# should show:  a386b80 Fix main schema (16 columns matching v3) ...

git checkout main
git pull --ff-only origin main

# sanity: confirm hybrid defaults are A15 (alpha=0.45, nf=0.58), not v3's A11 era (0.4, 0.62)
grep -nE "hybrid_alpha|non_full_default|alpha: float" pipeline/runner.py
# expected:
#   hybrid_direction(..., alpha: float = 0.45, non_full_default: float = 0.58)
#   assemble_submission(..., hybrid_alpha: float = 0.45, hybrid_non_full_default: float = 0.58)
```

If the grep shows `0.4` / `0.62`, the pull didn't take. Stop and fix.

---

## 1. Diagnose v3's inference outputs (cheapest, no compute spend)

The v3 submission used files like `attempts/<somewhere>/outputs/{42,43,44}/{id}.txt`.
Find them:

```bash
# Likely paths — adjust if YOU-k used a different attempts/ dir
ls attempts/12_cleaner_prompt/outputs/ 2>/dev/null | head
ls attempts/_a15_local_vllm/ 2>/dev/null | head
find . -path './attempts/*/outputs/42' -type d | head
```

Then check the parse rate for one seed (this is what mattered for the
0.510 score — if many outputs fail to parse, the parser falls back to
`P_DE = 0.45`, `P_up = 0.5`, which is exactly what AUROC-near-0.5 looks
like):

```bash
# Replace OUTPUT_DIR with the actual path
OUTPUT_DIR=attempts/12_cleaner_prompt/outputs

python3 - <<'PY'
import re, glob, sys, os
from collections import Counter

OUT = os.environ.get('OUTPUT_DIR', 'attempts/12_cleaner_prompt/outputs')
RE_PDE = re.compile(r'P_?DE\s*[:=]\s*([0-9]{1,3})', re.I)
RE_PUP = re.compile(r'P_?up_?given_?DE\s*[:=]\s*([0-9]{1,3})', re.I)

for seed in (42, 43, 44):
    files = sorted(glob.glob(f'{OUT}/{seed}/*.txt'))
    if not files:
        print(f'seed {seed}: NO FILES')
        continue
    counts = Counter()
    pde_vals, pup_vals = [], []
    for f in files:
        t = open(f).read()
        mde = RE_PDE.search(t)
        mup = RE_PUP.search(t)
        if mde and mup: tag = 'both_ok'
        elif mde:        tag = 'de_only'
        elif mup:        tag = 'up_only'
        else:            tag = 'fallback'
        counts[tag] += 1
        if mde: pde_vals.append(int(mde.group(1)))
        if mup: pup_vals.append(int(mup.group(1)))
    print(f'\nseed {seed}: {len(files)} files')
    for k, v in counts.most_common():
        pct = 100 * v / len(files)
        print(f'  {k:<12s} {v:>5} ({pct:>5.1f}%)')
    if pde_vals:
        n = len(pde_vals)
        print(f'  P_DE distribution (n={n}): min={min(pde_vals)} median={sorted(pde_vals)[n//2]} max={max(pde_vals)} mean={sum(pde_vals)/n:.1f}')
    if pup_vals:
        n = len(pup_vals)
        print(f'  P_up distribution (n={n}): min={min(pup_vals)} median={sorted(pup_vals)[n//2]} max={max(pup_vals)} mean={sum(pup_vals)/n:.1f}')
PY
```

**Interpretation**:

| fallback rate | meaning | next action |
|---|---|---|
| > 30% | GPT-OSS-120B is not following the A1-B2 output format reliably | Prompt-template fix needed for Harmony; see §3 below |
| 5-30% | partial format adherence | re-submit with the corrected config; the fix may close some of the gap |
| < 5% | parser is healthy | the gap is NOT parser noise; likely algorithm transfer or probe60 over-fit |

If `P_DE mean ≈ 24` matches our DeepSeek probe60 observation → GPT-OSS
is producing similar conservative outputs. If `mean ≈ 45-50` → GPT-OSS
is closer to balanced; the LB gap might be a tie/calibration issue.

---

## 2. Inspect a few real outputs (eyeball check)

```bash
# Sample 3 random files per seed
for seed in 42 43 44; do
  echo "==== seed $seed ===="
  ls $OUTPUT_DIR/$seed/*.txt | shuf | head -3 | while read f; do
    echo "--- $f ---"
    cat "$f"
    echo
  done
done
```

Look for:
- Does it have the `Step A1 ... B2 ... P_DE: X ... P_up_given_DE: Y` structure?
- If not, what does GPT-OSS output instead? (Harmony's "Reasoning: low"
  may make it skip the steps entirely and only emit a final answer.)
- Are P_DE / P_up values present somewhere in the text but not in the
  exact format the parser regex matches?

---

## 3. Re-assemble submission with the main-branch fix

This builds a new submission CSV from the SAME inference outputs (no
re-running GPT-OSS) but with:
- Correct 16-column schema (`prompt_tokens` per-call + `completion_tokens` + `tokens_used`)
- A15 SHIP hybrid params (α=0.45, nf=0.58) — v3 used 0.4 / 0.62 (or
  defaulted to 0.62)

```bash
python3 - <<'PY'
import os
from pipeline.runner import assemble_submission
from pathlib import Path

OUT = os.environ.get('OUTPUT_DIR', 'attempts/12_cleaner_prompt/outputs')
csv_path = Path('staging/submission_a15_fixed.csv')
csv_path.parent.mkdir(parents=True, exist_ok=True)

assemble_submission(
    outputs_dir=OUT,
    out_path=csv_path,
    model_name='gpt-oss-120b',
    apply_hybrid_direction=True,
    hybrid_alpha=0.45,                  # A15 SHIP
    hybrid_non_full_default=0.58,       # A15 SHIP
)
print(f'wrote {csv_path}')

# Sanity print
import csv
with open(csv_path) as f:
    r = csv.DictReader(f)
    print('columns:', r.fieldnames)
    row0 = next(r)
    for k, v in row0.items():
        s = v if len(str(v)) < 60 else str(v)[:57] + '...'
        print(f'  {k:<26s} {s}')
PY
```

Expected: 16 columns, `prompt_tokens` around 1900-2400 (well under 4096
cap), `completion_tokens` reasonable, all 1813 rows.

---

## 4. Build the prompt.txt template (under 4096)

```bash
python3 - <<'PY'
import sys
from pathlib import Path
from pipeline.prompt_builder_v3 import (
    _HEADER, _RULES, _PROTOCOL, _TIER_LADDERS, _OUTPUT_FORMAT, estimate_tokens,
)
template = (
    '# Track-A submission prompt template (Attempt 15 SHIP)\n'
    '# Architecture: single-call per (pert, gene) per seed.\n'
    '#   prompt_builder: pipeline/prompt_builder_v3.py\n'
    '#   retrieval:      paper §3.4.2 analog + contrast, k_a=5 + k_c=5\n'
    '#   priors used:    Replogle K562/RPE1 logFC + Hagai mouse-BMDM LPS6h |logFC|\n'
    '#   runner-side:    3-seed logit fusion of q + r; hybrid_direction(α=0.45, nf=0.58)\n\n'
)
body = (
    _HEADER.format(pert='{pert}', gene='{gene}') + '\n\n'
    + _RULES + '\n\n'
    + _PROTOCOL.format(pert='{pert}', gene='{gene}') + '\n\n'
    + _TIER_LADDERS.format(pert='{pert}', gene='{gene}') + '\n\n'
    + _OUTPUT_FORMAT
)
Path('staging/prompt.txt').write_text(template + body)
tk = estimate_tokens((template+body))
print(f'staging/prompt.txt: ~{tk} tokens (<4096 required)')
assert tk < 4096, 'prompt.txt over cap!'
PY
```

Should print `~1475 tokens (<4096 required)`. If over, trim further.

---

## 5. Package the zip

```bash
cd staging
zip -j submission_a15_fixed.zip submission_a15_fixed.csv prompt.txt
ls -la submission_a15_fixed.zip
unzip -l submission_a15_fixed.zip   # should show only [submission_a15_fixed.csv, prompt.txt]
cd ..
```

Note: Kaggle expects the inner CSV to be named `submission.csv`. Either
rename before zipping, or use the dry-run script:

```bash
python scripts/submission_dry_run.py \
    --staging staging/ \
    --out-zip submission_a15_fixed.zip
```

The dry-run script handles the rename and validates the schema.

But the dry-run uses *synthetic* outputs by default. For a real
submission, you need to replace the synthetic outputs step with your
real outputs. Easiest: skip the dry-run script and assemble manually
(steps 3 + 4 + 5 above).

---

## 6. Pre-submit validation

```bash
python3 - <<'PY'
import csv
from pathlib import Path

p = Path('staging/submission_a15_fixed.csv')
EXPECTED = ['id', 'prediction_up', 'prediction_down',
            'prediction_up_seed42', 'prediction_down_seed42',
            'prediction_up_seed43', 'prediction_down_seed43',
            'prediction_up_seed44', 'prediction_down_seed44',
            'reasoning_trace_seed42', 'reasoning_trace_seed43', 'reasoning_trace_seed44',
            'prompt_tokens', 'completion_tokens', 'tokens_used', 'model_name']

with open(p) as f:
    r = csv.DictReader(f)
    cols = r.fieldnames
    rows = list(r)

errors = []
if cols != EXPECTED:
    errors.append(f'columns wrong: got {cols}')
if len(rows) != 1813:
    errors.append(f'rows wrong: got {len(rows)}, expected 1813')

# check prompt_tokens cap
over_cap = [r for r in rows if int(r['prompt_tokens']) > 4096]
if over_cap:
    errors.append(f'{len(over_cap)} rows have prompt_tokens > 4096 (e.g. {over_cap[0]["id"]}: {over_cap[0]["prompt_tokens"]})')

# check no nulls / empty
for c in EXPECTED:
    n_empty = sum(1 for r in rows if not r[c])
    if n_empty and c not in ('reasoning_trace_seed42','reasoning_trace_seed43','reasoning_trace_seed44'):
        errors.append(f'column {c} has {n_empty} empty values')

# check float ranges
for c in ['prediction_up','prediction_down']:
    bad = [r for r in rows if not (0 <= float(r[c]) <= 1)]
    if bad: errors.append(f'{c} out of [0,1] in {len(bad)} rows')

if errors:
    print('❌ ERRORS:')
    for e in errors: print('  ' + e)
else:
    print('✓ all pre-submit checks pass — ready to upload')
PY
```

---

## 7. Upload via Kaggle API

If the user has the Kaggle CLI configured:

```bash
kaggle competitions submit \
  -c ml-gen-x-bioreasoning-challenge-track-a \
  -f staging/submission_a15_fixed.zip \
  -m "A15 SHIP with corrected 16-col schema + α=0.45 nf=0.58"
```

Or via curl using the existing token from `.claude/settings.local.json`:

```bash
curl -X POST \
  -H 'Authorization: Bearer KGAT_b9cea8348ce8476850fb61570ad05d46' \
  -F 'file=@staging/submission_a15_fixed.zip' \
  -F 'fileName=submission_a15_fixed.zip' \
  -F 'submissionDescription=A15 SHIP corrected 16-col schema + α=0.45 nf=0.58' \
  'https://www.kaggle.com/api/v1/competitions/submissions/submit/ml-gen-x-bioreasoning-challenge-track-a'
```

Wait ~10 sec then check status:

```bash
curl -sL -H 'Authorization: Bearer KGAT_b9cea8348ce8476850fb61570ad05d46' \
  'https://www.kaggle.com/api/v1/competitions/submissions/list/ml-gen-x-bioreasoning-challenge-track-a' \
  | python3 -m json.tool | head -30
```

---

## 8. Interpreting the new score

| new LB score | what it means | next step |
|---|---|---|
| ≥ 0.60 | Schema + hybrid fix unlocked real signal. Probe60 → LB transfer is decent | iterate normally; consider more retrieval / signal sources |
| 0.55 - 0.59 | Modest improvement. Hybrid α tuning closed part of the gap | look at parse_status carefully; consider Harmony-format-specific prompt tweaks |
| 0.51 - 0.54 | Small improvement, gap mostly remains | the issue is NOT just the schema/hybrid — it's GPT-OSS output quality. Need prompt redesign for Harmony |
| ≤ 0.51 | No change | something else is wrong; double-check pre-submit validation produced the file we actually submitted |

---

## Quick reference: known-good config

| Item | Value |
|---|---|
| Prompt builder | `pipeline/prompt_builder_v3.py:build_track_a_prompt` |
| `include_bmdm_context` | `False` (A12 finding) |
| `include_decision_rules` | `True` (A13) |
| `include_reasoning_protocol` | `True` (A13) |
| `enrich_examples` | `False` (A14) |
| `hide_example_labels` | `False` (A18) |
| `k_a`, `k_c` | `5`, `5` (A15) |
| `apply_hybrid_direction` | `True` |
| `hybrid_alpha` | `0.45` (A15 SHIP) |
| `hybrid_non_full_default` | `0.58` (A15 SHIP) |
| 3-seed fusion | logit-average q and r separately (`pipeline.runner.fuse_q_r_logit`) |
| Submission columns | 16: id, predictions×8, traces×3, prompt_tokens, completion_tokens, tokens_used, model_name |

## Quick reference: known failures (don't redo)

- Don't set `prompt_tokens = sum across seeds` (Kaggle validates against 4096 single-call cap)
- Don't include BMDM context paragraph (A12: -0.012 on probe60)
- Don't enrich each example with per-row Hagai/Replogle (A14: -0.054)
- Don't use prescriptive numerical defaults in prompt rules (A06/A16: escape hatch)
- Don't use imbalanced retrieval ratios (A19: -0.087 hybrid)
- Don't shift LLM distribution to match train calibration via prompt framing (A17: -0.066 hybrid)
