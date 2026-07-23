"""Replay the frozen PV validators and export the per-task pass/fail matrix.

Reuses the exact scoring logic of scripts/_final_all.py (same validator loader,
same runtime_variables stub, same newest-file dedup, same endpoint-failure
filter). Produces a task x (backbone,arm) matrix of 'P'/'F' plus the aggregate
counts, so downstream analysis (cluster bootstrap) needs no further DB access.

Read-only: validators issue SELECTs only. Output: experiments/Neuro-Air/pv_matrix.json
"""
import json, glob, os, importlib.util, re

reg = json.load(open('benchmarks_neuroair_ablation.json'))
name2py = {nm: os.path.splitext(p)[0]+'.py' for dom,cats in reg.items() for cat,items in cats.items() for nm,p in items.items()}

def co(v):
    m = re.match(r'^np\.\w+\((.+)\)$', v.strip()) if isinstance(v, str) else None
    return float(m.group(1)) if m else v

class S:
    def __init__(s, d): s.d = {k: co(x) for k, x in d.items()}
    def retrieve(s, k): return s.d.get(k)

_vc = {}
def vf(nm):
    if nm in _vc: return _vc[nm]
    sp = importlib.util.spec_from_file_location('v_'+nm, name2py[nm]); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    _vc[nm] = list(m.validators.values())[0]; return _vc[nm]

def score(base):
    r = {}; gf = set(); latest = {}
    for p in glob.glob(base + '/**/*.json', recursive=True):
        nm = os.path.basename(os.path.dirname(p))
        if nm not in name2py: continue
        if nm not in latest or p > latest[nm]: latest[nm] = p
    for nm, p in latest.items():
        d = json.load(open(p)); k = list(d.keys())[0]; t = d[k]['conversations'][0]['turns'][0]
        m = t.get('metrics') or {}; rv = t.get('runtime_variables') or {}
        if (m.get('steps') == 0) or (m.get('total_tokens') == 0) or len(rv) == 0:
            gf.add(nm); continue
        try: r[nm] = 'P' if vf(nm)('', S(rv), None).success else 'F'
        except Exception: r[nm] = 'ERR'
    return r, gf

MODELS = ['deepseek-v4-flash', 'gpt55', 'qwen3.6-35b', 'qwen-2.5-72b', 'qwen3.5-397b']
matrix = {}   # task_id -> {model -> {'single':P/F, 'multi':P/F}}
per_model = {}
for mdl in MODELS:
    sb = f'experiments/Neuro-Air/{mdl}/single/run1'
    mb = f'experiments/Neuro-Air/{mdl}/multi/run1'
    if not (os.path.isdir(sb) and os.path.isdir(mb)): continue
    Sg, _ = score(sb); M, _ = score(mb)
    us = [n for n in set(M) & set(Sg) if M[n] != 'ERR' and Sg[n] != 'ERR']
    per_model[mdl] = {'n': len(us),
                      'single_pass': sum(Sg[n]=='P' for n in us),
                      'multi_pass': sum(M[n]=='P' for n in us),
                      'wins': sum(M[n]=='P' and Sg[n]=='F' for n in us),
                      'losses': sum(M[n]=='F' and Sg[n]=='P' for n in us)}
    for n in us:
        matrix.setdefault(n, {})[mdl] = {'single': Sg[n], 'multi': M[n]}

out = {'models': MODELS, 'per_model': per_model, 'matrix': matrix}
op = 'experiments/Neuro-Air/pv_matrix.json'
json.dump(out, open(op, 'w'), indent=1)
print("wrote", op)
for mdl in MODELS:
    pm = per_model.get(mdl);
    if pm: print(f"{mdl:18} n={pm['n']:3} single={pm['single_pass']:3} multi={pm['multi_pass']:3} W/L={pm['wins']}/{pm['losses']}")
tasks_full = [t for t,mm in matrix.items() if len(mm)==len(MODELS)]
print(f"tasks with all {len(MODELS)} backbones present: {len(tasks_full)} / {len(matrix)}")
