# Neuro-Air

**Multi-agent AI for End-to-End Air Quality Analysis and Decision Support**

Neuro-Air is a hierarchical multi-agent LLM framework for urban air-quality
analysis. A central **Coordinator** decomposes a natural-language query into an
ordered plan over five domain-specialized **worker agents** and an independent
**verification** pass, all sharing **one persistent Python runtime** (the
"runtime is the state" dual-stream design): each worker's executed code and
staged variables persist in a shared namespace that downstream workers reuse
instead of re-querying. Every quantitative claim is grounded in code the agents
actually executed against read-only environmental databases.

This repository is the code release accompanying the paper. It reproduces the
paper's three evaluation channels across Hong Kong and Hebei:

- **Programmatic verification (PV)** — a judge-free benchmark of tasks whose
  answer is uniquely determined and recomputable live from the source database.
- **Response quality (RQ)** — a fixed multi-LLM judge panel scoring response
  prose on a frozen rubric.
- **Objective process metrics** — deterministic, rule-based parsing of the
  execution logs (no LLM, no human judgment).

> **Note on scope.** This repo contains **code, task definitions, frozen
> validators, and agent/prompt configurations only.** The manuscript and
> reviewer materials are intentionally not tracked (see `.gitignore`). The raw
> Hebei environmental records are proprietary and are **not** distributed here
> (see [Data availability](#data-availability)).

---

## Repository layout

```
Neuro-Air/
├── framework/     The Neuro-Air multi-agent framework — runs queries, generates answers
│   ├── adapters/
│   │   ├── cave_agent_adapter.py     single-agent factory (baseline arm)
│   │   └── multiagent_adapter.py     coordinator + 5 workers + verifier over one shared runtime
│   ├── core/                         agent loop, LLM client/registry, scoring, security
│   ├── domains/{HK,HB,Beijing}/      per-domain DB engine, schema, system prompt, tools
│   ├── evals/<capability>/<domain>/  ground-truth validators
│   ├── benchmarks_neuroair*.json     task registries (90-task ablation + variants)
│   ├── prompts/                      judge / claim-verification prompts
│   ├── scripts/run.py                entry point: run an agent (single or multi topology)
│   ├── config.py / models.toml       DB settings + model registry (gitignored; see *.example)
│   └── tests/
│
├── benchmark/     Neuro-Air-focused PV slice + reproduction scripts
│   ├── evals/neuroair/               frozen ground-truth validators (5 categories, HB + HK)
│   ├── benchmarks_neuroair*.json     the 90-task ablation and its variants
│   ├── experiments/Neuro-Air/        archived run outputs + per-task pass/fail matrix
│   ├── analysis/                     blinded human-evaluation statistics notebook + data
│   └── scripts/                      Table 2 / Supplementary Table 8 / bootstrap reproduction
│
├── evaluation/    Response-quality (LLM-judge) + objective process metrics
│   ├── evaluate.py                   three-judge panel (Kimi-K2, Claude, Qwen)
│   ├── objective_metrics.py          deterministic log parsing (no LLM/human)
│   ├── recompute.py / ranking.py     scoring utilities
│   ├── constants.py                  judge API keys (gitignored; see *.example)
│   └── eval_results/                 judge outputs
│
├── EXPERIMENTS.md    complete experiment inventory (E1–E7), mapped to paper results
├── pyproject.toml    root env (matplotlib/numpy) for local analysis scripts
└── README.md
```

`framework/` only **generates** runs; all grading lives in `benchmark/` (PV) and
`evaluation/` (RQ + process metrics).

## 

Two design points matter for the ablation:

- **Matched budget.** The multi-agent arm shares the *same* total step budget as
  the single agent (default 20). It spends part of that budget on independent
  verification rather than on extra producer workers — so any accuracy gain is
  attributable to the topology, not to more compute.
- **Shared-runtime discipline.** Workers reuse staged variables by name and never
  clobber another worker's values or store a silent zero/empty; only the verifier
  is permitted to re-derive and overwrite.

---

## Requirements

- **Python** 3.12+ (`framework`, `benchmark`, `evaluation`); the root analysis
  env targets 3.13.
- [**uv**](https://docs.astral.sh/uv/) for dependency management — each package
  is independently `uv`-managed with its own `pyproject.toml` and lockfile.
- **PostgreSQL + PostGIS** for the HK/HB domains (read-only access). The Beijing
  domain is DataFrame-based and needs no database.
- OpenAI-compatible API endpoints for every backbone and judge model.

Each package is self-contained; install the one(s) you need:

```bash
cd framework   && uv sync      # or: cd benchmark && uv sync   / cd evaluation && uv sync
```

---

## Configuration

Real credentials are **gitignored**; copy the `*.example` templates and fill in
your own.

```bash
# framework/ and benchmark/
cp models.toml.example models.toml     # model registry: api_model, api_key, base_url, temperature
cp config.py.example   config.py       # database connection settings

# evaluation/
cp constants.py.example constants.py    # judge API keys (inlined)
```

In `models.toml`, the section header (e.g. `[claude-sonnet-4-6]`) is the registry
key passed to `--model`, and it also drives foundation-lab inference for the
optional same-lab judge exclusion (`claude-*` → anthropic, `deepseek-*` →
deepseek, …). All endpoints are talked to via the OpenAI SDK.

**Database access is read-only throughout.** Validators recompute ground truth
from the database on every call; the agents cannot mutate the data of record.

---

## Usage

### 1. Run the Neuro-Air agent (`framework/`)

```bash
cd framework

# Multi-agent topology (the full Neuro-Air system)
uv run python -m scripts.run --domain HK --model claude-sonnet-4-6 --topology multi

# Single-agent baseline (matched ablation arm)
uv run python -m scripts.run --domain HK --model claude-sonnet-4-6 --topology single

# Scope to a category or specific benchmarks; nest --exp to separate arms/repeats
uv run python -m scripts.run --domain HB --model deepseek --category spatial_analysis \
    --topology multi --exp Neuro-Air/multi-agent/run1

# Resume (auto-skips completed benchmarks); or force a full re-run
uv run python -m scripts.run --domain HK --model gemini --exp exp1
uv run python -m scripts.run --domain HK --model gemini --exp exp1 --no-skip
```

Results are written to
`experiments/{exp_id}/{domain}/{category}/{benchmark}/{model}_{timestamp}.json`,
one entry per turn with `actual_response`, `runtime_variables`,
`validator_result`, and `validation_errors`. Inspect them with:

```bash
uv run python -m scripts.run_stats --exp exp1 --domain HK
uv run python -m scripts.run_stats --exp exp1 --failures
```

### 2. Reproduce the architecture ablation (`benchmark/`)

```bash
cd benchmark && uv sync

# DB-free (reads archived runs): Table 2 counts, Supplementary Table 8,
# and the pooled-gain bootstrap CI [+3.6, +9.3] pp
uv run python scripts/_category_table.py
uv run python scripts/_cluster_bootstrap.py

# DB-backed (needs config.py + a read-only DB): replay the frozen validators
# to rebuild the per-task pass/fail matrix
uv run python scripts/_export_pv_matrix_dbfree.py
```

### 3. Response quality + objective process metrics (`evaluation/`)

```bash
cd evaluation && uv sync

# LLM-judge panel (response quality) over generated transcripts
uv run python evaluate.py

# Objective process metrics — deterministic, no LLM
uv run python objective_metrics.py --exp ../framework/experiments
```

### 4. Human-evaluation statistics

```bash
cd benchmark/analysis
# 32 responses × 15 blinded experts (needs pandas, xlrd, pingouin, krippendorff, scipy)
jupyter notebook compute_human_eval_R1-3.ipynb
```

---

## Reproducing the paper

`EXPERIMENTS.md` is the authoritative inventory: it lists all seven experiments
(E1 automated multi-judge; E2 blinded human evaluation; E3 single- vs
multi-agent ablation; E4 execution-paradigm comparison; E5 objective process
metrics; E6–E7 the two case studies), their scale, purpose, headline result, and
the statistical methods used, each cross-referenced to the corresponding figure,
table, and section of the manuscript.

---

## Data availability

The Hong Kong datasets are publicly available from the cited open-data sources
(HKEPD, CSDI, Hong Kong Transport Department, Hong Kong Observatory,
OpenStreetMap, HKED). The raw environmental monitoring records for Hebei Province
were obtained from the Department of Ecology and Environment of Hebei Province
under restricted access and are **proprietary — not redistributed in this
repository**. Processed, aggregated results supporting the findings are reported
in the paper's Supplementary Information; further processed subsets may be
requested from the corresponding author subject to the data provider's approval.

The bulk population/POI grids under `framework/datasets/` are **not tracked in
git** (they exceed GitHub's file-size limit); obtain them from their original
sources — WorldPop population grids and OpenStreetMap-derived POI. Any
redistribution must preserve the WorldPop (CC BY 4.0) and OpenStreetMap (ODbL
1.0) attribution required by their licenses.

---

## Citation

Ma, C., Ran, M., Song, J., Gao, M. *Multi-agent AI for End-to-End Air Quality
Analysis and Decision Support.* (Under review, npj Clean Air.)

```bibtex
@article{neuroair,
  title   = {Multi-agent AI for End-to-End Air Quality Analysis and Decision Support},
  author  = {Ma, Chendong and Ran, Maohao and Song, Jun and Gao, Meng},
  year    = {2026},
  note    = {Under review}
}
```

---

## License

MIT License (see `framework/LICENSE` and `benchmark/LICENSE`).
