"""Multi-agent adapter for air-bench (R1-4 matched ablation).

Implements the paper's hierarchical topology — one central Coordinator plus five
domain-specialised worker agents sharing ONE ``IPythonRuntime`` — on top of
cave_agent, conforming to the same ``Agent`` / ``AgentFactory`` interface as the
single-agent ``CaveAgentFactory`` so the identical PV pipeline scores it.

All workers share one runtime (the paper's dual-stream "runtime is the state"):
a worker's executed code persists in the namespace, and each worker is shown a
manifest of the variables already staged so it reuses them instead of
re-querying. The only difference vs the single agent is the topology.
"""

from __future__ import annotations

import json
import re
from typing import Callable, List, Optional, Tuple

from core.agent import Agent, AgentFactory, AgentResponse, TokenUsage
from core.tracker import FunctionCallTracker
from cave_agent import CaveAgent, Model
from cave_agent.runtime import IPythonRuntime, Function, Variable, Type


# Coordinator + 5 workers, faithful to the manuscript Fig. 1.
WORKER_ROLES: dict[str, str] = {
    "data_acquisition": (
        "You are the DATA ACQUISITION agent, and you OWN entity resolution for the whole team. "
        "FIRST resolve EVERY named entity the task mentions (companies, districts, stations, "
        "cities) to its exact database id, and stage each id in a clearly named variable "
        "(e.g. company_id, district_id_jingxiu). When the task already gives an id, use it as-is. "
        "When it gives only a name: try exact-name equality first; if that returns nothing, try ONE "
        "fuzzy fallback; if still nothing, stage the id as None and print 'UNRESOLVED: <name>' — do "
        "NOT keep looping on resolution (never spend more than a couple of queries per entity). "
        "Print a 'RESOLVED: <name> = <id>' line for each. Then fetch the raw records those ids need "
        "(pollutant readings, emissions, geometry, weather) into clearly named DataFrames, and for "
        "each, print its row count; if a fetch is EMPTY for an id you expected data for, re-check the "
        "id rather than passing an empty/zero downstream. Do not perform the final analysis; just "
        "resolve, fetch, and stage."
    ),
    "knowledge_retrieval": (
        "You are the KNOWLEDGE RETRIEVAL agent. Identify the domain knowledge needed "
        "to interpret the task (regulatory standards, AQI/AQHI breakpoints, WHO/national "
        "limits, units) and stage it as clearly named variables or short notes. Use only "
        "the provided schema/knowledge and reliable domain facts; do not fabricate values."
    ),
    "pollution_analysis": (
        "You are the AIR POLLUTION ANALYSIS agent — the team's STATISTICS specialist. Using the "
        "variables already staged in the shared runtime, compute the core quantities the task asks "
        "for, applying the standard definitions: a 'total' is a SUM, a 'peak' is the MAX, a 'mean' is "
        "the arithmetic average of the hourly readings, 'exceedance hours' is the COUNT of hours whose "
        "value exceeds the stated threshold, and a correlation is Pearson's r on the paired series. "
        "Reuse existing variables instead of re-querying; store intermediate results as named "
        "variables. (Leave distance / bearing / 'within X km' geospatial computations to the "
        "geospatial specialist.)"
    ),
    "multivariate_meteo": (
        "You are the MULTIVARIATE, METEOROLOGICAL & GEOSPATIAL ANALYSIS agent — the team's SPATIAL "
        "SPECIALIST. When the task requires it, integrate meteorology / traffic / geospatial factors "
        "with the pollution data already staged (correlations, wind-direction checks, source-receptor "
        "associations, spatial joins). You OWN all spatial/geometry computation and know the correct "
        "PostGIS usage: the location columns are a geography type, so distances come out in METRES. "
        "Compute a distance in km as ST_Distance(a.location, b.location)/1000.0; 'within X km' as "
        "ST_DWithin(a.location, b.location, X*1000); a bearing as degrees(ST_Azimuth(from.location, "
        "to.location)) keeping the FROM->TO order the task states (a result ~180 deg off means the "
        "order is reversed). NEVER cast the geography location to ::geometry or rebuild points with "
        "ST_MakePoint/ST_SetSRID — that switches the unit to DEGREES and silently corrupts distances, "
        "'within' counts, and bearings. If a needed factor is missing or empty, say so explicitly "
        "rather than assuming it. Store results as named variables."
    ),
    "synthesis_report": (
        "You are the SYNTHESIS & REPORTING agent. Ensure EVERY required output variable listed "
        "in the task requirements is assigned in the runtime with the correct value and type, "
        "reusing the intermediate variables upstream agents staged. End by print()-ing each "
        "required output. (A verification agent will independently double-check your values after "
        "you, so assign your best current values.)"
    ),
    "verification": (
        "You are the VERIFICATION & CORRECTION agent — the FINAL, decisive step, an INDEPENDENT "
        "auditor of the team's answers. The required output variables are already assigned but may "
        "be wrong. For EACH required output, recompute it YOURSELF from the raw database with a "
        "FRESH query — do NOT trust or reuse the stored value, the staged intermediate variables, "
        "or the earlier agents' method; derive it independently. Then compare your result to the "
        "stored value: if they differ by more than rounding, the stored value is WRONG, so REASSIGN "
        "the variable to your independently-verified value. For each, print "
        "'VERIFY <var>: stored=<old> | independent=<new> | final=<kept>'. Re-derive from scratch and "
        "scrutinise these common error sources:\n"
        "  • ENTITY ID: resolve the named entity yourself and confirm it is the right record.\n"
        "  • TIME WINDOW: apply the stated window conventions exactly.\n"
        "  • UNITS & SCALE: confirm each value's units and scale match what the task asks (kilometres vs "
        "metres, a ratio vs a percentage, a per-hour rate vs a whole-period total). A value off by a clean "
        "factor (x100, x1000, /24) is almost always a unit/scale slip.\n"
        "  • SUM vs PEAK vs MEAN: confirm a 'total' is a SUM (not the peak/max), a 'peak' is the MAX, etc.\n"
        "  • PLAUSIBILITY: sanity-check each value's magnitude against what it measures — a 'within a small "
        "radius' count that returns almost every candidate, a sum orders of magnitude off, or a share "
        "outside 0-100% all signal a wrong filter / join / window; recompute it rather than trust it.\n"
        "  • EMPTY/ZERO: if a query returns empty/zero for an entity that should have data, the id or "
        "filter is wrong — fix it, never keep the zero.\n"
        "Finish by print()-ing every final required output."
    ),
}

