"""Find GT-audit tasks where stored.success != frozen validator verdict.

stored.success is the un-audited verdict; the frozen validator (post GT-audit,
strictly-relaxing) is authoritative and differs only on the audited tasks.
We live-validate ONLY the stored-Fail tasks (a relaxing fix can only flip F->P),
with a per-task timeout so no slow spatial query can hang the run.

Patches experiments/Neuro-Air/pv_matrix.json in place and re-checks vs Table 2.
"""
import json, glob, os, importlib.util, re, signal

reg = json.load(open('benchmarks_neuroair_ablation.json'))
n2p = {nm: os.path.splitext(p)[0]+'.py' for dom,cats in reg.items() for cat,items in cats.items() for nm,p in items.items()}
TASKS = set(n2p)
MODELS = ['deepseek-v4-flash', 'gpt55', 'qwen3.6-35b', 'qwen-2.5-72b', 'qwen3.5-397b']
TABLE2 = {'deepseek-v4-flash': (78,84,6,0), 'gpt55': (83,88,6,1), 'qwen3.6-35b': (80,86,6,0),
          'qwen-2.5-72b': (46,55,15,6), 'qwen3.5-397b': (82,85,5,2)}

def co(v):
    m = re.match(r'^np\.\w+\((.+)\)$', v.strip()) if isinstance(v, str) else None
    return float(m.group(1)) if m else v
class S:
    def __init__(s, d): s.d = {k: co(x) for k, x in d.items()}
    def retrieve(s, k): return s.d.get(k)
_vc = {}
def vf(nm):
    if nm not in _vc:
        sp = importlib.util.spec_from_file_location('v_'+nm, n2p[nm]); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
        _vc[nm] = list(m.validators.values())[0]
    return _vc[nm]

class TO(Exception): pass
def _alarm(*a): raise TO()
signal.signal(signal.SIGALRM, _alarm)
def live(nm, rv, secs=25):
    signal.alarm(secs)
    try: return vf(nm)('', S(rv), None).success
    except TO: return None            # slow query -> undecided
    finally: signal.alarm(0)

def turnfile(mdl, arm, nm):
    fs = glob.glob(f'experiments/Neuro-Air/{mdl}/{arm}/run1/**/{nm}/*.json', recursive=True)
    if not fs: return None
    fs.sort()
    return json.load(open(fs[-1]))[nm]['conversations'][0]['turns'][0]

d = json.load(open('experiments/Neuro-Air/pv_matrix.json'))
matrix = d['matrix']
flips = []
for mdl in MODELS:
    for arm in ('single', 'multi'):
        for nm, cell in list(matrix.items()):
            if mdl not in cell or cell[mdl][arm] != 'F':
                continue                      # relaxing fix can only flip F->P
            t = turnfile(mdl, arm, nm)
            if t is None: continue
            rv = t.get('runtime_variables') or {}
            lv = live(nm, rv)
            if lv is True:                    # audit-relaxed: stored F -> frozen P
                cell[mdl][arm] = 'P'; flips.append((mdl, arm, nm))
            elif lv is None:
                print(f"  [timeout] {mdl} {arm} {nm} — left as stored 'F'")
print(f"audit flips F->P: {len(flips)}")
for f in flips: print("   ", f)

# re-derive counts and assert Table 2
per_model = {}; ok = True
for mdl in MODELS:
    us = [n for n,c in matrix.items() if mdl in c]
    sp = sum(matrix[n][mdl]['single']=='P' for n in us); mp = sum(matrix[n][mdl]['multi']=='P' for n in us)
    wins = sum(matrix[n][mdl]['multi']=='P' and matrix[n][mdl]['single']=='F' for n in us)
    losses = sum(matrix[n][mdl]['multi']=='F' and matrix[n][mdl]['single']=='P' for n in us)
    per_model[mdl] = {'n': len(us), 'single_pass': sp, 'multi_pass': mp, 'wins': wins, 'losses': losses}
    got = (sp, mp, wins, losses); exp = TABLE2[mdl]
    print(f"{mdl:18} {got}  Table2={exp}  {'OK' if got==exp else '<== MISMATCH'}"); ok = ok and got==exp
tot = {k: sum(per_model[m][k] for m in MODELS) for k in ('single_pass','multi_pass','wins','losses')}
print(f"POOLED single={tot['single_pass']}/450 multi={tot['multi_pass']}/450 W/L={tot['wins']}/{tot['losses']}  (369/398, 38/9)")
assert ok and (tot['single_pass'],tot['multi_pass'],tot['wins'],tot['losses'])==(369,398,38,9), "still mismatched"
d['per_model'] = per_model
d['source'] = 'stored turn.success, reconciled to frozen PV validator on GT-audit tasks; counts == Table 2'
json.dump(d, open('experiments/Neuro-Air/pv_matrix.json','w'), indent=1)
print("\nReconciled. All counts == Table 2. Wrote pv_matrix.json.")
