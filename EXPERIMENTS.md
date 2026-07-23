# Neuro-Air: Complete Experiment Inventory

All experiments conducted for the study *Multi-agent AI for End-to-End Air Quality
Analysis and Decision Support*, including those added during major revision.
Numbers match the revised manuscript; entries marked † are operational details taken from the underlying analysis records rather than the paper text.

## Overview

| # | Experiment | Scale | Purpose | Key result |
|---|---|---|---|---|
| E1 | Automated multi-judge evaluation | 317 queries × 4 backbones × 3 judges × 3 repeats | System-level quality across backbones | >70% every configuration, >85% majority; judge consistency α = 0.97 |
| E2 | Blinded human expert evaluation | 32 responses × 15 experts (fully crossed) | Calibrate the automated judges against professionals | r = 0.47; judges lenient by +0.24; ICC(2,15) = 0.90 |
| E3 | Single- vs multi-agent architecture ablation (on the purpose-built PV benchmark) | 900 runs (90 tasks × 5 backbones × 2 arms) | Isolate the value of the multi-agent architecture with judge-free scoring | +6.4 pp pooled [+3.5, +9.5], McNemar p = 2.5×10⁻⁵ |
| E4 | Execution-paradigm comparison | 702 vs 118 runs† (same HK pool) | Isolate native code execution vs function calling | Error runs 1.7% vs 45.8% (27×) |
| E5 | Objective process metrics | 1,902 runs (317 × 6 backbones), rule-based parser | Deterministic reliability/faithfulness measurement | 99.3% first-attempt success; 97.4% numeral traceability |
| E6 | Case study 1: acute fire event (+ expert re-validation) | Tai Po Wang Fuk Court fire, six-day window, 18 stations | End-to-end emergency screening, then formal validation | Screening signal confirmed modest: z = 1.9; PM2.5 fingerprint +7.4 µg/m³ |
| E7 | Case study 2: industrial emission screening (+ verification) | Tianjin Iron Co. (She County, Handan), 72 h, 18 stations | End-to-end source–receptor association screening | Empirical 3-h lag r = 0.83; wind-unfavorable null reported |

---

## I. System-level evaluation

### E1: Automated multi-judge benchmark evaluation

**Design.** 317 real-world queries (200 Hebei, 117 Hong Kong) spanning six
functional domains, derived from practitioner interviews, government
documentation, and citizen inquiries. Each query is processed end-to-end by
Neuro-Air on four foundation-model backbones (GPT-5, Claude 4 Sonnet,
Gemini 2.5 Pro, DeepSeek-V3; temperature 0.2, August 2025 snapshots) and scored
independently by three LLM judges (Kimi-K2, Claude 4 Sonnet, Qwen3) on five
dimensions; the final score averages the three judges, and the entire procedure
is repeated three times and averaged.

**Results.** Every configuration exceeds an aggregate score of 70%, the
majority exceed 85%. Judge reliability: mean inter-rater correlation 0.93,
Cronbach's α = 0.97; t-based 95% CIs on per-backbone means all narrower than
±1.5 points. (Results §2.5; Extended Data Fig. S1.)

### E2: Blinded human expert evaluation (re-run during revision)

**Design.** The original anchored evaluation was discarded; the study was
re-run blinded. Fifteen active environmental-management professionals (five
atmospheric analysts, five data engineers, five policymakers; recruited through
the Hebei Provincial Department of Ecology and Environment and the Hong Kong
Generative AI R&D Center) each scored all 32 items of a difficulty-weighted
calibration subset (11 HK, 21 Hebei) on a holistic 1–10 scale, blinded to the
automated scores, with three disjoint calibration examples and counterbalanced
item order.

**Results.** Blinded human–AI agreement is moderate: Pearson r = 0.47
[0.15, 0.71], Spearman ρ = 0.56, Kendall τ = 0.46. The automated judges are
systematically lenient: Bland–Altman bias +0.24 on the 0–1 scale, fitted slope
0.54. Inter-rater reliability: ICC(2,1) = 0.38 (single expert, noisy) but
ICC(2,15) = 0.90 (panel mean, reliable); Krippendorff's α = 0.37. The review
also produced an expert-derived failure-mode taxonomy (transport reasoning
substituted by proximity/correlation, spatial-join unit errors,
temporal–causal mismatches, missing premise validation). (Results §2.5;
Fig. 6b; Extended Data.)

