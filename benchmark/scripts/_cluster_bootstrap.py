"""Task-level cluster bootstrap for the pooled multi vs single accuracy gain.

Reads the per-task pass/fail matrix (experiments/Neuro-Air/pv_matrix.json,
produced by _export_pv_matrix.py). Resamples TASKS with replacement, carrying
each resampled task's full row of backbone x arm outcomes intact, so the
within-task correlation across the five backbones is preserved. No DB access.

Reports the pooled gain point estimate and the cluster-bootstrap 95% percentile
CI, alongside the analytic Newcombe interval for comparison. Deterministic
(fixed seed); B configurable.
"""
import json, numpy as np

MAT = "experiments/Neuro-Air/pv_matrix.json"
B = 100_000
SEED = 20260709

d = json.load(open(MAT))
models = d["models"]
matrix = d["matrix"]

# keep only tasks present for all backbones (balanced clusters)
tasks = [t for t, mm in matrix.items() if all(m in mm for m in models)]
tasks.sort()
K = len(tasks)
nb = len(models)
print(f"tasks (all {nb} backbones present): {K}; pairs = {K*nb}")

# per-task arrays: single[t, b], multi[t, b] in {0,1}
single = np.zeros((K, nb), dtype=np.int8)
multi = np.zeros((K, nb), dtype=np.int8)
for i, t in enumerate(tasks):
    for j, m in enumerate(models):
        single[i, j] = 1 if matrix[t][m]["single"] == "P" else 0
        multi[i, j] = 1 if matrix[t][m]["multi"] == "P" else 0

# point estimate: pooled gain = mean(multi) - mean(single) over all K*nb pairs
gain_point = 100 * (multi.mean() - single.mean())
sp = int(single.sum()); mp = int(multi.sum()); N = K * nb
print(f"pooled single {sp}/{N} ({100*sp/N:.1f}%)  multi {mp}/{N} ({100*mp/N:.1f}%)  gain {gain_point:+.2f} pp")

# discordant counts (pooled) for sanity vs Table 2 (38/9)
wins = int(((multi == 1) & (single == 0)).sum())
losses = int(((multi == 0) & (single == 1)).sum())
print(f"pooled discordants: wins(multi-only)={wins}  losses(single-only)={losses}")

# cluster bootstrap by task
rng = np.random.default_rng(SEED)
diff_per_task = (multi - single).mean(axis=1)          # not used directly; keep rows intact instead
gains = np.empty(B)
idx_all = np.arange(K)
for b in range(B):
    idx = rng.choice(idx_all, size=K, replace=True)
    gains[b] = multi[idx].mean() - single[idx].mean()
gains *= 100
lo, hi = np.percentile(gains, [2.5, 97.5])
print(f"cluster-bootstrap 95% CI (B={B:,}, seed={SEED}): [{lo:+.2f}, {hi:+.2f}] pp   (mean {gains.mean():+.2f}, sd {gains.std(ddof=1):.2f})")
print(f"Newcombe analytic (paper): [+3.5, +9.5] pp")
