"""Abstract agent interfaces for air-bench benchmarking framework.

This module defines the core abstractions that allow the framework to evaluate
different agent implementations (currently only CaveAgent)
using the same evaluation pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

from core.types import ToolCall


@dataclass
class TokenUsage:
    """Tracks token usage for an agent run.

    Attributes:
        prompt_tokens: Number of tokens in the prompt/input
        completion_tokens: Number of tokens in the completion/output
        total_tokens: Total tokens used (prompt + completion)
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: 'TokenUsage') -> 'TokenUsage':
        """Add two TokenUsage objects together."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )

    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
        }


@dataclass
class AgentResponse:
    """Represents the response from an agent execution.

    Attributes:
        content: The final text response from the agent
        tool_calls: List of tool/function calls made during execution
        steps: Number of steps/turns taken to complete the task
        code_snippets: List of code snippets executed (for CaveAgent)
        token_usage: Token usage statistics for this run
    """
    content: str
    tool_calls: List[ToolCall]
    steps: int
    code_snippets: List[str] = field(default_factory=list)
    token_usage: TokenUsage = field(default_factory=TokenUsage)


class Agent(ABC):
    """Abstract base class for agent implementations.

    All agent adapters must implement this interface to be used with the
    evaluation framework.
    """

    @abstractmethod
    async def run(self, query: str) -> AgentResponse:
        """Run the agent with a query and return the response.

        Args:
            query: The user input query

        Returns:
            AgentResponse containing the result, tool calls, and metrics
        """

    @property
    def runtime(self) -> Optional[Any]:
        """Get the runtime (for CaveAgent). Returns None for other agents."""
        return None


class AgentFactory(ABC):
    """Abstract base class for creating agent instances.

    Factories encapsulate the model configuration and create agents
    with specific tools for each benchmark scenario.
    """

    @abstractmethod
    def create_agent(
        self,
        functions: List[Callable],
        variables: Optional[List[Any]] = None,
        types: Optional[List[Any]] = None,
        description: Optional[str] = None,
        requirements: Optional[str] = None
    ) -> Agent:
        """Create an agent instance with the specified configuration.

        Args:
            functions: List of callable functions/tools
            variables: List of variables (for stateful agents like CaveAgent)
            types: List of custom types (for CaveAgent)
            description: Scenario-specific agent description
            requirements: Scenario-specific requirements

        Returns:
            An Agent instance ready for evaluation
        """
