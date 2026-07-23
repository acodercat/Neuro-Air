# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

The Neuro-Air project: a hierarchical multi-agent LLM framework for urban air-quality analysis, plus the **npj Clean Air manuscript** describing it. Layout:

- **`manuscript/`** — the paper and everything needed to build it (see below). Nearly all writing work happens here.
- **`benchmark/`** — the 90-task programmatically verified (PV) benchmark, single- vs multi-agent ablation runs, validators, and reproduction scripts (`benchmark/scripts/`). Has its own `.venv`.
- **`framework/`** — the Neuro-Air agent framework (near-duplicate of benchmark's evals; differs by `PythonRuntime`→`IPythonRuntime` rename).
- **`evaluation/`** — LLM-judge evaluation pipeline, raw run logs (`logs_to_eval/`), judge outputs (`eval_results/`), objective process metrics.
- **`reviews/`** — review-related internal documents (incl. `REVIEWER_ANALYSIS_AND_REVISION_RECOMMENDATIONS.md`).
- **`Neuro-Air_submission_clean.zip`** — the submission package (regenerate from `manuscript/`, see below).
- Root `pyproject.toml`/`.venv` — utility Python env (has matplotlib/pandas/scipy; used by figure scripts).

The original August-2025 experiment runners live outside this repo in `~/Desktop/Workplace/Metaseq-agent/` (see `legacy/` there for per-backbone scripts).

## The manuscript (`manuscript/`)

- `main.tex` — the manuscript (npj Clean Air; Results/Methods use **primary subheadings only**). Build with **pdflatex** via latexmk.
- `supplementary.tex` — Supplementary Information source. **Must be built with `latexmk -xelatex`** (uses fontspec; pdflatex fatals). Inputs `si_build/notes345.tex` (Notes 3–5) and uses `figure/judges.png`, `figure/backbone_scores.pdf`.
- `supplementary.pdf` — the single merged SI PDF required by npj (Notes 1–5, Tables 1–10, Figures 1–2 + Supplementary References). Every SI item must be cited in `main.tex`; keep the two-way mapping exact.
- `figure/` — all figures (6 main-text + 2 SI-only: `judges.png`, `backbone_scores.pdf`).
- `scripts/` — figure generators (`make_backbone_scores_figure.py` regenerates SI Fig 1 from `evaluation/eval_results/`; run from repo root with the root `.venv`).
- `Response_to_Reviewers.docx` — original letter; `Response_to_Reviewers_aligned.docx` — numbering-aligned version to submit.
- `修改说明_CHANGES.md` — full change log of the 2026-07 revision rounds (8 rounds; includes decisions NOT to disclose certain items and the rationale — read before re-litigating any wording).
- `sciencemag.bst`, `scicite.sty` — do not edit.

### Building

```bash
cd manuscript
latexmk -pdf main.tex               # manuscript (49 pp; expect 0 undefined, 0 overfull)
latexmk -xelatex supplementary.tex  # SI (46 pp) — xelatex, NOT pdflatex
latexmk -c                          # clean aux files
```

### Regenerating the submission zip

Package contains ONLY: `main.tex`, `main.bbl`, `main.pdf`, `science_template.bib`, `sciencemag.bst`, `scicite.sty`, `supplementary.pdf`, and the 6 main-text figures (NOT `judges.png`/`backbone_scores.pdf`, NOT the letters/scripts/CHANGES). After any edit, rebuild both PDFs, then rebuild the zip and verify it compiles standalone from a scratch unpack.

## Conventions and constraints

- Supplementary items are labelled/cited uniformly as "Supplementary Table/Figure/Note N" (npj requirement — never "Table S1"/"A1"/"Supplementary Material Table").
- Results and Methods: primary subheadings only; no bolded/numbered pseudo-headings.
- No new `\usepackage`; author rows use `\and`; no references in the abstract.
- Numbers in the text are tied to archived computations — key reproduction scripts: `benchmark/scripts/_category_table.py` (hard-asserts published ablation numbers), `_cluster_bootstrap.py`, `_emission_lag_contrast.py` (industrial-case lag/BH/bootstrap reanalysis; needs the restricted HB database via `benchmark/domains/HB/db.py`).
- The HB database is restricted; HK data is public. Reproducibility is three-tiered (see Code Availability in `main.tex`).
