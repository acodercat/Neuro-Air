import json, glob, os, importlib.util, re
from math import comb

reg = json.load(open('benchmarks_neuroair_ablation.json'))
name2py = {nm: os.path.splitext(p)[0]+'.py' for dom,cats in reg.items() for cat,items in cats.items() for nm,p in items.items()}
raw = json.load(open('benchmarks_neuroair_ablation_tiers.json'))
tier = {nm: (v.get('tier') if isinstance(v, dict) else v) for nm, v in raw.items()}

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
    r = {}; gf = set()
    # newest file per benchmark (dedup safety)
    latest = {}
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
print(f'{"model":18} {"single":>8} {"multi":>8} {"d":>4} {"W/L":>6} {"McNemar p":>10}  tiers(s->m hard/med/simple)')
for mdl in MODELS:
    sb = f'experiments/Neuro-Air/{mdl}/single/run1'
    mb = f'experiments/Neuro-Air/{mdl}/multi/run1'
    if not (os.path.isdir(sb) and os.path.isdir(mb)): continue
    Sg, gfs = score(sb); M, gfm = score(mb)
    us = [n for n in set(M) & set(Sg) if M[n] != 'ERR' and Sg[n] != 'ERR']
    sp = sum(Sg[n] == 'P' for n in us); mp = sum(M[n] == 'P' for n in us)
    win = [n for n in us if M[n] == 'P' and Sg[n] == 'F']
    loss = [n for n in us if M[n] == 'F' and Sg[n] == 'P']
    b, c = len(loss), len(win); n = b + c
    p = min(1.0, 2*sum(comb(n, k) for k in range(0, min(b, c)+1))/2**n) if n else 1.0
    ts = []
    for tv in ['hard', 'medium', 'simple']:
        u = [x for x in us if tier.get(x) == tv]
        ts.append(f'{sum(Sg[x]=="P" for x in u)}->{sum(M[x]=="P" for x in u)}/{len(u)}')
    gtag = f' gfS={len(gfs)} gfM={len(gfm)}' if (gfs or gfm) else ''
    print(f'{mdl:18} {sp:>3}/{len(us):<4} {mp:>3}/{len(us):<4} {mp-sp:>+4} {c:>2}/{b:<3} {p:>10.4f}  {" ".join(ts)}{gtag}')
