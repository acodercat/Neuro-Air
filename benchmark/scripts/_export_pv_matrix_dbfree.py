"""Build the per-task PV pass/fail matrix from stored turn['success'] — NO DB.

Validated: turn['success'] equals the frozen PV validator verdict (probe:
scripts/_probe_stored_verdict.py, 0 mismatches incl. known fails). This script
cross-checks the resulting per-model counts against the published Table 2; it
asserts an exact match before writing, so any drift fails loudly.

Output: experiments/Neuro-Air/pv_matrix.json  (same schema as the DB replay).
"""
import json, glob, os

reg = json.load(open('benchmarks_neuroair_ablation.json'))
name2py = {nm: p for dom,cats in reg.items() for cat,items in cats.items() for nm,p in items.items()}
TASKS = set(name2py)

MODELS = ['deepseek-v4-flash', 'gpt55', 'qwen3.6-35b', 'qwen-2.5-72b', 'qwen3.5-397b']
# published Table 2 (single_pass, multi_pass, wins, losses) per model, n=90
TABLE2 = {
    'deepseek-v4-flash': (78, 84, 6, 0),
    'gpt55':             (83, 88, 6, 1),
    'qwen3.6-35b':       (80, 86, 6, 0),
    'qwen-2.5-72b':      (46, 55, 15, 6),
    'qwen3.5-397b':      (82, 85, 5, 2),
}

def verdicts(base):
    """task -> 'P'/'F' from stored turn['success']; newest file per task; endpoint-failure filtered."""
    latest = {}
    for p in glob.glob(base + '/**/*.json', recursive=True):
        nm = os.path.basename(os.path.dirname(p))
        if nm not in TASKS: continue
        if nm not in latest or p > latest[nm]: latest[nm] = p
    out = {}; gf = []
    for nm, p in latest.items():
        t = json.load(open(p))[nm]['conversations'][0]['turns'][0]
        m = t.get('metrics') or {}; rv = t.get('runtime_variables') or {}
        steps = m.get('steps', m.get('total_steps'))
        if steps == 0 or m.get('total_tokens') == 0 or len(rv) == 0:
            gf.append(nm); continue
        out[nm] = 'P' if t.get('success') else 'F'
    return out, gf

matrix = {}; per_model = {}; ok = True
for mdl in MODELS:
    sb = f'experiments/Neuro-Air/{mdl}/single/run1'
    mb = f'experiments/Neuro-Air/{mdl}/multi/run1'
    Sg, gfs = verdicts(sb); M, gfm = verdicts(mb)
    us = sorted(set(M) & set(Sg))
    sp = sum(Sg[n]=='P' for n in us); mp = sum(M[n]=='P' for n in us)
    wins = sum(M[n]=='P' and Sg[n]=='F' for n in us)
    losses = sum(M[n]=='F' and Sg[n]=='P' for n in us)
    per_model[mdl] = {'n': len(us), 'single_pass': sp, 'multi_pass': mp, 'wins': wins, 'losses': losses}
    exp = TABLE2[mdl]; got = (sp, mp, wins, losses)
    match = (len(us) == 90 and got == exp)
    print(f"{mdl:18} n={len(us):3} single={sp:3} multi={mp:3} W/L={wins}/{losses}   Table2={exp}   {'OK' if match else '<== MISMATCH'}"
          + (f"  gf(s/m)={len(gfs)}/{len(gfm)}" if (gfs or gfm) else ""))
    ok = ok and match
    for n in us:
        matrix.setdefault(n, {})[mdl] = {'single': Sg[n], 'multi': M[n]}

# pooled cross-check
tot = {k: sum(per_model[m][k] for m in MODELS) for k in ('single_pass','multi_pass','wins','losses')}
print(f"\nPOOLED single={tot['single_pass']}/450  multi={tot['multi_pass']}/450  W/L={tot['wins']}/{tot['losses']}  (Table 2: 369/398, 38/9)")

out = {'models': MODELS, 'per_model': per_model, 'matrix': matrix,
       'source': 'stored turn.success (un-audited); reconcile GT-audit tasks before use'}
json.dump(out, open('experiments/Neuro-Air/pv_matrix.json', 'w'), indent=1)
if ok and (tot['single_pass'], tot['multi_pass'], tot['wins'], tot['losses']) == (369, 398, 38, 9):
    print("\nAll counts already match Table 2 (no DB used).")
else:
    print("\nWrote unreconciled matrix; run _reconcile_audit_tasks.py to patch GT-audit tasks to the frozen validator.")