_SYNTH_ROLE = "synthesis_report"
_VERIFY_ROLE = "verification"
DEFAULT_PIPELINE = ["data_acquisition", "pollution_analysis", "multivariate_meteo", _SYNTH_ROLE]
_MAX_PLAN_STEPS = 6

# Applied to EVERY worker. The failure modes a shared-runtime team must avoid are
# (1) re-resolving an entity by name when the task already gives its ID (wrong entity),
# and (2) recomputing — and thereby CLOBBERING — an intermediate another worker already
# staged correctly (last-write-wins on a wrong recompute). Both are hard rules here.
_SHARED_DISCIPLINE = (
    "SHARED-RUNTIME DISCIPLINE (mandatory for every agent):\n"
    "- ENTITY RESOLUTION is owned by the data_acquisition agent. Use the ids it already resolved "
    "and staged (shown in the manifest, e.g. company_id, district_id_*). If the task gives an "
    "explicit id, use that exact id. Do NOT resolve or re-resolve any entity by name yourself, and "
    "never loop over name variants — if a needed id is missing or was staged as None, flag it in "
    "text rather than guessing.\n"
    "- NEVER CLOBBER: variables already staged in the shared runtime are authoritative. Reuse them "
    "by name. Do NOT reassign, overwrite, or recompute a variable — or a quantity another agent "
    "already computed — even if you would derive it differently. Add ONLY what your own subtask "
    "contributes, in NEW descriptively-named variables. If an existing value looks wrong, note it "
    "in text for the synthesis agent; do not silently overwrite it.\n"
    "- NEVER STORE A SILENT ZERO/EMPTY: if a query returns no rows (sum/count = 0 or empty) for an "
    "entity the task expects to have data, do NOT store that 0 as the answer — it almost always "
    "means the id/filter/time-window is wrong. Re-check the resolved id and the filter first, and "
    "if it is genuinely empty, say so explicitly."
)