---

## II. Controlled and objective verification

### E3: Matched single-agent vs multi-agent architecture ablation

**Instrument (built for this experiment): the programmatically verified (PV)
benchmark.** A 90-task subset (78 Hebei, 12 HK; five categories: spatial 27,
data retrieval 20, comparative 18, statistical 16, temporal 9) of the 317-query
benchmark, retaining only tasks with a uniquely determined,
database-recomputable answer. For each task an expert wrote and reviewed a
reference program (SQL + Python) blind to any model output; the reviewed
program itself was locked in as the task's validator. At scoring time the
validator recomputes the ground truth live from the database and compares the
agent's stored values under per-task tolerances (typically 0.5–2% relative;
counts and identifiers exact). A ground-truth audit applied only
strictly-relaxing fixes; the frozen set was applied uniformly to all 900 runs.
No LLM judge and no human rating enter the score. This instrument also serves
as the paper's judge-free objective-correctness channel (multi-agent pooled
accuracy 88.4%). (Fig. 5; Methods.)

**Design.** The complete Neuro-Air topology (coordinator + five specialized
workers + in-loop computational auditing) versus a single agent with all roles
merged, holding backbone, temperature, database, persistent Python runtime,
byte-identical system prompt, 20-step budget, and single attempt per task
identical. Five contemporary backbones spanning four model families
(DeepSeek-V4-Flash, GPT-5.5, Qwen3.6-35B-A3B, Qwen2.5-72B, Qwen3.5-397B-A17B);
900 runs scored on the PV benchmark above.

**Results.** Accuracy improves on every backbone (+3.3 to +10.0 pp). Two
backbones are individually significant (p = 0.031 each; unadjusted, read
descriptively). Pooled:
82.0% → 88.4%, +6.4 pp (Newcombe 95% CI +3.5 to +9.5; exact McNemar
p = 2.5×10⁻⁵; 38 vs 9 discordant tasks). A task-level cluster bootstrap
(B = 100,000) gives +3.6 to +9.3, confirming negligible task-induced
correlation. Gains trend larger on weaker backbones (tie-adjusted Spearman
ρ = −0.87; directional at n = 5, permutation p = 0.067); a ~3B-active-parameter
model under the architecture reaches the accuracy band of an ~11× larger model
(parity, overlapping CIs). Repairs concentrate in spatial analysis and
statistical characterization (repair rates 11.1%/11.3% vs 4.4–7.0%); all nine
regressions are spatial; six tasks repaired under ≥2 backbones. Cost: the
multi-agent arm consumes 3.3–4.4× median tokens per task. (Table 2; Fig. 6a,c,d;
Extended Data Tables S7–S8; Methods.)

### E4: Execution-paradigm comparison (native Python vs function calling)

**Design.** The second, orthogonal ablation axis: on the identical 117-query
Hong Kong pool, native Python execution (six backbones, n = 702 runs†) versus a
JSON function-calling baseline (n = 118 runs†; single backbone, identity not
recorded, disclosed as quasi-experimental).

**Results.** First-attempt success 99.6% vs 91.5% (disjoint 95% CIs); runs with
≥1 error 1.7% vs 45.8% (27× relative); per-execution error rate 19× lower†;
median interaction rounds 3 vs 9†. Error taxonomy: 94.7% of function-calling
errors arise at the SQL/tool interface, a class that largely disappears under
native execution. (Table 1; Results "Objective Process Metrics".)

### E5: Objective process metrics (rule-based log analysis)

**Design.** A deterministic rule-based parser (Python stdlib only†) over the complete execution
logs of 1,902 runs (317 queries × six backbones: the four E1 models plus
Qwen3-235B-A22B and Kimi-K2). No LLM or human judgment.

