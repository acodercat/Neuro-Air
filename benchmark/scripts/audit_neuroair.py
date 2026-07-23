"""Audit the Neuro-Air PV benchmark (benchmarks_neuroair.json) with gpt55.

Thin wrapper over scripts.audit_benchmarks.audit_benchmark that points at our own
registry instead of the hardcoded benchmarks.json. Usage:
    uv run python -m scripts.audit_neuroair --model gpt55
"""
import argparse, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from core.llm import LLMClient, ModelRegistry
from scripts.audit_benchmarks import _load_schema
import json as _json

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "benchmarks_neuroair.json"
OUT = ROOT / "audit_results"


# ---------------------------------------------------------------------------
# Ground-truth quality audit prompt (focused on whether the VALIDATOR is an
# objective, correct, fair arbiter — not the general leakage/rigor audit).
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert air-quality benchmark auditor focused on GROUND-TRUTH QUALITY. Each benchmark gives an agent a task; a Python validator recomputes the ground truth from the database and checks the agent's numeric outputs within an absolute tolerance. Your job: judge whether the validator is an OBJECTIVE, CORRECT, and FAIR arbiter of the task.

Be rigorous but pragmatic: flag an issue only if it would make a CORRECT agent fail, a WRONG agent pass, or make the "right answer" depend on a convention the task never states. Do not flag style, theoretical risks, or unlikely edge cases.

Respond with a single JSON object. No markdown, no prose outside the JSON."""

AUDIT_PROMPT_TEMPLATE = """## Benchmark: {benchmark_name}
Domain: {domain} | Category: {category}

### Database Schema
{schema}

### Task the agent is given
{queries}

### Validator (recomputes ground truth from the DB, then checks the agent's variables)
```python
{validator_code}
```

---
## Audit dimensions — focus on GROUND-TRUTH QUALITY. For EACH required output variable:

### 1. GT computation correctness
Is the validator's SQL/logic a CORRECT way to produce what the task asks? CRITICAL if it uses the wrong table/join/filter/time-window/aggregation/column/unit, so the ground truth itself is wrong.

### 2. Query<->validator consistency
Does the validator check EXACTLY what the task asks (same entity, period, metric, filter)? Flag if it checks something materially different so a correct agent fails.

### 3. Tolerance appropriateness  <-- pay special attention
Each numeric var is checked within an ABSOLUTE tolerance. Estimate the variable's typical magnitude (from the metric + schema), then judge the tolerance:
- TOO TIGHT (critical): the tolerance is a very small fraction of the magnitude (roughly < 0.3%), so it would REJECT a legitimate alternative-but-valid computation — e.g. great-circle (Haversine sphere) distance vs PostGIS geography ellipsoid differ ~0.2-0.5%; a large sum differing by rounding; correlation pinned to 2 decimals. State the variable, its approx magnitude, the tol, and the implied fraction.
- TOO LOOSE (warning): large enough to accept a clearly-wrong answer.
Counts, IDs, hour-of-day, and offset-in-whole-hours are exact by nature — tol=0 is CORRECT for them; do NOT flag those as too tight.

### 4. Task determinism / unstated convention  <-- pay special attention
Is there a UNIQUE defensible answer, or does the checked value depend on a convention the task does NOT state, so two reasonable analysts get DIFFERENT values beyond tolerance? Flag (critical if it changes the checked value):
- time-window boundary: is "A to B" inclusive or exclusive of the end hour? (matters for counts/sums/means)
- argmax/peak/"most X" tie-breaking; which hour is "the peak" on a plateau
- offset/lag anchor: from which exact datetime an offset is measured
- rounding / ddof / percentile method when the tolerance is tight enough to distinguish them
If the `requirements` already pin the convention, it is NOT ambiguous.

### 5. Unit / sign correctness
Units consistent across task, variable description, and validator (kg vs tonnes, m vs km, ug/m3); signed quantities compared signed.

### 6. Knowledge leakage (brief)
Flag only if the QUERY text leaks exact underscore table/column names or ALL_CAPS enum values. (Requirements naming the output variables is intended, not leakage.)

