"""Benchmark evaluation engine.

For each conversation in a scenario the Evaluator creates a fresh agent
with a fresh copy of the scenario variables, walks the turns, runs the
agent on each query, and invokes the named validator. The validator
inspects runtime variables directly and returns a `ValidatorResult`.
"""

import copy
import logging
import time
from typing import Any, Callable, Dict, List, Optional

import sqlalchemy.exc

from core.agent import Agent, AgentFactory
from core.types import (
    BenchmarkScenario,
    Conversation,
    ConversationResult,
    ScenarioMetrics,
    ScenarioResult,
    Turn,
    TurnMetrics,
    TurnResult,
)


logger = logging.getLogger("Agent.Evaluator")

# Retry policy for validators — most query a live remote database for ground
# truth, so transient connection errors are common. Kept small; a persistent
# outage should surface as a raise, not a long silent stall.
_VALIDATOR_RETRIES = 3
_VALIDATOR_RETRY_SLEEP_S = 2


def _run_validator_with_retry(validator, response, runtime, turn):
    """Call `validator(response, runtime, turn)`, retrying on transient DB errors."""
    for attempt in range(_VALIDATOR_RETRIES):
        try:
            return validator(response, runtime, turn)
        except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.DatabaseError):
            if attempt == _VALIDATOR_RETRIES - 1:
                raise
            time.sleep(_VALIDATOR_RETRY_SLEEP_S)


def _error_turn_result(turn: Turn, error_msg: str) -> TurnResult:
    """TurnResult for a turn that could not be evaluated (infra error).

    `error` is set so downstream consumers (resume skip-logic, run_stats)
    treat this as a retryable infrastructure failure, not a model failure.
    """
    return TurnResult(
        query=turn.query,
        actual_response="",
        actual_calls=[],
        validation_errors=[f"Infrastructure error: {error_msg}"],
        metrics=TurnMetrics(),
        success=False,
        error=error_msg,
    )


