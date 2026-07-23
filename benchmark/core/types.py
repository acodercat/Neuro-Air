"""Core data types for the AirBench framework.

Three groups:
- Input (benchmark JSON → memory): `Turn`, `Conversation`, `BenchmarkScenario`.
- Runtime: `ToolCall` is what the agent's tool tracker emits during one turn;
  `runtime_variables` is what the runtime exposes at end of turn.
- Output (memory → result JSON): `TurnMetrics`, `TurnResult`,
  `ConversationResult`, `ScenarioMetrics`, `ScenarioResult` — what
  `scripts/run.py` writes under `experiments/<exp_id>/`.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable
from cave_agent.runtime import Type, Variable


@dataclass
class ToolCall:
    """One tool/function call captured during agent execution."""

    function: str
    arguments: Dict[str, Any]
    call_id: str

    def __repr__(self) -> str:
        return f"ToolCall(function={self.function}, call_id={self.call_id})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "function": self.function,
            "arguments": self.arguments,
            "call_id": self.call_id,
        }


# Input data structures (from benchmark JSON files)

@dataclass
class Turn:
    """A single turn in a benchmark conversation."""

    query: str = ""                                # optional if pre_turn_hook supplies it
    validator: Optional[str] = None                # name of a callable in module.validators
    pre_turn_hook: Optional[str] = None            # injects randomness / mutates runtime state

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Turn":
        return cls(
            query=data.get("query", ""),
            validator=data.get("validator"),
            pre_turn_hook=data.get("pre_turn_hook"),
        )


@dataclass
class Conversation:
    """A conversation in a benchmark scenario."""

    id: str
    turns: List[Turn]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        turns = [Turn.from_dict(turn) for turn in data.get("turns", [])]
        return cls(
            id=data.get("id", "unnamed_conversation"),
            turns=turns,
        )


@dataclass
class BenchmarkScenario:
    """Scenario module contents — tools, variables, validators, hooks, prompts."""

    tools: List[Callable] = field(default_factory=list)
    variables: List[Variable] = field(default_factory=list)
    validators: Dict[str, Callable] = field(default_factory=dict)
    hooks: Dict[str, Callable] = field(default_factory=dict)
    types: List[Type] = field(default_factory=list)
    description: Optional[str] = None
    requirements: Optional[str] = None

    @classmethod
    def from_module(cls, module, json_config: Optional[Dict[str, Any]] = None) -> "BenchmarkScenario":
        """Read tools/variables/etc. off a module, with JSON overrides for prompts.

        Precedence for description/requirements: JSON > module attribute > None.
        """
        json_config = json_config or {}
        description = json_config.get("description") or getattr(module, "description", None)
        requirements = json_config.get("requirements") or getattr(module, "requirements", None)
        return cls(
            tools=getattr(module, "tools", []),
            variables=getattr(module, "variables", []),
            validators=getattr(module, "validators", {}),
            hooks=getattr(module, "hooks", {}),
            types=getattr(module, "types", []),
            description=description,
            requirements=requirements,
        )


# Output data structures (evaluation results)

@dataclass
class TurnMetrics:
    """Per-turn cost / step counters."""

    steps: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TurnResult:
    """Result from evaluating a single turn."""

    query: str
    actual_response: str
    actual_calls: List[Dict[str, Any]]                       # diagnostic — agent's tool calls this turn
    validation_errors: List[str]
    metrics: TurnMetrics
    success: bool
    variables_not_set: bool = False
    error: Optional[str] = None                              # infrastructure error (API/DB), None if ok
    code_snippets: List[str] = field(default_factory=list)
    # Reserved for judge scores; scripts/score_responses.py currently writes
    # aggregated scores to a sibling `*_scores.json`, not into this field.
    judge_scores: Optional[Dict[str, Any]] = None
    # Snapshot of `scenario.variables` after the turn ran. None when the agent
    # has no runtime (only CaveAgent currently exposes one).
    runtime_variables: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["metrics"] = self.metrics.to_dict()
        # Omit optional fields when None to keep result files compact.
        for k in ("judge_scores", "runtime_variables"):
            if result[k] is None:
                del result[k]
        return result


@dataclass
class ConversationResult:
    """Result from evaluating a conversation."""

    id: str
    turns: List[TurnResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "turns": [turn.to_dict() for turn in self.turns],
        }


@dataclass
class ScenarioMetrics:
    """Overall metrics for a scenario evaluation."""

    total_turns: int = 0
    successful_turns: int = 0
    failed_turns: int = 0
    total_steps: int = 0
    success_rate: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioResult:
    """Complete result from evaluating a scenario."""

    scenario: str
    conversations: List[ConversationResult]
    metrics: ScenarioMetrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "conversations": [c.to_dict() for c in self.conversations],
            "metrics": self.metrics.to_dict(),
        }
