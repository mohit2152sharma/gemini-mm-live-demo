"""
Tool state manager for tracking individual tool executions.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.state_machine import ToolExecutionState


@dataclass
class ToolExecution:
    """Represents a single tool execution."""

    id: str
    tool_name: str
    state: ToolExecutionState
    arguments: Dict[str, Any]
    started_at: float
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_duration(self) -> Optional[float]:
        """Get execution duration if completed."""
        if self.completed_at is None:
            return None
        return self.completed_at - self.started_at

    def get_elapsed_time(self) -> float:
        """Get time elapsed since start."""
        end_time = self.completed_at if self.completed_at else time.time()
        return end_time - self.started_at


class ToolStateManager:
    """
    Manages state for all tool executions.
    """

    def __init__(self):
        """Initialize tool state manager."""
        # Track all tool executions by ID
        self.tool_executions: Dict[str, ToolExecution] = {}

        # Define valid state transitions for tool execution
        valid_transitions = {
            ToolExecutionState.QUEUED: {
                ToolExecutionState.RUNNING,
                ToolExecutionState.FAILED,
            },
            ToolExecutionState.RUNNING: {
                ToolExecutionState.COMPLETED,
                ToolExecutionState.FAILED,
            },
            ToolExecutionState.COMPLETED: {
                ToolExecutionState.DELIVERED,
                ToolExecutionState.FAILED,
            },
            ToolExecutionState.DELIVERED: set(),  # Terminal state
            ToolExecutionState.FAILED: set(),  # Terminal state
        }

        # State machine template for validation
        self.valid_transitions = valid_transitions

    def register_tool(
        self, tool_name: str, arguments: Dict[str, Any], tool_id: Optional[str] = None
    ) -> str:
        """
        Register a new tool execution.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            tool_id: Optional tool ID (generated if not provided)

        Returns:
            Tool execution ID
        """
        if tool_id is None:
            tool_id = str(uuid.uuid4())

        tool_exec = ToolExecution(
            id=tool_id,
            tool_name=tool_name,
            state=ToolExecutionState.QUEUED,
            arguments=arguments,
            started_at=time.time(),
        )

        self.tool_executions[tool_id] = tool_exec

        print(
            f"📝 TOOL_REGISTERED: {tool_name} (ID: {tool_id[:8]}...) with args: {arguments}"
        )

        return tool_id

    def transition(
        self, tool_id: str, new_state: ToolExecutionState, **metadata
    ) -> bool:
        """
        Transition a tool to a new state.

        Args:
            tool_id: Tool execution ID
            new_state: Target state
            **metadata: Additional metadata

        Returns:
            True if transition succeeded
        """
        if tool_id not in self.tool_executions:
            print(f"⚠️  TOOL_NOT_FOUND: {tool_id}")
            return False

        tool_exec = self.tool_executions[tool_id]
        old_state = tool_exec.state

        # Validate transition
        valid_next_states = self.valid_transitions.get(old_state, set())
        if new_state not in valid_next_states and new_state != old_state:
            print(
                f"⚠️  INVALID_TOOL_TRANSITION: {tool_exec.tool_name} {old_state.value} → {new_state.value}"
            )
            return False

        # Update state
        tool_exec.state = new_state
        tool_exec.metadata.update(metadata)

        # Update completion time if moving to terminal state
        if new_state in {ToolExecutionState.COMPLETED, ToolExecutionState.FAILED}:
            tool_exec.completed_at = time.time()

        print(
            f"✅ TOOL_STATE_CHANGE: {tool_exec.tool_name} ({tool_id[:8]}...) "
            f"{old_state.value} → {new_state.value}"
        )

        return True

    def set_result(self, tool_id: str, result: Any) -> bool:
        """
        Set the result for a tool execution.

        Args:
            tool_id: Tool execution ID
            result: Tool execution result

        Returns:
            True if successful
        """
        if tool_id not in self.tool_executions:
            print(f"⚠️  TOOL_NOT_FOUND: {tool_id}")
            return False

        tool_exec = self.tool_executions[tool_id]
        tool_exec.result = result

        print(f"📦 TOOL_RESULT_SET: {tool_exec.tool_name} ({tool_id[:8]}...)")

        return True

    def set_error(self, tool_id: str, error: str) -> bool:
        """
        Set an error for a tool execution.

        Args:
            tool_id: Tool execution ID
            error: Error message

        Returns:
            True if successful
        """
        if tool_id not in self.tool_executions:
            print(f"⚠️  TOOL_NOT_FOUND: {tool_id}")
            return False

        tool_exec = self.tool_executions[tool_id]
        tool_exec.error = error
        tool_exec.state = ToolExecutionState.FAILED

        print(f"❌ TOOL_ERROR_SET: {tool_exec.tool_name} ({tool_id[:8]}...): {error}")

        return True

    # Query methods

    def get_tool_execution(self, tool_id: str) -> Optional[ToolExecution]:
        """Get tool execution by ID."""
        return self.tool_executions.get(tool_id)

    def get_tools_in_state(self, state: ToolExecutionState) -> List[ToolExecution]:
        """Get all tools in a specific state."""
        return [
            tool_exec
            for tool_exec in self.tool_executions.values()
            if tool_exec.state == state
        ]

    def get_running_tools(self) -> List[ToolExecution]:
        """Get all currently running tools."""
        return self.get_tools_in_state(ToolExecutionState.RUNNING)

    def get_completed_tools(self) -> List[ToolExecution]:
        """Get all completed but not yet delivered tools."""
        return self.get_tools_in_state(ToolExecutionState.COMPLETED)

    def get_pending_results(self) -> List[ToolExecution]:
        """
        Get tools that have results ready but not yet delivered.
        Same as get_completed_tools.
        """
        return self.get_completed_tools()

    def has_undelivered_results(self) -> bool:
        """Check if there are any completed but undelivered results."""
        return len(self.get_completed_tools()) > 0

    def has_running_tools(self) -> bool:
        """Check if there are any tools currently running."""
        return len(self.get_running_tools()) > 0

    def get_tool_count_by_state(self) -> Dict[ToolExecutionState, int]:
        """Get count of tools in each state."""
        counts = {state: 0 for state in ToolExecutionState}
        for tool_exec in self.tool_executions.values():
            counts[tool_exec.state] += 1
        return counts

    def get_oldest_pending_result(self) -> Optional[ToolExecution]:
        """Get the oldest completed but undelivered result."""
        completed = self.get_completed_tools()
        if not completed:
            return None
        # Sort by completion time
        completed.sort(key=lambda t: t.completed_at or 0)
        return completed[0]

    def mark_as_delivered(self, tool_id: str) -> bool:
        """Mark a tool result as delivered."""
        return self.transition(tool_id, ToolExecutionState.DELIVERED)

    # Cleanup methods

    def cleanup_old_executions(self, max_age_seconds: float = 3600) -> int:
        """
        Clean up old tool executions.

        Args:
            max_age_seconds: Maximum age to keep executions

        Returns:
            Number of executions cleaned up
        """
        current_time = time.time()
        to_remove = []

        for tool_id, tool_exec in self.tool_executions.items():
            # Only clean up terminal states
            if tool_exec.state not in {
                ToolExecutionState.DELIVERED,
                ToolExecutionState.FAILED,
            }:
                continue

            age = current_time - tool_exec.started_at
            if age > max_age_seconds:
                to_remove.append(tool_id)

        for tool_id in to_remove:
            del self.tool_executions[tool_id]

        if to_remove:
            print(f"🧹 CLEANUP: Removed {len(to_remove)} old tool executions")

        return len(to_remove)

    # Debug methods

    def print_state_summary(self) -> None:
        """Print current state summary for debugging."""
        counts = self.get_tool_count_by_state()

        print(f"\n{'='*60}")
        print("Tool State Summary:")
        print(f"  Total Tools: {len(self.tool_executions)}")
        for state, count in counts.items():
            if count > 0:
                print(f"  {state.value}: {count}")

        running = self.get_running_tools()
        if running:
            print("\nRunning Tools:")
            for tool_exec in running:
                elapsed = tool_exec.get_elapsed_time()
                print(
                    f"  - {tool_exec.tool_name} ({tool_exec.id[:8]}...): {elapsed:.2f}s"
                )

        pending = self.get_pending_results()
        if pending:
            print("\nPending Results:")
            for tool_exec in pending:
                duration = tool_exec.get_duration()
                print(
                    f"  - {tool_exec.tool_name} ({tool_exec.id[:8]}...): completed in {duration:.2f}s"
                )

        print(f"{'='*60}\n")

    def get_all_tools(self) -> List[ToolExecution]:
        """Get all tool executions."""
        return list(self.tool_executions.values())