class Evaluator:
    """Evaluator for benchmarking agent implementations.

    Works with any agent that implements the `Agent` interface. Currently
    the only adapter in regular use is `CaveAgent` (Python code execution),
    but the abstraction is preserved for the JSON-function-calling
    `LitellmAgent` alternate.
    """

    def __init__(self, agent_factory: AgentFactory):
        self.agent_factory = agent_factory
        self.metrics = ScenarioMetrics()

    def _reset_metrics(self) -> None:
        logger.debug("Resetting evaluation metrics")
        self.metrics = ScenarioMetrics()

    async def evaluate(
        self,
        scenario: str,
        module,
        conversations: List[Conversation],
        json_config: Optional[dict] = None,
    ) -> ScenarioResult:
        """Evaluate the agent on one scenario across all its conversations."""
        self._reset_metrics()
        scenario_contents = BenchmarkScenario.from_module(module, json_config)
        logger.info(f"Evaluating scenario {scenario} with {len(conversations)} conversations")

        conversation_results = []
        for conversation in conversations:
            result = await self._evaluate_conversation(conversation, scenario_contents)
            conversation_results.append(result)

        self.metrics.success_rate = (
            self.metrics.successful_turns / self.metrics.total_turns
            if self.metrics.total_turns > 0 else 0.0
        )
        logger.info(f"Evaluation complete. Success rate: {self.metrics.success_rate:.2f}")

        return ScenarioResult(
            scenario=scenario,
            conversations=conversation_results,
            metrics=self.metrics,
        )

    async def _evaluate_conversation(
        self,
        conversation: Conversation,
        scenario: BenchmarkScenario,
    ) -> ConversationResult:
        logger.debug(f"Evaluating conversation: {conversation.id}")

        # Fresh copy of variables per conversation: prevents mutable values
        # (lists, dicts) from leaking state across conversations.
        fresh_variables = copy.deepcopy(scenario.variables)
        agent = self.agent_factory.create_agent(
            functions=scenario.tools,
            variables=fresh_variables,
            types=scenario.types,
            description=scenario.description,
            requirements=scenario.requirements,
        )

        # A turn that raises (API/DB outage, validator bug) must not discard
        # the turns that already succeeded, and must not be recorded as a
        # model failure: it gets `error` set, which marks the whole result
        # retryable for the resume logic (core.results.result_is_complete).
        # Turns after the error are skipped — the conversation context is
        # broken, so evaluating them would not be a fair measurement.
        turn_results = []
        aborted: Optional[str] = None
        for turn in conversation.turns:
            if aborted is not None:
                turn_results.append(_error_turn_result(
                    turn, f"skipped: earlier turn in conversation errored ({aborted})"
                ))
                continue
            try:
                result = await self._evaluate_turn(
                    turn, agent, scenario.validators, scenario.hooks, scenario.variables
                )
            except Exception as e:
                aborted = f"{type(e).__name__}: {e}"
                logger.error(f"Turn errored in conversation {conversation.id}: {aborted}")
                result = _error_turn_result(turn, aborted)
            turn_results.append(result)

        # Metrics are accounted here, once per recorded turn, so exception
        # paths cannot double-count or drop a turn.
        for r in turn_results:
            self.metrics.total_turns += 1
            if r.success:
                self.metrics.successful_turns += 1
            else:
                self.metrics.failed_turns += 1
            self.metrics.total_steps += r.metrics.steps
            self.metrics.total_prompt_tokens += r.metrics.prompt_tokens
            self.metrics.total_completion_tokens += r.metrics.completion_tokens
            self.metrics.total_tokens += r.metrics.total_tokens

        return ConversationResult(id=conversation.id, turns=turn_results)

    async def _evaluate_turn(
        self,
        turn: Turn,
        agent: Agent,
        validators: Optional[Dict[str, Callable]] = None,
        hooks: Optional[Dict[str, Callable]] = None,
        variables: Optional[list] = None,
    ) -> TurnResult:
        validators = validators or {}
        hooks = hooks or {}
        variables = variables or []

        query = turn.query

        # Pre-turn hook (e.g., inject randomness, mutate runtime state, or
        # rewrite the query). Hooks need runtime access; only CaveAgent has one.
        if turn.pre_turn_hook:
            if turn.pre_turn_hook not in hooks:
                raise KeyError(
                    f"Hook '{turn.pre_turn_hook}' not found. "
                    f"Available hooks: {list(hooks.keys())}"
                )
            if agent.runtime is None:
                raise ValueError(
                    f"Hook '{turn.pre_turn_hook}' requires runtime access, "
                    "but agent has no runtime"
                )
            hook_result = hooks[turn.pre_turn_hook](agent.runtime, turn)
            if hook_result is not None:
                query = hook_result
                logger.debug(f"Pre-turn hook modified query to: {query[:100]}...")

        turn_metrics = TurnMetrics()

        result = await agent.run(query)
        turn_metrics.steps = result.steps
        turn_metrics.prompt_tokens = result.token_usage.prompt_tokens
        turn_metrics.completion_tokens = result.token_usage.completion_tokens
        turn_metrics.total_tokens = result.token_usage.total_tokens

        actual_calls_dict = [c.to_dict() for c in result.tool_calls]

        # Every turn must name a validator. A missing/misspelled `validator`
        # key in the benchmark JSON is a spec bug — silently auto-passing it
        # would inflate PV scores, so fail loudly instead.
        validator_name = turn.validator
        if not validator_name:
            raise KeyError(
                "Turn declares no validator — every turn must name one "
                f"(query: {query[:80]!r})"
            )
        if validator_name not in validators:
            raise KeyError(
                f"Validator '{validator_name}' not found. "
                f"Available validators: {list(validators.keys())}"
            )
        validator_result = _run_validator_with_retry(
            validators[validator_name], result.content, agent.runtime, turn
        )

        success = bool(validator_result.success)
        validation_errors = [] if success else [f"Custom validator failed: {validator_result.message}"]

        # Snapshot the declared scenario variables. Only meaningful for agents
        # that expose a runtime (currently CaveAgent); a failed retrieve means
        # the agent never populated that variable, which is itself signal.
        runtime_variables: Optional[Dict[str, Any]] = None
        if agent.runtime is not None and variables:
            runtime_variables = {}
            for var in variables:
                try:
                    runtime_variables[var.name] = agent.runtime.retrieve(var.name)
                except Exception:
                    pass

        return TurnResult(
            query=query,
            actual_response=result.content,
            actual_calls=actual_calls_dict,
            validation_errors=validation_errors,
            metrics=turn_metrics,
            success=success,
            variables_not_set=validator_result.variables_not_set,
            code_snippets=result.code_snippets,
            runtime_variables=runtime_variables,
        )
