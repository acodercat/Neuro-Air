"""Does the stored turn['success'] equal the frozen PV validator verdict?

If yes, the per-task pass/fail matrix can be read straight from the run JSONs
with zero DB access. Tests a spread including known-FAIL cases.
"""
import json, glob, os, importlib.util, re
reg = json.load(open('benchmarks_neuroair_ablation.json'))
n2p = {nm: os.path.splitext(p)[0]+'.py' for dom,cats in reg.items() for cat,items in cats.items() for nm,p in items.items()}

def co(v):
    m = re.match(r'^np\.\w+\((.+)\)$', v.strip()) if isinstance(v, str) else None
    return float(m.group(1)) if m else v
class S:
    def __init__(s, d): s.d = {k: co(x) for k, x in d.items()}
    def retrieve(s, k): return s.d.get(k)
def liveval(nm, rv):
    sp = importlib.util.spec_from_file_location('v_'+nm, n2p[nm]); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return list(m.validators.values())[0]('', S(rv), None).success

probe = [('qwen3.5-397b','multi','hb_6_16'), ('qwen-2.5-72b','multi','hb_6_16'),
         ('qwen-2.5-72b','single','hb_6_16'), ('deepseek-v4-flash','single','hb_6_16'),
         ('gpt55','multi','hk_1_2'), ('qwen3.6-35b','single','hk_1_2')]
mism = 0
for mdl, arm, nm in probe:
    fs = glob.glob(f'experiments/Neuro-Air/{mdl}/{arm}/run1/**/{nm}/*.json', recursive=True)
    if not fs:
        print(mdl, arm, nm, 'NO FILE'); continue
    t = json.load(open(fs[0]))[nm]['conversations'][0]['turns'][0]
    rv = t.get('runtime_variables') or {}
    live = liveval(nm, rv); ss = t.get('success')
    tag = '<== MISMATCH' if bool(ss) != bool(live) else 'ok'
    if bool(ss) != bool(live): mism += 1
    print(f"{mdl:18} {arm:6} {nm:8} stored.success={str(ss):5} LIVE_validator={str(live):5}  {tag}")
print(f"\nmismatches: {mism}/{len(probe)}  ->  {'stored.success is NOT the PV verdict; must re-score' if mism else 'stored.success MATCHES PV verdict on this probe'}")
