# benchmark — Programmatic Verification (PV)

The judge-free evaluation channel for Neuro-Air: 90 tasks whose answer is
uniquely determined and recomputable from the source database. A frozen
validator recomputes the ground truth live and compares the agent's stored
values under numeric tolerance. No LLM or human judgment enters the score.

This is a Neuro-Air-focused slice of the air-bench harness (the response-quality
LLM-judge and objective process metrics live in `../evaluation/`).

## Layout

```
evals/neuroair/            118 frozen ground-truth validators (5 categories, HB + HK)
benchmarks_neuroair*.json  task registries (the 90-task ablation + variants)
core/ domains/ adapters/   the validation package (validators import from here)
experiments/Neuro-Air/     run outputs + the per-task PV matrix (pv_matrix.json)
scripts/                   scoring + reproduction (below)
analysis/                  human-eval statistics notebook + data
config.py                  DB settings (gitignored: real credentials)
models.toml                model registry (gitignored: real API keys)
```

## Reproduce the ablation results

```bash
uv sync

# DB-free (reads archived runs): reproduce Table 2 counts, Extended Data Table S8,
# and the cluster-bootstrap CI
uv run python scripts/_category_table.py        # category-level wins/losses (Table S8)
uv run python scripts/_cluster_bootstrap.py     # pooled gain 95% CI = [+3.6, +9.3]

# DB-backed (needs config.py credentials + a read-only DB): replay the frozen
# validators to rebuild the per-task pass/fail matrix
uv run python scripts/_export_pv_matrix_dbfree.py
```

Validators recompute ground truth from the database on every call; database
access is read-only. The raw Hebei environmental records are proprietary and are
not distributed here.
