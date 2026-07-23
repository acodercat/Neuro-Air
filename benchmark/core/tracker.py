"""Function call tracker using Python's profiling hooks."""

import sys
import inspect
from types import FrameType
from typing import Any, List, Optional, Type
from core.types import ToolCall


class FunctionCallTracker:
    """Tracker for function calls using Python's sys.setprofile."""

    def __init__(self, target_functions: Optional[List[str]] = None) -> None:
        """
        Initialize a function call tracker.

        Args:
            target_functions: List of function names to track. If None, track all functions.
        """
        self.tool_calls: List[ToolCall] = []
        self.current_call_id: int = 0
        self.target_functions = target_functions
        # Set form for O(1) membership and ancestor-frame checks in the hook.
        self._targets = set(target_functions) if target_functions is not None else None

    def start(self) -> None:
        """Start tracking function calls and returns"""
        self.tool_calls = []
        self.current_call_id = 0
        sys.setprofile(self._profile_handler)

    def stop(self) -> None:
        """Stop tracking function calls and returns"""
        sys.setprofile(None)

    def __enter__(self) -> "FunctionCallTracker":
        """Context manager entry - start tracking."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ) -> None:
        """Context manager exit - ensure tracking is stopped even on exception."""
        self.stop()

    def _profile_handler(self, frame: FrameType, event: str, arg: Any) -> None:
        """Profile handler to capture function calls and returns"""
        if event != 'call':
            return

        # Get function name
        func_name = frame.f_code.co_name

        targets = self._targets
        if targets is not None:
            # Only track the configured tool functions.
            if func_name not in targets:
                return
            # Skip tool calls made *inside* another tracked tool: when a tool's
            # body calls another tool, sys.setprofile still fires for that inner
            # call even though the agent did not initiate it. Record only the
            # outermost (agent-initiated) call — i.e. when no ancestor frame is
            # itself a tracked tool.
            parent = frame.f_back
            while parent is not None:
                if parent.f_code.co_name in targets:
                    return
                parent = parent.f_back

        # Increment call ID for this function call
        self.current_call_id += 1
        call_id = self.current_call_id

        # Get function arguments
        arg_info = inspect.getargvalues(frame)
        arguments = {}

        # Process regular arguments
        for arg_name in arg_info.args:
            if arg_name == 'self':  # Skip self in methods
                continue

            if arg_name in arg_info.locals:
                value = arg_info.locals[arg_name]
                arguments[arg_name] = value

        tool_call = ToolCall(
            call_id=str(call_id),
            function=func_name,
            arguments=arguments
        )

        # Add to call history
        self.tool_calls.append(tool_call)

    def get_tool_calls(self) -> List[ToolCall]:
        """Get tracked tool calls"""
        return self.tool_calls
