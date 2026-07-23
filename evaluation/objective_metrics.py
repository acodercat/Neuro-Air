#!/usr/bin/env python3
"""Objective (LLM-free) metrics extracted from Neuro-Air benchmark run logs.

Motivation: reviewers asked for objective task-level metrics instead of
LLM-judge-only scoring. Every metric here is computed deterministically from
the raw execution logs under experiments/{exp}/{DOMAIN}/{Category}/*.log —
no LLM, no human, fully reproducible.

Metrics per group (model / paradigm / domain / category):

  Execution reliability (objective TIQ):
    - first_attempt_success : first code block (or tool call) executes without
      error. Reported with Wilson 95% CI.
    - exec_error_rate       : errors / (successes + errors), per execution.
    - runs_with_error       : share of runs with >=1 execution error.
    - recovery_rate         : among runs with >=1 error, share whose LAST
      execution succeeded (agent self-corrected and completed).

  Iteration behaviour:
    - steps per run         : mean / median / p90 / max executions.

  Sandbox safety + genuine failure rate (objective; for the safety/repro concern):
    - security_intervention : share of runs in which the runtime SecurityChecker
      blocked a call/import/attribute (the guardrail firing — NOT a code bug),
      plus the raw block count.
    - genuine_error_rate    : execution errors EXCLUDING security blocks /
      executions — the true code-failure rate once guardrail activations are
      separated out (a cleaner reliability figure than exec_error_rate).

  Data-handling behaviour (descriptive only):
    - empty_result_rate     : successful executions returning empty data
      (Empty DataFrame etc.), share of successes. Reported descriptively: an
      empty result is frequently the CORRECT answer to a yes/no query (no
      alert / no receptor / no exceedance), so it is NOT a fault signal and no
      "honesty/acknowledgement" rate is derived from it (that distinction
      requires query semantics, not available from logs).

  Wall-clock latency (objective, from filename timestamps):
    Log filenames are {qid}_{YYYYMMDD}_{HHMMSS}.log stamped at query START;
    queries in a batch ran sequentially, so the delta between consecutive
    start stamps ~= per-query duration. Deltas outside [5s, 30min] are
    treated as batch boundaries and dropped.
    - duration median / mean / p90, and share of queries under 10 minutes.

  Faithfulness proxy (objective FAI lower bound):
    - numeric grounding: every salient numeral in the Final Response
      (floats, or integers >= 10) must appear in the user query, generated
      code, or execution outputs (comma-normalised; rounding-tolerant:
      an output 54.63 grounds a reported 54.6). An ungrounded numeral is a
      number the model introduced at synthesis time — a strong, conservative
      hallucination signal. Reported as numeral-level grounding rate and
      share of runs fully grounded.

  Error taxonomy: SQL vs Python vs other error classes.

Caveats (stated in the paper text as well):
  - These are process/executability metrics; they do NOT measure scientific
    correctness of the answer (that requires ground-truth validation).
  - control_group_1 logs interleave multiple code blocks without per-block
    outputs; its execution-level metrics are not extractable and it is
    EXCLUDED from execution metrics (kept for volume/latency only).
  - kimi2 frequently emits consecutive code blocks where only the last gets
    an output marker; unmatched blocks are counted separately (n_none) and
    excluded from error-rate denominators.

Usage:
    python3 eval/objective_metrics.py                 # default paths
    python3 eval/objective_metrics.py --experiments experiments --out eval/eval_results/objective
"""

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------
# Log tokenisation
# --------------------------------------------------------------------------

MARKERS = [
    "# User query:", "## Thinking:", "## Execution Code:", "## Execution Result:",
    "## Execution Output:", "## Execution Output Exceeded:", "## Execution Error:",
    "## Security Error:", "## Max Steps Reached:", "## Final Response:",
    "## Tool Call:", "## Tool Result:", "## Tool Error:",
    "## COMPACTING:", "## COMPACTED:",
]
MARK_RE = re.compile("^(%s)" % "|".join(re.escape(m) for m in MARKERS))
SUCCESS_OUT = {"## Execution Result:", "## Execution Output:", "## Execution Output Exceeded:"}
MAIN_MODELS = ("claude4", "gpt5", "gemini", "deepseek", "qwen3", "kimi2")


