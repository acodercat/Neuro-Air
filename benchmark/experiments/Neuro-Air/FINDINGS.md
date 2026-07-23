# Single-Agent vs. Multi-Agent Ablation: Results and Findings

**Neuro-Air ablation study — addressing reviewer request R1-4 (isolate the contribution of the multi-agent architecture)**
Date: 2026-07-08 · Config fingerprint: `cee8f2b5b98a` (shared system prompt `67f53c62888b` + multi-agent adapter `33978b149bb1`)

---

## 1. Executive Summary

We compare a single-agent baseline against the Neuro-Air hierarchical multi-agent architecture (a central coordinator + 5 domain-specialized worker agents over a shared persistent Python runtime, with the framework's hallucination-mitigation layer instantiated as an in-loop computational-auditing pass) on **90 programmatically-verified (PV) real-world air-quality analysis tasks** (78 Hebei + 12 Hong Kong), across **five LLM backbones spanning four model families and a 51–92% single-agent accuracy range**.

**The multi-agent architecture improves accuracy on all five backbones (+3 to +9 tasks; pooled +6.4 pp, 95% CI [+3.5, +9.5], exact McNemar p = 2.5×10⁻⁵), with near-zero regression on capable backbones (0–2 regressions), and the largest gains on the weakest and smallest models.** Gains concentrate in the most compute-intensive task categories — spatial analysis and statistical characterization. A small 35B-A3B model equipped with the multi-agent architecture reaches **95.6%** — the same accuracy band as a ~11× larger 397B-A17B model (91.1% single, 94.4% multi; pairwise gaps within overlapping 95% CIs at n = 90) — supporting the paper's central claim that **architecture, not merely model scale, drives reliable autonomous air-quality analysis**.

---

## 2. Experimental Setup

### 2.1 Benchmark
- **90 programmatically-verified tasks** (`benchmarks_neuroair_ablation.json`): 78 Hebei (HB) + 12 Hong Kong (HK), spanning data retrieval, temporal pattern analysis, statistical characterization, spatial analysis, and comparative assessment.
- Each task requires the agent to store typed numeric/text outputs into registered runtime variables; free-text answers are never graded.

### 2.2 Programmatic verification (PV) and ground-truth construction
- **How ground truth is obtained.** Consistent with the paper's Hallucination Mitigation protocol ("empirical anchoring"), ground truth is established by *manually pre-executing SQL and Python queries directly against our curated environmental databases*: for each task, the relevant records were manually identified in the source dataset, a reference implementation (SQL + Python) was hand-written to compute the target quantities, and both the code and its outputs were then human-reviewed for correctness (entity identity, time-window boundaries, units, and aggregation semantics). The reviewed reference implementation — not its numeric output — is what ships inside the task's validator.
- **How scoring works.** At scoring time the validator **re-executes the reference implementation live against the PostGIS database** and compares the agent's stored variables under explicit numeric tolerances. Because ground truth is recomputed from the data rather than stored as constants, it is deterministic, auditable, and immune to transcription errors. No human judgment and no LLM judge are involved at scoring time.
- Validators are **identical for both arms** and are never visible to the agents: they play no role in generation and are applied only at scoring time. The validator set — including a small number of GT-audit fixes resolving genuine ambiguities (tied argmax, window-boundary conventions, dual counting conventions), each **strictly relaxing** (accepting additional semantically-legitimate answers, so a fix can only convert a false failure into a pass, never the reverse) and driven by review of the reference implementations rather than by either arm's outputs — was finalized at the start of the experimental campaign and then frozen; all reported numbers come from applying this single frozen set **uniformly to all 900 runs in one final DB-idle scoring pass**.

### 2.3 The two arms — matched everything except architecture
| Dimension | Single agent | Multi-agent |
|---|---|---|
| Backbone LLM, temperature | identical | identical |
| Tools (SQL/Python runtime), database | identical | identical |
| Shared system prompt (time-window & granularity conventions) | identical | identical |
| Execution-step budget | 20 steps | 20 steps total across all agents (auditing reserve 6, synthesis reserve 3) |
| Attempts | **1** | **1** |
| Architecture | one agent does everything | Central Coordinator → 5 domain-specialized worker agents — data acquisition (data pre-processing), knowledge retrieving, comprehensive air pollution modeling, multi-variate analysis, and synthesis and communication (visualization and report generation) — followed by an in-loop computational-auditing pass, all over one shared persistent Python runtime |

The agent roster mirrors the paper exactly (Central Coordinator + the 5 workers of the three functional modules: External Knowledge and Data Extraction; Analytical; Synthesis and Communication). The computational-auditing pass is the in-loop instantiation of the paper's Hallucination Mitigation layer ("strict computational auditing"): before outputs are finalized, each required variable is independently recomputed from the raw database and reconciled. Domain expertise (PostGIS geography semantics for the multi-variate environmental analysis agent; sum/peak/mean/exceedance/correlation definitions for the air pollution modeling agent) lives **inside the worker roles**. These are generalizable schema/convention facts — the legitimate substance of role specialization — not task-specific hints; the auditing pass is fully generic (independent recomputation + plausibility checks, no per-task knowledge).

### 2.4 Scoring protocol (measurement hygiene)
- All final scores computed **with the database idle** (concurrent generation causes validator timeouts that masquerade as failures; we identified and eliminated this artifact).
- **Endpoint failures** (provider-side connection errors → `steps = 0`, zero tokens, empty variables) are *infrastructure* failures, not model failures: the affected tasks were deleted and re-run serially until every arm contains 90 genuinely-executed tasks. Final runs: **0 generation failures, 0 validator errors, 90/90 tasks per arm per model.**
- Statistical test: exact two-sided McNemar on paired task outcomes (the correct test for paired binary data; it uses only discordant pairs).

---

## 3. Main Results

### Table 1 — Overall accuracy (90 tasks, single attempt per arm)

Cells show accuracy % with the **95% confidence interval** in brackets (raw correct-task counts recoverable as acc%×90 per backbone, ×450 for the pooled row). "Wins / Losses" count the discordant tasks — those one arm solved and the other failed — which are exactly what McNemar's test uses. Accuracy CIs are **Wilson score** intervals (appropriate near the ceiling, where the normal approximation fails); the **Gain** CI is the **Newcombe MOVER** interval for the difference of two *paired* proportions (it accounts for the pairing, unlike an independent-samples interval).

| Backbone | Single acc [95% CI] | Multi acc [95% CI] | Gain [95% CI] | Wins / Losses | McNemar p |
|---|---:|---:|:---:|:---:|:---:|
| deepseek-v4-flash | 86.7% [78.1, 92.2] | 93.3% [86.2, 96.9] | **+6.7 [+1.4, +13.3]** | 6 / 0 | **0.031** |
| gpt-5.5 | 92.2% [84.8, 96.2] | 97.8% [92.3, 99.4] | +5.6 [−0.4, +12.8] | 6 / 1 | 0.125 |
| qwen3.6-35b (35B-A3B) | 88.9% [80.7, 93.9] | 95.6% [89.1, 98.3] | **+6.7 [+1.5, +13.5]** | 6 / 0 | **0.031** |
| qwen-2.5-72b | 51.1% [41.0, 61.2] | 61.1% [50.8, 70.5] | +10.0 [+0.2, +19.4] | 15 / 6 | 0.078 |
| qwen3.5-397b (397B-A17B) | 91.1% [83.4, 95.4] | 94.4% [87.6, 97.6] | +3.3 [−2.9, +10.3] | 5 / 2 | 0.453 |
| **Pooled (5 backbones, 450 pairs)** | **82.0% [78.2, 85.3]** | **88.4% [85.2, 91.1]** | **+6.4 [+3.5, +9.5]** | **38 / 9** | **2.5×10⁻⁵** |

*CI reading.* Two backbones (deepseek, qwen3.6-35b) have a **gain CI that excludes 0** (consistent with their p = 0.031); qwen-2.5-72b just excludes 0 (lower bound +0.2, McNemar p = 0.078, i.e. borderline); gpt-5.5 and qwen3.5-397b have **gain CIs spanning 0** — individually inconclusive. The evidence for the architecture effect is therefore carried by the **pooled** estimate (+6.4 pp, CI excludes 0 with margin), not by any single small backbone. The pooled gain CI is the deterministic paired-Newcombe interval; a **cluster-bootstrap-by-task** robustness check — resampling whole tasks, so the correlation among the 450 pairs induced by shared tasks is respected rather than assumed away — yields an essentially identical interval, indicating that task-level clustering is weak.

### Table 2 — Cost (median per task; execution-step cap = 20 in both arms)

| Backbone | Single: steps / tokens | Multi: steps / tokens | Token ratio | Extra tokens per additional solved task |
|---|---|---|---|---|
| deepseek-v4-flash | 4 / 34.2k | 13 / 112.4k | 3.3× | 1.32M |
| gpt-5.5 | 2 / 18.7k | 9 / 79.4k | 4.2× | 1.23M |
| qwen3.6-35b | 5 / 40.8k | 16 / 142.9k | 3.5× | 1.38M |
| qwen-2.5-72b | 4 / 30.9k | 17 / 135.5k | 4.4× | 0.95M |
| qwen3.5-397b | 4 / 32.8k | 15 / 123.4k | 3.8× | 2.61M |

---

## 4. Findings

### F1. The architecture effect is positive on every backbone tested, and highly significant in aggregate.
All five backbones improve under the multi-agent architecture (+3 to +9 tasks). Two backbones reach per-model significance on their own (deepseek-v4-flash and qwen3.6-35b, p = 0.031 each); the pooled effect across 450 paired observations is unambiguous (38 wins vs. 9 losses among discordant pairs; p = 2.5×10⁻⁵). The direction never reverses. This is the direct, controlled answer to R1-4: **holding backbone, tools, data, prompts, attempt count, and step budget fixed, the multi-agent architecture alone accounts for a +6.4 pp accuracy gain.**

### F2. Smaller and weaker models benefit the most (ρ = −0.87; directional at n = 5).
The gain is anti-correlated with single-agent strength (tie-adjusted Spearman ρ = −0.87 across the five backbones): the weakest backbone (qwen-2.5-72b, single 51.1%) gains **+10.0 pp**, while backbones whose single-agent accuracy already exceeds 91% gain +3.3 to +5.6 pp. With only five backbones this correlation is a **directional trend, not an independently significant one** (exact two-sided permutation test, p = 8/120 = 0.067); we report it as suggestive and consistent with the per-category and mechanistic evidence below, not as an independently established result. The interpretation is mechanistic, not mysterious: the architecture supplies exactly what weak models lack — task decomposition, role-scoped domain conventions, and independent computational auditing — while strong models already get part of this right on their own, leaving less headroom. **Practically, this means the Neuro-Air architecture is a capability equalizer: it delivers governance-grade reliability without requiring frontier-scale models** (see F3).

### F3. Architecture substitutes for scale.
qwen3.6-35b (35B total, ~3B active parameters) under the multi-agent architecture reaches **95.6% [95% CI 89.1, 98.3]** — the same accuracy band as the ~11×-larger qwen3.5-397b (17B active; 91.1% single, 94.4% [87.6, 97.6] multi) and the frontier gpt-5.5 single agent (92.2%). The pairwise gaps sit within overlapping confidence intervals at n = 90, so the claim is parity, not superiority — and parity is all the argument needs: a 35B-A3B model *inside the architecture* occupies the same accuracy band as models an order of magnitude larger. **For deployment, a small open-weight model inside the Neuro-Air architecture is therefore a viable — cheaper and more controllable — alternative to a much larger single agent.**

### F4. Gains concentrate in the compute-intensive task categories.
Sorting the 38 multi-agent wins by the benchmark's native task categories, they cluster in **spatial analysis (15 wins), statistical characterization (9), and multi-step data retrieval (7)**, with comparative assessment (5) and temporal analysis (2) making up the remainder. The concentration survives normalizing by category size: per-pair win rates are **11.1%** for spatial analysis (15/135) and **11.3%** for statistical characterization (9/80) versus 4.4–7.0% elsewhere — not an artifact of spatial analysis being the largest category. These are precisely the categories that demand multi-table joins, geospatial computation, and multi-step aggregation — i.e., where a single context is most easily overloaded. This matches the designed mechanism: decomposition plus specialist expertise pays off on compositional tasks, not on simple lookups.

### F5. The improvement is near-monotone: multi rarely breaks what single gets right.
Across the four capable backbones (single ≥ 86%), the multi arm produces **23 wins against only 3 regressions** (deepseek 6/0, qwen3.6-35b 6/0, gpt-5.5 6/1, qwen3.5-397b 5/2). This asymmetry matters for governance deployment: an architecture that trades errors (fixing some tasks while breaking others) would be operationally risky even at equal accuracy; Neuro-Air's audit-gated pipeline instead behaves as a **strict enhancement layer**. Regression only becomes material on the weakest backbone (6 regressions vs. 15 wins), where the auditing pass itself occasionally miscomputes — see F6.

### F6. Failure anatomy: all regressions are spatial, and most belong to the weakest backbone.
All 9 regressions across all models fall in a single category — spatial analysis — and 6 of the 9 come from qwen-2.5-72b. Spatial analysis is simultaneously the *largest win category* (15 wins; net +6): geospatial tasks are where specialist knowledge helps most and where a weak backbone's auditing recomputation can still get the final reconciliation wrong. The residual multi-agent failures are idiosyncratic single-task misses (e.g., one bearing-convention miss for gpt-5.5), not a systematic blind spot shared across backbones. This localizes future work precisely: harden the spatial recomputation inside the computational-auditing pass.

### F7. The wins are architecture-attributable, not stochastic.
Six distinct tasks are fixed by the multi-agent arm under **two or more different backbones** (`hb_5_28` under three; `hb_1_1`, `hb_2_23`, `hb_5_11`, `hb_6_12`, `hb_7_35` under two each). Independent model families converging on the same repaired tasks is the signature of a *structural* mechanism (decomposition, worker-role conventions, computational auditing) rather than sampling luck — corroborated by the design being single-attempt at fixed temperature in both arms.

### F8. The cost of the architecture is bounded, interpretable, and buys a specific mechanism.
The multi arm consumes 3.3–4.4× the median tokens per task (median steps rise from 2–5 to 9–17, still under the same 20-step cap). The marginal price of each *additional solved task* is 0.95–2.6M tokens, cheapest exactly where gains are largest (weakest backbone: 0.95M). Two observations preempt the "just give the single agent more compute" objection:
1. **The single agent is not resource-starved.** Its median consumption is 2–5 steps of a 20-step budget — it terminates early because it *believes* it is done, not because it ran out. Its failures are silent semantic errors (wrong time window, wrong aggregation, geometry-unit corruption), which additional budget does not repair because the agent never detects them.
2. **The extra tokens are the mechanism, not slack.** They are spent on independent recomputation in the auditing pass and on specialist worker consultations — i.e., on redundancy that detects and repairs silent errors. Equal-token, same-architecture comparisons would remove the very object under study.

---

## 5. Robustness and Threats to Validity

- **Measurement artifacts eliminated.** Scoring concurrent with generation inflates failures via database contention. We quantified this on a preliminary configuration: the same run's multi-vs-single delta read −7 when scored during generation but +4 when re-scored with the database idle — an 11-task swing caused purely by validator timeouts. All reported numbers therefore come from DB-idle scoring passes. Provider-side endpoint failures (zero-step runs) were detected via stored execution metrics, excluded symmetrically, and re-run until absent.
- **No answer leakage.** The auditing pass contains no task-specific information; worker-role prompts contain only schema/convention knowledge (e.g., "PostGIS `geography` distances are in metres; use `ST_Distance(a,b)/1000` for km"), applicable to any task in the domain and available to *any* competent implementer. The shared system prompt is byte-identical between arms (fingerprinted).
- **Paired, exact statistics with interval estimates.** McNemar's exact test on paired outcomes per backbone plus a pooled test across 450 pairs; no Gaussian approximations at these sample sizes. All accuracies and gains carry 95% CIs (Wilson; paired Newcombe, cross-checked by a cluster-bootstrap-by-task robustness pass for the pooled gain — see Table 1), and every claim in this report is scoped to what its interval supports.
- **Model diversity.** Four model families (DeepSeek, OpenAI, Qwen-3.x-MoE, Qwen-2.5-dense), open and closed weights, 51–92% baseline range. The effect holds across all of them.
- **Honest limitations.** (i) Per-model significance is reached by two of five backbones; gpt-5.5 (p = 0.125, 6/1 discordants) and qwen-2.5-72b (p = 0.078) show strong directional trends that a larger benchmark may confirm; qwen3.5-397b's +3 is not individually significant. The pooled analysis is the primary claim. (ii) n = 90 tasks from two regions; broader geographic replication is future work. (iii) As single-agent accuracy approaches the benchmark ceiling, the architecture's headroom shrinks by construction (F2); the benefit claim is strongest for the realistic deployment regime of small-to-mid-scale backbones.
---

## 6. Reproducibility

- **Canonical results layout:** `experiments/Neuro-Air/{model}/{single|multi}/run1/` — one JSON per task containing the query, all executed code (`code_snippets`), stored `runtime_variables`, per-task token/step `metrics`, and the stored validator outcome.
- **Config provenance:** shared prompt sha1 `67f53c62888b`; multi-agent adapter sha1 `33978b149bb1`; combined fingerprint `cee8f2b5b98a`. All five models ran under this single frozen configuration; no per-model tuning of any kind.
- **Re-scoring:** `scripts/_final_all.py` recomputes the entire results table (including McNemar) from the raw run directories against the live database.
- **Benchmark definition:** `benchmarks_neuroair_ablation.json` (90 tasks with their native categories).

---

## 7. One-Paragraph Response Skeleton for R1-4

> Following the reviewer's request, we added a controlled ablation that isolates the multi-agent architecture. Holding the backbone LLM, tools, database, prompts, sampling temperature, attempt count, and execution budget identical, we compare Neuro-Air's coordinator + five specialized worker agents with in-loop computational auditing against a single-agent baseline on 90 programmatically-verified real-world tasks, across five backbones from four model families. The architecture improves accuracy on every backbone (+3 to +9 tasks; pooled +6.4 pp, 95% CI [+3.5, +9.5]; exact McNemar p = 2.5×10⁻⁵) with near-zero regression on capable backbones, and the gains concentrate in the most compute-intensive task categories (spatial analysis, statistical characterization, multi-step retrieval). The gains trend larger for smaller/weaker backbones (Spearman ρ = −0.87; directional at n = 5, exact permutation p = 0.067), and a 35B-A3B model inside our architecture reaches the same frontier accuracy band (95.6%) as a model an order of magnitude larger — evidence consistent with the reported capability deriving from the architecture itself rather than from model scale.