## Output Format
```json
{{
    "benchmark": "{benchmark_name}",
    "overall": "PASS" or "FAIL",
    "issues": [
        {{
            "category": "gt_correctness|query_validator_consistency|tolerance|task_ambiguity|unit_sign|knowledge_leakage",
            "severity": "critical|warning",
            "variable": "output variable involved, or null",
            "description": "what is wrong and why it changes the pass/fail verdict",
            "suggestion": "concrete fix, e.g. 'loosen tol 0.2->~1.2km (0.5%)' or 'state window is end-exclusive'"
        }}
    ]
}}
```
PASS with empty issues if the validator is an objective, correct, unambiguous arbiter."""


def audit_benchmark(client, domain, category, name, path):
    """Audit one benchmark, INCLUDING the `requirements` the agent is given.

    The upstream auditor only shows the auditor the `query`. Our benchmarks
    deliberately keep the Neuro-Air query verbatim and pin the deterministic
    sub-task in a separate `requirements` field — which the agent DOES see. We
    include it here so the query-validator-consistency judgement is fair.
    """
    data = _json.load(open(path))[0]
    turns = data["conversations"][0]["turns"]
    req = data.get("requirements", "")
    agent_sees = "\n".join(f"Turn {i}: {t['query']}" for i, t in enumerate(turns, 1))
    agent_sees += (
        "\n\n[Requirements the agent is ALSO given — these tell the agent exactly which "
        f"deterministic variables to compute and store, which the validator then checks]:\n{req}"
    )
    prompt = AUDIT_PROMPT_TEMPLATE.format(
        benchmark_name=name, domain=domain, category=category,
        schema=_load_schema(domain), queries=agent_sees,
        validator_code=Path(path).with_suffix(".py").read_text(),
    )
    result = client.complete(prompt, json_mode=True, system=SYSTEM_PROMPT, max_tokens=8192)
    if result is None:
        return {"benchmark": name, "overall": "ERROR", "issues": [], "error": "LLM call failed"}
    try:
        return _json.loads(result.text)
    except _json.JSONDecodeError:
        return {"benchmark": name, "overall": "ERROR", "issues": [], "raw": result.text[:500]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", "-m", default="gpt55")
    ap.add_argument("--concurrency", "-c", type=int, default=5)
    args = ap.parse_args()

    client = LLMClient(ModelRegistry.load(ROOT / "models.toml").get(args.model))
    registry = json.load(open(REG))
    tasks = [(dom, cat, name, path) for dom, cats in registry.items()
             for cat, items in cats.items() for name, path in items.items()]
    OUT.mkdir(exist_ok=True)
    out_file = OUT / f"audit_neuroair_{args.model}.json"

    results = []
    lock = threading.Lock()
    total = len(tasks)
    print(f"Auditing {total} Neuro-Air benchmarks with {args.model} (concurrency={args.concurrency})...\n")

    def one(dom, cat, name, path):
        r = audit_benchmark(client, dom, cat, name, path)
        with lock:
            results.append({"domain": dom, "category": cat, **r})
            ov = r.get("overall", "ERROR")
            iss = r.get("issues", [])
            crit = sum(1 for i in iss if i.get("severity") == "critical")
            tag = {"PASS": "PASS", "FAIL": f"FAIL ({len(iss)} issues, {crit} critical)"}.get(ov, ov)
            print(f"[{len(results)}/{total}] {dom}/{cat}/{name} ... {tag}")
            for i in iss:
                sev = "CRIT" if i.get("severity") == "critical" else "warn"
                print(f"      {sev} [{i.get('category')}] {i.get('description')}")
            json.dump(results, open(out_file, "w"), indent=2, ensure_ascii=False)

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(one, *t): t for t in tasks}
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:
                print(f"  thread error {futs[f][2]}: {e}")

    p = sum(1 for r in results if r.get("overall") == "PASS")
    fa = sum(1 for r in results if r.get("overall") == "FAIL")
    er = sum(1 for r in results if r.get("overall") == "ERROR")
    print("\n" + "=" * 60)
    print(f"AUDIT COMPLETE ({args.model}): total={len(results)} PASS={p} FAIL={fa} ERROR={er}")
    print(f"Saved: {out_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