def tokenize(text):
    """Split a log into (marker, content) events using logger markers only."""
    events, cur_m, buf = [], None, []
    for line in text.splitlines():
        m = MARK_RE.match(line)
        if m:
            if cur_m is not None:
                events.append((cur_m, "\n".join(buf)))
            cur_m, buf = m.group(1), [line[len(m.group(1)):]]
        elif cur_m is not None:
            buf.append(line)
    if cur_m is not None:
        events.append((cur_m, "\n".join(buf)))
    return events


# --------------------------------------------------------------------------
# Error taxonomy
# --------------------------------------------------------------------------

PY_EXC = re.compile(
    r"\b(KeyError|TypeError|ValueError|AttributeError|IndexError|NameError|"
    r"ZeroDivisionError|ModuleNotFoundError|ImportError|UnboundLocalError|"
    r"FileNotFoundError|RuntimeError|AssertionError|SyntaxError|IndentationError)\b")
SQL_PATTERNS = [
    ("SQL:UndefinedFunction", r"UndefinedFunction|function .{1,80} does not exist"),
    ("SQL:UndefinedColumn", r"UndefinedColumn|column .{1,80} does not exist"),
    ("SQL:UndefinedTable", r"UndefinedTable|relation .{1,80} does not exist"),
    ("SQL:GroupingError", r"GroupingError|must appear in the GROUP BY"),
    ("SQL:DatatypeMismatch", r"DatatypeMismatch|operator does not exist|cannot cast|invalid input syntax"),
    ("SQL:AmbiguousColumn", r"AmbiguousColumn|column reference .{1,80} is ambiguous"),
    ("SQL:DivisionByZero", r"division by zero"),
    ("SQL:SyntaxError", r"syntax error at or near"),
    # tool-boundary parameterisation failures (psycopg placeholder rejection)
    ("SQL:Parameterisation", r"allowed as placeholders"),
    # enum/value-domain violations surfaced by the database driver
    ("SQL:InvalidValue", r"InvalidTextRepresentation|invalid input value"),
]
SQL_RE = [(n, re.compile(p, re.I)) for n, p in SQL_PATTERNS]


def classify_error(text):
    for name, rx in SQL_RE:
        if rx.search(text):
            return name
    # runtime pre-execution checks (cave_agent checker formats, not Python tracebacks)
    if re.search(r"Syntax error:", text):
        return "CodeGen:SyntaxError"
    if re.search(r"Blocked (function call|import|attribute)", text):
        return "Security:Blocked"
    hits = PY_EXC.findall(text)
    if hits:
        return "PY:" + hits[-1]
    if "timeout" in text.lower() or "timed out" in text.lower():
        return "Timeout"
    if "OperationalError" in text or "connection" in text.lower():
        return "DBConnection"
    return "Other"


EMPTY_RE = re.compile(
    r"Empty DataFrame|\[0 rows x|Series\(\[\], |Columns: \[\]|returned no records|no rows", re.I)


# --------------------------------------------------------------------------
# Numeric grounding (objective faithfulness proxy)
# --------------------------------------------------------------------------

# lookbehind excludes word chars, '.', ',' (no mid-comma-group partial matches);
# a leading '-' is allowed so range dashes ("1,427-1,557") and signs don't split numbers.
NUM_RE = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?![\w%.])|"
                    r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?%")

# unit-conversion factors tolerated in the scale-aware grounding tier
# (m<->km, kg<->t, raw<->millions, ratios<->percent, ...)
SCALES = (1e3, 1e-3, 1e6, 1e-6, 100.0, 0.01, 10.0, 0.1)


