"""CaveAgent adapter for air-bench benchmarking framework.

This adapter wraps CaveAgent to conform to the abstract Agent interface,
allowing it to be evaluated using the same pipeline as JSON function calling agents.
"""

from typing import List, Callable, Optional
from core.agent import Agent, AgentFactory, AgentResponse, TokenUsage
from core.tracker import FunctionCallTracker
from cave_agent import CaveAgent, Model
from cave_agent.runtime import IPythonRuntime, Function, Variable, Type


class CaveAgentWrapper(Agent):
    """Agent implementation that wraps CaveAgent.

    CaveAgent executes Python code to call functions, so we use
    sys.setprofile() via FunctionCallTracker to capture actual function calls.
    """

    def __init__(
        self,
        model: Model,
        functions: List[Callable],
        variables: Optional[List[Variable]] = None,
        types: Optional[List[Type]] = None,
        system_instructions: Optional[str] = None,
        description: Optional[str] = None,
        requirements: Optional[str] = None
    ):
        """Initialize the CaveAgentWrapper.

        Args:
            model: The LLM model configuration
            functions: List of callable functions/tools
            variables: List of variables for stateful execution
            types: List of custom types
            description: Scenario-specific agent description
            requirements: Scenario-specific requirements
        """
        self._model = model
        self._functions = functions
        self._function_names = [f.__name__ for f in functions]
        self._variables = variables or []
        self._types = types or []
        # Build task instructions from scenario metadata
        parts = []
        if description:
            parts.append(f"TASK DESCRIPTION:\n{description}")
        if requirements:
            parts.append(f"TASK REQUIREMENTS:\n{requirements}")
        task_instructions = "\n\n".join(parts) or None

        wrapped_functions = [Function(f) for f in functions]
        runtime = IPythonRuntime(
            functions=wrapped_functions,
            variables=self._variables,
            types=self._types
        )

        # Create the underlying CaveAgent. Forward instructions / system_instructions
        # only when provided: cave_agent>=0.7.5 does `system_instructions.format(...)`
        # and crashes on None, so fall back to CaveAgent's own defaults otherwise.
        agent_kwargs = dict(
            model=model,
            runtime=runtime,
            max_steps=20,
            max_exec_output=10000,
        )
        if task_instructions is not None:
            agent_kwargs["instructions"] = task_instructions
        if system_instructions is not None:
            agent_kwargs["system_instructions"] = system_instructions
        self._agent = CaveAgent(**agent_kwargs)

    @property
    def runtime(self) -> IPythonRuntime:
        """Get the Python runtime for accessing variables."""
        return self._agent.runtime

    async def run(self, query: str) -> AgentResponse:
        """Run the agent and capture function calls via profiling.

        Args:
            query: The user input query

        Returns:
            AgentResponse with result, tool calls, steps, code snippets, and token usage
        """
        # Use context manager to safely track function calls
        with FunctionCallTracker(target_functions=self._function_names) as tracker:
            result = await self._agent.run(query)

        # Get tracked tool calls
        tool_calls = tracker.get_tool_calls()

        # Extract token usage from CaveAgent's response
        cave_token_usage = result.token_usage
        token_usage = TokenUsage(
            prompt_tokens=cave_token_usage.prompt_tokens,
            completion_tokens=cave_token_usage.completion_tokens,
            total_tokens=cave_token_usage.total_tokens
        )

        return AgentResponse(
            content=result.content,
            tool_calls=tool_calls,
            steps=result.steps_taken,
            code_snippets=result.code_snippets,
            token_usage=token_usage
        )


class CaveAgentFactory(AgentFactory):
    """Factory for creating CaveAgent instances.

    The factory holds global config (model, system_instructions, base_variables)
    that applies to every agent. Per-scenario config (functions, variables, types,
    description, requirements) is passed to create_agent() by the evaluator.

    base_variables (e.g. the DB engine) are merged into every agent's variables.
    system_instructions are passed through as-is — they are not merged with
    per-scenario fields; scenario-level description/requirements become the
    CaveAgent task instructions instead.
    """

    def __init__(
        self,
        model: Model,
        system_instructions: Optional[str] = None,
        base_variables: Optional[List[Variable]] = None,
        extra_functions: Optional[List[Callable]] = None,
    ):
        """Initialize the factory with a model configuration.

        Args:
            model: The LLM model to use for all created agents
            system_instructions: System instructions for the agent
            base_variables: Variables injected into every agent (e.g. DB engine).
                These are merged with per-scenario variables in create_agent().
            extra_functions: Domain-specific functions injected into every agent
                (e.g. search_hk_location for HK domain).
        """
        self.model = model
        self.system_instructions = system_instructions
        self.base_variables = base_variables or []
        self.extra_functions = extra_functions or []

    def create_agent(
        self,
        functions: List[Callable],
        variables: Optional[List[Variable]] = None,
        types: Optional[List[Type]] = None,
        description: Optional[str] = None,
        requirements: Optional[str] = None
    ) -> CaveAgentWrapper:
        """Create a CaveAgent with the specified configuration.

        Args:
            functions: List of callable functions/tools
            variables: Per-scenario variables (merged with base_variables)
            types: List of custom types
            description: Scenario-specific agent description
            requirements: Scenario-specific requirements

        Returns:
            A CaveAgentWrapper instance
        """
        return CaveAgentWrapper(
            model=self.model,
            functions=functions + self.extra_functions,
            variables=(variables or []) + self.base_variables,
            system_instructions=self.system_instructions,
            types=types,
            description=description,
            requirements=requirements
        )