_COORDINATOR_SYS = (
    "You are the CENTRAL COORDINATOR of a hierarchical multi-agent air-quality "
    "analysis system. Decompose the user's task into an ordered plan over these "
    "specialised worker agents:\n"
    "  - data_acquisition: fetch raw data from the database\n"
    "  - knowledge_retrieval: gather standards/thresholds/domain facts\n"
    "  - pollution_analysis: compute the core statistics/metrics\n"
    "  - multivariate_meteo: integrate meteorology/traffic/geospatial factors\n"
    "  - synthesis_report: assemble the final answer and set the required output variables\n\n"
    "Return ONLY a JSON array of steps, each {\"role\": <one of the roles>, "
    "\"task\": <concise instruction for that worker>}. Use the MINIMAL set of workers the "
    "task truly needs, in execution order, always ending with synthesis_report. Fewer workers "
    "is better: every extra worker re-touches the shared runtime and risks recomputing (and "
    "corrupting) data an earlier worker already staged correctly. Guidance:\n"
    "  - a retrieval or single-source statistics task needs only [data_acquisition, synthesis_report];\n"
    "  - add pollution_analysis only for non-trivial multi-step computation;\n"
    "  - add multivariate_meteo ONLY if the task genuinely needs meteorology/traffic/geospatial "
    "integration; add knowledge_retrieval ONLY if it needs external standards/thresholds.\n"
    "Do NOT include a worker just because it exists. Ensure some worker computes each required "
    f"output variable. Maximum {_MAX_PLAN_STEPS} steps."
)

# Read-only probe: prints a {name: type} map of the live user namespace (excluding
# modules, callables, and IPython bookkeeping) so the next worker knows what to reuse.
_MANIFEST_SNIPPET = (
    "print('VARS::', {n: type(v).__name__ for n, v in list(locals().items()) "
    "if not n.startswith('_') and n not in ('In', 'Out', 'exit', 'quit', 'get_ipython') "
    "and v is not None and not callable(v) and type(v).__name__ != 'module'})"
)


def _required_outputs(requirements: Optional[str]) -> str:
    """The 'store the results in: ...' clause, for prompt display."""
    if not requirements:
        return ""
    m = re.search(r"store[^:]*:(.*)", requirements, re.I | re.S)
    return m.group(1).strip() if m else requirements.strip()