def extract_numbers(text):
    """Return list of (raw_normalised, float_value, n_decimals)."""
    out = []
    for m in NUM_RE.finditer(text):
        intpart = m.group(1) or m.group(3)
        decpart = m.group(2) or m.group(4) or ""
        raw = (intpart or "").replace(",", "") + decpart
        if not raw:
            continue
        try:
            val = float(raw)
        except ValueError:
            continue
        out.append((raw, val, len(decpart) - 1 if decpart else 0))
    return out


def salient(numbers):
    """Keep numerals that constitute data claims: any float, or int >= 10."""
    return [(r, v, d) for r, v, d in numbers if d > 0 or v >= 10]


def _round_match(val, dec, candidates):
    """True if any candidate rounds to `val` at `dec` decimal places."""
    q = 10 ** (-dec) if dec else 1.0
    return any(abs(round(v / q) * q - val) < q * 0.51 and abs(v - val) < max(q, abs(val) * 0.005) + q
               for v in candidates)


def grounding(final_text, corpus_text):
    """Return (n_salient, n_strict, n_scaled) for numerals in the final response.

    strict : numeral appears verbatim (comma-normalised) or an evidence value
             rounds to it at its reported precision.
    scaled : additionally grounded after a plausible unit conversion (SCALES),
             e.g. output 317459 (m) grounds a reported 317 (km).
    Ungrounded = salient - scaled: values introduced by synthesis-time
    arithmetic (in-text differences/ratios) or without any evidential source.
    """
    finals = salient(extract_numbers(final_text))
    if not finals:
        return 0, 0, 0
    corpus_nums = extract_numbers(corpus_text)
    corpus_raw = {r for r, _, _ in corpus_nums}
    corpus_vals = [v for _, v, _ in corpus_nums]
    strict = scaled = 0
    for raw, val, dec in finals:
        if raw in corpus_raw or _round_match(val, dec, corpus_vals):
            strict += 1
            scaled += 1
            continue
        if any(_round_match(val, dec, (v * s for v in corpus_vals)) for s in SCALES):
            scaled += 1
    return len(finals), strict, scaled


# --------------------------------------------------------------------------
# Statistics helpers
# --------------------------------------------------------------------------