**Results.** First-attempt code-execution success 99.3% (Wilson 95% CI
98.8–99.6%); in-loop error recovery 60/61 (98.4%); no run exhausted its step
budget. Of 42,893 salient numerals in final responses, 97.4% are traceable to
executed computational evidence (94.2% under strict matching). Median latency
71 s per query (p90 247 s; 96.3% within ten minutes). Pollution-transmission
queries are objectively hardest (97.7% first-attempt success, 8.1% error-run
rate, ~2.7× corpus average). Of 76 execution errors, 49 were security-guardrail
activations; the genuine code-failure rate is 1.3% of runs. Empty results
(6.0% of successful executions) are reported descriptively. (Results
"Objective Process Metrics"; Extended Data Table S9.)

---

## III. End-to-end case studies (with post-hoc expert validation)

### E6: Case study 1: Tai Po Wang Fuk Court fire (Hong Kong, acute event)

**System run.** Autonomous detection and screening of the 26 Nov 2025
five-alarm fire (first report 14:51 HKT, verified against three official press
releases†): pre/post segmentation, peak-to-mean screening signals (peak NO₂
123.2 µg/m³ at 20:00, 2.5× the pre-fire mean), proximity-based exposure
proxies, and public advisories. (Fig. 3; Algorithm 1.)

**Expert re-validation added in revision** (the screening-then-validation
workflow the paper advocates): (i) matched-hour historical baseline: the
fire-evening NO₂ value is z = 1.9 against the same clock hour over the
preceding 14 days, below that fortnight's matched-hour maximum (125.5 µg/m³);
(ii) 18-station network contrast (difference-in-differences style): a
territory-wide elevation of +19.6 µg/m³ that evening, with upwind stations
rising as much or more; (iii) hour-resolved meteorological reconstruction:
northeast-monsoon flow weakening to near calm (stagnation), with the system's
"westerly 8.5 m/s" traced to a faithful but too-coarse 24-h aggregate;
(iv) the defensible local signal: a combustion-specific PM2.5 fingerprint,
the nearest station ranking 1st of 18 in evening PM2.5 elevation
(+7.4 µg/m³ above the network mean rise). AQHI remained moderate (5–6).

### E7: Case study 2: industrial emission screening (Tianjin Iron Co., She County, Handan)

**System run.** Exploratory source–receptor association for CO emissions over
6–8 Jan 2026: geofenced screening of 18 stations within 20 km, emission–
concentration cross-correlation (strongest receptor r = 0.77, rising to 0.83
at an empirical 3-hour lag of maximum correlation), and a high- vs low-emission
contrast (67th/33rd percentile thresholds, contemporaneously aligned hours).
(Fig. 4; Algorithm 2.)

**Verification analyses added in revision.** The wind query returned zero
records (the "downwind" label was a geometric bearing, not meteorology); no
Gaussian plume computation exists in the code, so all attribution language was
renamed to exploratory association accordingly. A companion run under
transport-unfavorable wind is reported as a null result (r = 0.777, n = 62,
vs r = 0.640, n = 8 favorable), and the ~72-observation insufficiency
(autocorrelation, shared meteorological forcing, max-selection across stations
and lags) is stated explicitly.

---

## Statistical methods used across experiments

Wilson score intervals for proportions; exact two-sided McNemar tests on paired
task outcomes (per backbone and pooled); Newcombe MOVER intervals for paired
proportion differences; task-level cluster bootstrap (B = 100,000, fixed seed)
for cross-backbone clustering; exact permutation test for the capability–gain
Spearman correlation; Fisher-z and bootstrap CIs for human–AI correlations;
Bland–Altman agreement analysis; ICC(2,1)/ICC(2,15) and Krippendorff's α for
inter-rater reliability; t-based CIs for judge-score means. Per-backbone
p-values are unadjusted for multiplicity and read descriptively; each ablation
cell is a single stochastic draw at fixed temperature, so the architecture
conclusion rests on the pooled analysis replicated across five backbones.

## Not run (by design, disclosed in the paper)

- Multi-agent + function-calling crossed cell (confounds both ablation axes).
- Fixed deterministic workflow arm (removes coordinator adaptivity; future work).
- Repeat-run variance quantification on discordant tasks (declined; handled as
  a stated limitation plus cross-backbone replication).
- Compute-matched single-agent control (e.g., self-consistency at ~4× tokens;
  pre-empted by the early-termination analysis, acknowledged as untested).