class MultiAgentWrapper(Agent):
    """Coordinator + worker agents over one shared IPythonRuntime."""

    def __init__(
        self,
        model: Model,
        functions: List[Callable],
        variables: Optional[List[Variable]] = None,
        types: Optional[List[Type]] = None,
        system_instructions: Optional[str] = None,
        description: Optional[str] = None,
        requirements: Optional[str] = None,
        max_total_steps: int = 20,
        synth_reserve: int = 3,
        verify_reserve: int = 6,
        coordinator_mode: str = "llm",   # "llm" | "fixed"
    ):
        self._model = model
        self._function_names = [f.__name__ for f in functions]
        self._system_instructions = system_instructions
        self._description = description
        self._requirements = requirements
        self._required_outputs = _required_outputs(requirements)
        # Shared step budget across the whole pipeline, matched to the single
        # agent's max_steps for a fair comparison. synth_reserve steps are held
        # back for the final synthesis worker (so it can always set the required
        # outputs); earlier workers draw from the rest and may use more to recover
        # from a dead end, rather than each being starved by a fixed per-worker cap.
        self._max_total_steps = max_total_steps
        self._synth_reserve = synth_reserve
        self._verify_reserve = verify_reserve
        self._coordinator_mode = coordinator_mode
        # ONE shared runtime — the blackboard every worker reads/writes.
        self._runtime = IPythonRuntime(
            functions=[Function(f) for f in functions],
            variables=variables or [],
            types=types or [],
        )

    @property
    def runtime(self) -> IPythonRuntime:
        return self._runtime

    async def _plan(self, query: str) -> Tuple[List[dict], Optional[TokenUsage]]:
        """Return (ordered plan, coordinator token usage). Falls back to the fixed
        pipeline in 'fixed' mode or on any coordinator/parse failure."""
        fixed = [{"role": r, "task": query} for r in DEFAULT_PIPELINE]
        if self._coordinator_mode == "fixed":
            return fixed, None
        prompt = (
            f"TASK: {query}\n\n"
            f"REQUIRED OUTPUT VARIABLES: {self._required_outputs or '(see task)'}\n\n"
            "Produce the JSON plan now."
        )
        try:
            resp = await self._model.call([
                {"role": "system", "content": _COORDINATOR_SYS},
                {"role": "user", "content": prompt},
            ])
            text = getattr(resp, "content", "") or ""
            start, end = text.find("["), text.rfind("]") + 1
            if start < 0 or end <= start:
                raise ValueError("no JSON array in coordinator output")
            steps = [
                {"role": s["role"], "task": str(s.get("task", query))}
                for s in json.loads(text[start:end])
                if isinstance(s, dict) and s.get("role") in WORKER_ROLES
            ][:_MAX_PLAN_STEPS]
            if not steps:
                raise ValueError("empty plan")
            if steps[-1]["role"] != _SYNTH_ROLE:
                steps.append({"role": _SYNTH_ROLE, "task": query})
            usage = getattr(resp, "token_usage", None)
            coord_usage = TokenUsage(
                getattr(usage, "prompt_tokens", 0),
                getattr(usage, "completion_tokens", 0),
                getattr(usage, "total_tokens", 0),
            ) if usage is not None else None
            return steps, coord_usage
        except Exception:
            return fixed, None

    async def _manifest(self) -> str:
        """Compact {name: type} map of the live namespace for the next worker."""
        try:
            res = await self._runtime.execute(_MANIFEST_SNIPPET)
            out = getattr(res, "stdout", "") or ""
            i = out.find("VARS::")
            return out[i + len("VARS::"):].strip() if i >= 0 else ""
        except Exception:
            return ""

    def _build_worker(self, role: str, task: str, manifest: str, max_steps: int) -> CaveAgent:
        is_verify = role == _VERIFY_ROLE
        # The verifier's whole job is to independently RE-DERIVE and OVERWRITE wrong outputs,
        # so it must NOT get the producers' no-clobber / reuse-don't-recompute discipline.
        parts = [WORKER_ROLES[role]] if is_verify else [WORKER_ROLES[role], _SHARED_DISCIPLINE]
        if self._description:
            parts.append(f"TASK DESCRIPTION:\n{self._description}")
        if self._requirements:
            parts.append(f"TASK REQUIREMENTS:\n{self._requirements}")
        if is_verify:
            if self._required_outputs:
                parts.append(f"REQUIRED OUTPUTS TO VERIFY (and correct if wrong):\n{self._required_outputs}")
            if manifest and manifest != "{}":
                parts.append(
                    "CURRENT STAGED VALUES — verify EACH against your OWN fresh recomputation; "
                    f"do NOT trust them:\n{manifest}"
                )
        else:
            if self._required_outputs:
                if role == _SYNTH_ROLE:
                    parts.append(
                        "OUTPUT OWNERSHIP: you are the ONLY producer that assigns the required output "
                        "variables. Assign each of them now — reusing the intermediate variables "
                        "upstream agents staged rather than recomputing from scratch — and print each "
                        f"to confirm it is set:\n{self._required_outputs}"
                    )
                else:
                    parts.append(
                        "OUTPUT OWNERSHIP: do NOT assign or create the task's required output variables "
                        f"({self._required_outputs}); the synthesis agent alone assigns them. Stage your "
                        "findings in your OWN descriptively-named variables for it to reuse."
                    )
            if manifest and manifest != "{}":
                parts.append(
                    "VARIABLES ALREADY IN THE SHARED RUNTIME (already computed and correct) — "
                    f"reuse these directly; do NOT re-query or re-derive them:\n{manifest}"
                )
        parts.append(f"YOUR SUBTASK:\n{task}")
        # Forward system_instructions only when set — cave_agent>=0.7.5 formats it
        # and would crash on None (falls back to CaveAgent's default otherwise).
        agent_kwargs = dict(
            model=self._model,
            runtime=self._runtime,           # shared -> state persists across workers
            max_steps=max_steps,
            instructions="\n\n".join(parts),
            max_exec_output=10000,
        )
        if self._system_instructions is not None:
            agent_kwargs["system_instructions"] = self._system_instructions
        return CaveAgent(**agent_kwargs)

    async def run(self, query: str) -> AgentResponse:
        plan, coord_usage = await self._plan(query)
        total = coord_usage or TokenUsage()
        steps_total = 0
        code_all: List[str] = []
        synthesis_content = ""
        last_nonempty = ""

        n = len(plan)
        # Hold back steps for the final verification pass; producers + synthesis run within
        # the rest. Total stays <= max_total_steps (matched to the single agent) — the
        # multi-agent spends part of the SAME budget on independent verification instead of
        # extra producer workers.
        plan_budget = max(1, self._max_total_steps - self._verify_reserve)
        pre_pool = max(0, plan_budget - self._synth_reserve)
        with FunctionCallTracker(target_functions=self._function_names) as tracker:
            for idx, step in enumerate(plan):
                if idx == n - 1:
                    budget = max(1, plan_budget - steps_total)
                else:
                    budget = pre_pool - steps_total
                    if budget < 1:
                        continue  # producer pool spent — skip to keep the matched budget
                agent = self._build_worker(step["role"], step["task"], await self._manifest(), budget)
                res = await agent.run(step["task"])
                tu = res.token_usage
                total = total + TokenUsage(tu.prompt_tokens, tu.completion_tokens, tu.total_tokens)
                steps_total += getattr(res, "steps_taken", 0)
                code_all.extend(getattr(res, "code_snippets", []) or [])
                if (res.content or "").strip():
                    last_nonempty = res.content
                    if step["role"] == _SYNTH_ROLE:
                        synthesis_content = res.content

            # Final stage: an INDEPENDENT verification + correction pass over every required
            # output. The verifier recomputes each output from scratch and OVERWRITES wrong
            # values. This independent second computation — not division of labour — is what
            # lets the multi-agent beat a single pass. Gets all remaining steps (>= verify_reserve).
            if self._required_outputs:
                vbudget = max(1, self._max_total_steps - steps_total)
                vagent = self._build_worker(_VERIFY_ROLE, query, await self._manifest(), vbudget)
                vres = await vagent.run(query)
                tu = vres.token_usage
                total = total + TokenUsage(tu.prompt_tokens, tu.completion_tokens, tu.total_tokens)
                steps_total += getattr(vres, "steps_taken", 0)
                code_all.extend(getattr(vres, "code_snippets", []) or [])
                if (vres.content or "").strip():
                    synthesis_content = vres.content

        return AgentResponse(
            content=synthesis_content or last_nonempty,
            tool_calls=tracker.get_tool_calls(),
            steps=steps_total,
            code_snippets=code_all,
            token_usage=total,
        )


