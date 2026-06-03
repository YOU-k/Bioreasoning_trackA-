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
