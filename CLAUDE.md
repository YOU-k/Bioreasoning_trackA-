# Project: MLGenX Bioreasoning Challenge — Track A

Kaggle competition predicting ternary perturbation response (`up` / `down` / `none`)
for unseen (perturbed_gene, target_gene) pairs in mouse BMDM CRISPRi.

## Folder layout

| Folder | Purpose |
|---|---|
| `data/` | Raw inputs (`train.csv`, `test.csv`) and computed priors (`replogle_de.pkl`, `mouse_to_human_ortholog.json`). Read-only for analysis code; new computed artifacts may be written here. |
| `project_info/` | Competition facts: data schema, rules, evaluation metric. Fixed reference. |
| `discussion/` | Reasoning notes and analytical frameworks (`analysis.md`, `tricks.md`, reference PDFs). |
| `plans/` | Active and historical plans for the next attempts. |
| `pipeline/` | Shared, reusable infrastructure (prior loading, prompt building, output parsing, submission assembly). Each module owns one concern. |
| `pipeline/tests/` | Sanity tests for pipeline modules. Run before any meaningful change. |
| `attempts/NN_short_name/` | One experiment per folder. Self-contained: `README.md` (hypothesis + what), runnable script, `result.md` (numbers + verdict + next). |
| `progress.md` | Top-level append-only log. One block per completed attempt. |

## Conventions

- **Decoupled, small modules.** Each `pipeline/*.py` does one thing. Adding a new
  signal must not require touching unrelated files.
- **Every attempt has its own folder under `attempts/`** with `README.md` and
  `result.md`. Numbers belong in `result.md`, narrative in `discussion/`.
- **Test before committing pipeline changes.** Tests in `pipeline/tests/` should
  run in under 10 seconds and exit non-zero on regression.
- **Update `progress.md`** after every meaningful run, success or failure.
  Format: date · attempt id · headline result · next.
- **Discussion stays in `discussion/`**, not in code comments. Code stays terse.
- **Never modify raw competition files in `data/`.** Computed priors written
  there are reproducible from scripts in `attempts/`.
- **Reproducibility**: each attempt's `README.md` lists inputs (paths) and
  outputs (paths), so the experiment can be re-run from scratch.

## After meaningful work — required updates

Whenever an attempt completes, a strategic decision is made, or the
architecture changes, update **all of** the following before stopping:

1. `progress.md` — append a dated block: what was done, headline result, next action.
2. `plans/plan.md` — refresh the forward-looking pending list. Move completed items out, add new ones.
3. `attempts/NN_short_name/result.md` — if this was a finished attempt, fill in numbers and verdict.
4. **Commit and push.** Workflow spans two servers; the remote must be current.
   ```bash
   git add -A && git commit -m "<one-line summary>" && git push
   ```

These updates are part of "done" for any non-trivial change. Don't leave a
session with stale `plan.md` / `progress.md` or uncommitted state.