class MultiAgentCaveFactory(AgentFactory):
    """Factory mirroring CaveAgentFactory but producing MultiAgentWrapper agents.

    Same constructor signature as adapters.CaveAgentFactory so a runner can swap
    the topology while holding model / domain / benchmark / prompt constant.
    """

    def __init__(
        self,
        model: Model,
        system_instructions: Optional[str] = None,
        base_variables: Optional[List[Variable]] = None,
        extra_functions: Optional[List[Callable]] = None,
        max_total_steps: int = 20,
        synth_reserve: int = 3,
        verify_reserve: int = 6,
        coordinator_mode: str = "llm",
    ):
        self.model = model
        self.system_instructions = system_instructions
        self.base_variables = base_variables or []
        self.extra_functions = extra_functions or []
        self.max_total_steps = max_total_steps
        self.synth_reserve = synth_reserve
        self.verify_reserve = verify_reserve
        self.coordinator_mode = coordinator_mode

    def create_agent(
        self,
        functions: List[Callable],
        variables: Optional[List[Variable]] = None,
        types: Optional[List[Type]] = None,
        description: Optional[str] = None,
        requirements: Optional[str] = None,
    ) -> MultiAgentWrapper:
        return MultiAgentWrapper(
            model=self.model,
            functions=functions + self.extra_functions,
            variables=(variables or []) + self.base_variables,
            types=types,
            system_instructions=self.system_instructions,
            description=description,
            requirements=requirements,
            max_total_steps=self.max_total_steps,
            synth_reserve=self.synth_reserve,
            verify_reserve=self.verify_reserve,
            coordinator_mode=self.coordinator_mode,
        )