def wilson(k, n, z=1.96):
    """Wilson 95% CI for a proportion; returns (lo, hi) in percent."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (100 * (c - h), 100 * (c + h))


def pct(k, n):
    return 100 * k / n if n else float("nan")


def percentile(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, int(round(q / 100 * (len(xs) - 1)))))
    return xs[i]


# --------------------------------------------------------------------------
# Per-log parsing
# --------------------------------------------------------------------------

FNAME_RE = re.compile(r"^(?P<qid>.+)_(?P<d>\d{8})_(?P<t>\d{6})\.log$")


def parse_log(path: Path, exp: str, domain: str, category: str):
    text = path.read_text(encoding="utf-8", errors="ignore")
    ev = tokenize(text)
    marks = [m for m, _ in ev]

    n_tool, n_code = marks.count("## Tool Call:"), marks.count("## Execution Code:")
    paradigm = "func_call" if n_tool > n_code else "code_exec"
    call_m = "## Tool Call:" if paradigm == "func_call" else "## Execution Code:"
    ok_set = {"## Tool Result:"} if paradigm == "func_call" else SUCCESS_OUT
    err_m = "## Tool Error:" if paradigm == "func_call" else "## Execution Error:"

    execs, err_types, empties = [], [], []   # outcome list; taxonomy; per-exec empty flag
    for i, (m, _) in enumerate(ev):
        if m != call_m:
            continue
        nxt = ev[i + 1] if i + 1 < len(ev) else None
        if nxt and nxt[0] in ok_set:
            execs.append("ok")
            empties.append(bool(EMPTY_RE.search(nxt[1])))
        elif nxt and nxt[0] == err_m:
            execs.append("err")
            empties.append(False)
            err_types.append(classify_error(nxt[1]))
        else:
            execs.append("none")
            empties.append(False)

    query = next((c for m, c in ev if m == "# User query:"), "")
    final = next((c for m, c in ev if m == "## Final Response:"), "")
    code_all = "\n".join(c for m, c in ev if m in ("## Execution Code:", "## Tool Call:"))
    out_all = "\n".join(c for m, c in ev if m in SUCCESS_OUT | {"## Tool Result:", "## Execution Error:", "## Tool Error:"})

    n_sal, n_strict, n_scaled = grounding(final, query + "\n" + code_all + "\n" + out_all)

    matched = [e for e in execs if e in ("ok", "err")]
    # empty-result rate: successful executions returning empty data. NOTE this
    # is a loose signature: an empty result is often the CORRECT answer to a
    # yes/no query (no alert / no receptor / no exceedance), so it is reported
    # descriptively only and is NOT treated as a fault.
    empty_seen = sum(1 for e, emp in zip(execs, empties) if e == "ok" and emp)
    # sandbox guardrail activations (blocked calls/imports) — NOT code bugs.
    n_sec = sum(1 for t in err_types if t == "Security:Blocked")

    m = FNAME_RE.match(path.name)
    start = datetime.strptime(m.group("d") + m.group("t"), "%Y%m%d%H%M%S") if m else None

    return dict(
        exp=exp, domain=domain, category=category, paradigm=paradigm, path=str(path),
        n_exec=len(execs), n_ok=matched.count("ok"), n_err=matched.count("err"),
        n_none=execs.count("none"),
        first=(matched[0] if matched else None),
        last_ok=(matched[-1] == "ok") if matched else None,
        err_types=err_types, n_sec=n_sec,
        n_empty=empty_seen,
        final_len=len(final.strip()), code_chars=len(code_all), out_chars=len(out_all),
        n_sal=n_sal, n_strict=n_strict, n_scaled=n_scaled,
        start=start.isoformat() if start else None,
    )


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

def aggregate(rows):
    n = len(rows)
    if n == 0:
        return None
    fa = [r for r in rows if r["first"] in ("ok", "err")]
    fa_ok = sum(1 for r in fa if r["first"] == "ok")
    ok = sum(r["n_ok"] for r in rows)
    err = sum(r["n_err"] for r in rows)
    err_runs = [r for r in rows if r["n_err"] > 0]
    recovered = sum(1 for r in err_runs if r["last_ok"])
    steps = [r["n_exec"] for r in rows]
    empty = sum(r["n_empty"] for r in rows)
    # sandbox safety + genuine (non-guardrail) failure rate
    n_sec = sum(r["n_sec"] for r in rows)
    runs_sec = sum(1 for r in rows if r["n_sec"] > 0)
    genuine_err = err - n_sec
    runs_genuine_err = sum(1 for r in rows if (r["n_err"] - r["n_sec"]) > 0)
    sal = sum(r["n_sal"] for r in rows)
    strict = sum(r["n_strict"] for r in rows)
    scaled = sum(r["n_scaled"] for r in rows)
    fully = sum(1 for r in rows if r["n_sal"] > 0 and r["n_scaled"] == r["n_sal"])
    with_nums = sum(1 for r in rows if r["n_sal"] > 0)
    tax = Counter()
    for r in rows:
        tax.update(r["err_types"])
    n_none = sum(r["n_none"] for r in rows)
    n_exec_total = sum(r["n_exec"] for r in rows)
    return dict(
        runs=n,
        unmatched_pct=pct(n_none, n_exec_total),  # code blocks with no logged outcome
        first_ok_pct=pct(fa_ok, len(fa)), first_ok_ci=wilson(fa_ok, len(fa)),
        exec_err_pct=pct(err, ok + err), exec_err_ci=wilson(err, ok + err),
        runs_err_pct=pct(len(err_runs), n), runs_err_ci=wilson(len(err_runs), n),
        recovery_pct=pct(recovered, len(err_runs)) if err_runs else float("nan"),
        n_err_runs=len(err_runs),
        steps_mean=sum(steps) / n, steps_med=percentile(steps, 50),
        steps_p90=percentile(steps, 90), steps_max=max(steps),
        empty_pct=pct(empty, ok), n_empty=empty,
        genuine_exec_err_pct=pct(genuine_err, ok + err), genuine_exec_err_ci=wilson(genuine_err, ok + err),
        runs_genuine_err_pct=pct(runs_genuine_err, n),
        n_security_blocks=n_sec, runs_with_security_pct=pct(runs_sec, n),
        ground_strict_pct=pct(strict, sal), ground_strict_ci=wilson(strict, sal),
        ground_scaled_pct=pct(scaled, sal), ground_scaled_ci=wilson(scaled, sal),
        fully_grounded_pct=pct(fully, with_nums), n_numerals=sal,
        taxonomy=dict(tax.most_common()),
    )


def durations(rows):
    """Per-query wall-clock estimates from consecutive start stamps."""
    per_group = defaultdict(list)
    for r in rows:
        if r["start"]:
            per_group[(r["exp"], r["domain"])].append(r["start"])
    deltas = []
    for stamps in per_group.values():
        ts = sorted(datetime.fromisoformat(s) for s in stamps)
        for a, b in zip(ts, ts[1:]):
            d = (b - a).total_seconds()
            if 5 <= d <= 1800:          # drop batch boundaries / restarts
                deltas.append(d)
    if not deltas:
        return None
    return dict(
        n=len(deltas),
        med_s=percentile(deltas, 50), mean_s=sum(deltas) / len(deltas),
        p90_s=percentile(deltas, 90),
        under_10min_pct=pct(sum(1 for d in deltas if d < 600), len(deltas)),
    )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def fmt_ci(ci):
    lo, hi = ci
    return f"[{lo:.1f},{hi:.1f}]" if lo == lo else "—"


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--experiments", type=Path, default=here.parent / "experiments")
    ap.add_argument("--out", type=Path, default=here / "eval_results" / "objective")
    args = ap.parse_args()

    rows = []
    for log in sorted(args.experiments.glob("*/*/*/*.log")):
        exp, domain, category = log.parts[-4], log.parts[-3], log.parts[-2]
        rows.append(parse_log(log, exp, domain, category))
    print(f"parsed {len(rows)} logs from {args.experiments}")

    exec_rows = [r for r in rows if r["exp"] != "control_group_1"]  # see module docstring

    groups = {}
    for m in MAIN_MODELS:
        groups[("model", m)] = [r for r in exec_rows if r["exp"] == m]
    groups[("paradigm", "native_python")] = [r for r in exec_rows if r["exp"] in MAIN_MODELS]
    groups[("paradigm", "function_calling")] = [r for r in exec_rows if r["exp"] == "control_group_2"]
    # paradigm comparison restricted to HK (CG2 is HK-only) for a matched view
    groups[("paradigm_hk", "native_python_HK")] = [r for r in exec_rows if r["exp"] in MAIN_MODELS and r["domain"] == "HK"]
    groups[("paradigm_hk", "function_calling_HK")] = [r for r in exec_rows if r["exp"] == "control_group_2"]
    for d in ("HB", "HK"):
        groups[("domain", d)] = [r for r in exec_rows if r["exp"] in MAIN_MODELS and r["domain"] == d]
    # per-model breakdown restricted to HK (for the HK-only deployment paper)
    for m in MAIN_MODELS:
        groups[("model_hk", f"{m}_HK")] = [r for r in exec_rows if r["exp"] == m and r["domain"] == "HK"]
    # per-category breakdown restricted to HK (matched to the HK query taxonomy)
    for c in sorted({r["category"] for r in exec_rows if r["exp"] in MAIN_MODELS and r["domain"] == "HK"}):
        groups[("category_hk", c)] = [r for r in exec_rows if r["exp"] in MAIN_MODELS and r["domain"] == "HK" and r["category"] == c]
    for c in sorted({r["category"] for r in exec_rows if r["exp"] in MAIN_MODELS}):
        groups[("category", c)] = [r for r in exec_rows if r["exp"] in MAIN_MODELS and r["category"] == c]

    results = {}
    for key, rs in groups.items():
        agg = aggregate(rs)
        if agg:
            agg["duration"] = durations(rs)
            results["/".join(key)] = agg

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "objective_metrics.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))

    # CSV (one row per group)
    cols = ["group", "runs", "first_ok_pct", "first_ok_ci", "exec_err_pct", "runs_err_pct",
            "recovery_pct", "steps_mean", "steps_med", "steps_p90",
            "genuine_exec_err_pct", "runs_genuine_err_pct", "runs_with_security_pct",
            "n_security_blocks", "empty_pct",
            "ground_strict_pct", "ground_scaled_pct", "ground_scaled_ci", "fully_grounded_pct",
            "dur_med_s", "dur_p90_s", "under_10min_pct"]
    with open(args.out / "objective_metrics.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for k, a in results.items():
            d = a["duration"] or {}
            w.writerow([k, a["runs"], f"{a['first_ok_pct']:.1f}", fmt_ci(a["first_ok_ci"]),
                        f"{a['exec_err_pct']:.1f}", f"{a['runs_err_pct']:.1f}",
                        f"{a['recovery_pct']:.1f}", f"{a['steps_mean']:.1f}", a["steps_med"],
                        a["steps_p90"], f"{a['genuine_exec_err_pct']:.1f}",
                        f"{a['runs_genuine_err_pct']:.1f}", f"{a['runs_with_security_pct']:.1f}",
                        a["n_security_blocks"], f"{a['empty_pct']:.1f}",
                        f"{a['ground_strict_pct']:.1f}", f"{a['ground_scaled_pct']:.1f}",
                        fmt_ci(a["ground_scaled_ci"]), f"{a['fully_grounded_pct']:.1f}",
                        f"{d.get('med_s', float('nan')):.0f}", f"{d.get('p90_s', float('nan')):.0f}",
                        f"{d.get('under_10min_pct', float('nan')):.1f}"])

    # console summary
    def line(k):
        a = results.get(k)
        if not a:
            return
        d = a["duration"] or {}
        print(f"  {k:38s} n={a['runs']:4d}  first_ok={a['first_ok_pct']:5.1f}% {fmt_ci(a['first_ok_ci'])}"
              f"  errRuns={a['runs_err_pct']:4.1f}%  genErrRuns={a['runs_genuine_err_pct']:4.1f}%"
              f"  secBlk={a['n_security_blocks']:2d}({a['runs_with_security_pct']:4.1f}%)  recover={a['recovery_pct']:5.1f}%"
              f"  steps~{a['steps_med']:.0f}  ground={a['ground_strict_pct']:4.1f}/{a['ground_scaled_pct']:4.1f}%"
              f"  dur_med={d.get('med_s', float('nan')):5.0f}s  <10min={d.get('under_10min_pct', float('nan')):5.1f}%")

    print("\n== per model ==")
    for m in MAIN_MODELS:
        line(f"model/{m}")
    print("== paradigm (all) ==")
    line("paradigm/native_python"); line("paradigm/function_calling")
    print("== paradigm (HK-matched) ==")
    line("paradigm_hk/native_python_HK"); line("paradigm_hk/function_calling_HK")
    print("== domain ==")
    line("domain/HB"); line("domain/HK")
    print(f"\nwritten: {args.out}/objective_metrics.json / .csv")


if __name__ == "__main__":
    main()
