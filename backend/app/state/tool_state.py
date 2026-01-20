"""
Tool State Machine for managing tool execution lifecycle.

This module defines tool states and manages the lifecycle of multiple concurrent
tool executions, including queueing and delivery coordination.
"""

import time
from enum import Enum
from typing import Any, Dict, List, Optional

from app.utils.logging import logger


class ToolState(Enum):
    """Enum representing the different tool execution states."""

    IDLE = "idle"
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    DELIVERING = "delivering"
    FAILED = "failed"


class ToolExecutionRecord:
    """Record of a single tool execution."""

    def __init__(
        self,
        tool_name: str,
        tool_call_id: str,
        parameters: Dict[str, Any],
    ):
        """
        Initialize a tool execution record.

        Args:
            tool_name: Name of the tool being executed.
            tool_call_id: Unique identifier for this tool call.
            parameters: Parameters passed to the tool.
        """
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id
        self.parameters = parameters
        self.state = ToolState.PENDING
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.delivered_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for logging/debugging."""
        return {
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "delivered_at": self.delivered_at,
            "has_result": self.result is not None,
            "has_error": self.error is not None,
        }


class ToolStateMachine:
    """
    Manages tool execution states and coordinates result delivery.

    Tracks multiple concurrent tool executions and manages their lifecycle
    from pending to completion and delivery.
    """

    def __init__(self):
        """Initialize the tool state machine."""
        self._tools: Dict[str, ToolExecutionRecord] = {}
        self._pending_delivery: List[str] = []  # List of tool_call_ids ready to deliver
        self._awaiting_user_ack = False

    def register_tool_call(
        self,
        tool_name: str,
        tool_call_id: str,
        parameters: Dict[str, Any],
    ) -> ToolExecutionRecord:
        """
        Register a new tool call.

        Args:
            tool_name: Name of the tool.
            tool_call_id: Unique identifier for the tool call.
            parameters: Tool parameters.

        Returns:
            ToolExecutionRecord for the registered tool.
        """
        record = ToolExecutionRecord(tool_name, tool_call_id, parameters)
        self._tools[tool_call_id] = record

        logger.info(
            "Tool call registered",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            parameters=parameters,
        )

        return record

    def mark_executing(self, tool_call_id: str) -> bool:
        """
        Mark a tool as currently executing.

        Args:
            tool_call_id: ID of the tool call.

        Returns:
            bool: True if state was updated, False otherwise.
        """
        if tool_call_id not in self._tools:
            logger.error(
                "Cannot mark unknown tool as executing", tool_call_id=tool_call_id
            )
            return False

        record = self._tools[tool_call_id]
        record.state = ToolState.EXECUTING
        record.started_at = time.time()

        logger.info(
            "Tool execution started",
            tool_name=record.tool_name,
            tool_call_id=tool_call_id,
        )

        return True

    def mark_completed(
        self,
        tool_call_id: str,
        result: Dict[str, Any],
    ) -> bool:
        """
        Mark a tool as completed with its result.

        Args:
            tool_call_id: ID of the tool call.
            result: Result returned by the tool.

        Returns:
            bool: True if state was updated, False otherwise.
        """
        if tool_call_id not in self._tools:
            logger.error(
                "Cannot mark unknown tool as completed", tool_call_id=tool_call_id
            )
            return False

        record = self._tools[tool_call_id]
        record.state = ToolState.COMPLETED
        record.result = result
        record.completed_at = time.time()

        # Add to pending delivery queue
        if tool_call_id not in self._pending_delivery:
            self._pending_delivery.append(tool_call_id)

        duration = record.completed_at - record.started_at if record.started_at else 0

        logger.info(
            "Tool execution completed",
            tool_name=record.tool_name,
            tool_call_id=tool_call_id,
            duration_seconds=f"{duration:.2f}",
            pending_count=len(self._pending_delivery),
        )

        return True

    def mark_failed(self, tool_call_id: str, error: str) -> bool:
        """
        Mark a tool as failed with an error.

        Args:
            tool_call_id: ID of the tool call.
            error: Error message.

        Returns:
            bool: True if state was updated, False otherwise.
        """
        if tool_call_id not in self._tools:
            logger.error(
                "Cannot mark unknown tool as failed", tool_call_id=tool_call_id
            )
            return False

        record = self._tools[tool_call_id]
        record.state = ToolState.FAILED
        record.error = error
        record.completed_at = time.time()

        logger.error(
            "Tool execution failed",
            tool_name=record.tool_name,
            tool_call_id=tool_call_id,
            error=error,
        )

        return True

    def mark_delivering(self, tool_call_id: str) -> bool:
        """
        Mark a tool result as currently being delivered.

        Args:
            tool_call_id: ID of the tool call.

        Returns:
            bool: True if state was updated, False otherwise.
        """
        if tool_call_id not in self._tools:
            logger.error(
                "Cannot mark unknown tool as delivering", tool_call_id=tool_call_id
            )
            return False

        record = self._tools[tool_call_id]
        record.state = ToolState.DELIVERING

        # Remove from pending delivery queue
        if tool_call_id in self._pending_delivery:
            self._pending_delivery.remove(tool_call_id)

        logger.info(
            "Tool result delivery started",
            tool_name=record.tool_name,
            tool_call_id=tool_call_id,
        )

        return True

    def mark_delivered(self, tool_call_id: str) -> bool:
        """
        Mark a tool result as delivered and return to idle.

        Args:
            tool_call_id: ID of the tool call.

        Returns:
            bool: True if state was updated, False otherwise.
        """
        if tool_call_id not in self._tools:
            logger.error(
                "Cannot mark unknown tool as delivered", tool_call_id=tool_call_id
            )
            return False

        record = self._tools[tool_call_id]
        record.state = ToolState.IDLE
        record.delivered_at = time.time()

        logger.info(
            "Tool result delivered",
            tool_name=record.tool_name,
            tool_call_id=tool_call_id,
        )

        return True

    def has_pending_results(self) -> bool:
        """
        Check if there are any tool results pending delivery.

        Returns:
            bool: True if there are pending results.
        """
        return len(self._pending_delivery) > 0

    def get_pending_count(self) -> int:
        """
        Get the count of pending tool results.

        Returns:
            int: Number of pending results.
        """
        return len(self._pending_delivery)

    def get_pending_tool_ids(self) -> List[str]:
        """
        Get list of tool call IDs with pending results.

        Returns:
            List of tool call IDs.
        """
        return self._pending_delivery.copy()

    def get_next_pending(self) -> Optional[ToolExecutionRecord]:
        """
        Get the next pending tool result to deliver (FIFO).

        Returns:
            ToolExecutionRecord or None if no pending results.
        """
        if not self._pending_delivery:
            return None

        tool_call_id = self._pending_delivery[0]
        return self._tools.get(tool_call_id)

    def get_tool_record(self, tool_call_id: str) -> Optional[ToolExecutionRecord]:
        """
        Get the execution record for a specific tool call.

        Args:
            tool_call_id: ID of the tool call.

        Returns:
            ToolExecutionRecord or None if not found.
        """
        return self._tools.get(tool_call_id)

    def get_all_pending_records(self) -> List[ToolExecutionRecord]:
        """
        Get all pending tool execution records.

        Returns:
            List of ToolExecutionRecord objects for pending tools.
        """
        return [
            self._tools[tool_id]
            for tool_id in self._pending_delivery
            if tool_id in self._tools
        ]

    def can_deliver_results(self) -> bool:
        """
        Check if tool results can be delivered right now.

        Considers whether we're awaiting user acknowledgment.

        Returns:
            bool: True if results can be delivered.
        """
        return self.has_pending_results() and not self._awaiting_user_ack

    def set_awaiting_user_ack(self, awaiting: bool):
        """
        Set whether the system is awaiting user acknowledgment.

        Args:
            awaiting: True if awaiting user acknowledgment.
        """
        self._awaiting_user_ack = awaiting
        logger.info("User acknowledgment state updated", awaiting_ack=awaiting)

    def is_awaiting_user_ack(self) -> bool:
        """
        Check if the system is awaiting user acknowledgment.

        Returns:
            bool: True if awaiting acknowledgment.
        """
        return self._awaiting_user_ack

    def get_active_tools_count(self) -> int:
        """
        Get count of tools currently executing.

        Returns:
            int: Number of tools in EXECUTING state.
        """
        return sum(
            1 for record in self._tools.values() if record.state == ToolState.EXECUTING
        )

    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all tool states.

        Returns:
            Dictionary with counts of tools in each state.
        """
        summary = {
            "total_tools": len(self._tools),
            "pending": 0,
            "executing": 0,
            "completed": 0,
            "delivering": 0,
            "failed": 0,
            "idle": 0,
            "pending_delivery_count": len(self._pending_delivery),
            "awaiting_user_ack": self._awaiting_user_ack,
        }

        for record in self._tools.values():
            state_key = record.state.value
            if state_key in summary:
                summary[state_key] += 1

        return summary

    def cleanup_old_tools(self, max_age_seconds: float = 3600):
        """
        Clean up old tool records that have been delivered.

        Args:
            max_age_seconds: Maximum age in seconds for keeping delivered tools.
        """
        current_time = time.time()
        to_remove = []

        for tool_call_id, record in self._tools.items():
            if record.state == ToolState.IDLE and record.delivered_at:
                age = current_time - record.delivered_at
                if age > max_age_seconds:
                    to_remove.append(tool_call_id)

        for tool_call_id in to_remove:
            del self._tools[tool_call_id]

        if to_remove:
            logger.info("Cleaned up old tool records", count=len(to_remove))
