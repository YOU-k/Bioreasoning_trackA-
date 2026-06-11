# Attempt 20 (P2) — Submission format dry-run

Validates the Track-A submission pipeline end-to-end with synthetic LLM
outputs, BEFORE spending on GPT-OSS-120B.

## Why

Track-A submission is `submission.csv` + `prompt.txt` in a zip, with very
specific columns. The official sample (`sample_submission_track_a.csv`)
isn't auto-downloadable; it has to be pulled from the Kaggle Data tab.

A 0-score submission (wrong format) burns a daily submission quota slot.
So we validate offline against the column spec documented in
`project_info/overview.md` before submitting.

## What this script does

`scripts/submission_dry_run.py`:

1. Generates synthetic per-seed LLM responses for ALL 1813 test rows:
   `staging/outputs/{42,43,44}/{id}.txt` + `staging/outputs/tokens/{id}.json`
   Each response uses the A15 SHIP protocol output format so the parser
   exercises its full regex path.
2. Runs `pipeline.runner.assemble_submission()` with the current ship
   config (hybrid_direction α=0.45, nf=0.58).
3. Validates the produced `submission.csv` against the Track-A schema:
   - 14 columns in exact order
   - All 1813 ids from test.csv present, no extras
   - Floats in [0, 1] for all prediction columns
   - No nulls (reasoning_trace = "none" if empty; tokens = 0 default)
   - Type check on a sample of rows
4. Packages the final zip with `submission.csv` + `prompt.txt`.
5. Verifies zip layout.

## Result (this run)

```
[1/4] Generating synthetic LLM outputs ...
      Wrote 1813 rows × 3 seeds = 5439 response files + 1813 token files

[2/4] Assembling submission.csv via pipeline.runner.assemble_submission ...
      Wrote staging/submission.csv (1,557,474 bytes)

[3/4] Validating against Track-A spec ...
      rows: 1813, cols: 14
      column order: OK
      ✓ all schema checks passed

[4/4] Packaging zip ...
      Wrote submission_dryrun.zip (132,888 bytes)
      Zip contents: ['submission.csv', 'prompt.txt']
```

All checks green. **The pipeline is submission-ready as soon as real
GPT-OSS-120B outputs are dropped into the same outputs/{seed}/{id}.txt
layout.**

## Inspection of first row (random synthetic data)

| Column | Value |
|---|---|
| id | Slc35b1_Pdia6 |
| prediction_up | 0.276 |
| prediction_down | 0.236 |
| prediction_up_seed42 | 0.163 (raw LLM, no hybrid) |
| prediction_up_seed43 | 0.144 |
| prediction_up_seed44 | 0.040 |
| reasoning_trace_seed42 | "A1 — Mechanism..." (synthetic) |
| tokens_used | 6393 |
| model_name | gpt-oss-120b |

**Per-seed columns** = raw LLM outputs (audit trail).
**Final `prediction_up` / `prediction_down`** = hybrid-blended via
`hybrid_direction(α=0.45, nf=0.58)` on the 3-seed logit-fused (q, r).

This split is consistent with Track-A spec line 87:
> "Final prediction_up / prediction_down are typically the average across
> the three seeds (the exact aggregation rule is whatever your sample
> submission encodes)."

Our aggregation rule (hybrid) is documented in `prompt.txt` packaged in
the zip.

## Pre-submission checklist (still need to do)

- [ ] Pull `sample_submission_track_a.csv` from Kaggle's Data tab and
      diff our `submission.csv` against it (catches any Kaggle quirks
      like BOM, line ending, float precision)
- [ ] Replace synthetic outputs with real GPT-OSS-120B outputs
- [ ] Re-run this script to validate the real submission zip
- [ ] Upload to Kaggle, confirm score > 0 (then real LB score)

## Files

- `scripts/submission_dry_run.py` — full pipeline runner + validator
- `attempts/20_submission_dryrun/staging/outputs/` — synthetic LLM responses (1813 × 3 seeds, gitignored)
- `attempts/20_submission_dryrun/staging/submission.csv` — assembled CSV (gitignored)
- `attempts/20_submission_dryrun/submission_dryrun.zip` — final zip (gitignored)
- `attempts/20_submission_dryrun/dryrun_log.txt` — full run log
