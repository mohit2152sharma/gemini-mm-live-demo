"""
Core state machine implementation with validation and transition tracking.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class ConversationState(Enum):
    """States for the overall conversation flow."""

    IDLE = "idle"
    USER_SPEAKING = "user_speaking"
    BOT_SPEAKING = "bot_speaking"
    TOOL_EXECUTING = "tool_executing"
    AWAITING_USER_ACK = "awaiting_user_ack"
    DELIVERING_TOOL_RESULT = "delivering_tool_result"


class ToolExecutionState(Enum):
    """States for individual tool execution lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class StateTransition:
    """Record of a state transition."""

    from_state: Any
    to_state: Any
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class StateMachine:
    """
    Base state machine with transition validation and history tracking.
    """

    def __init__(
        self,
        initial_state: Enum,
        valid_transitions: Optional[Dict[Enum, Set[Enum]]] = None,
    ):
        """
        Initialize state machine.

        Args:
            initial_state: Starting state
            valid_transitions: Dict mapping each state to set of valid next states
        """
        self.current_state = initial_state
        self.valid_transitions = valid_transitions or {}
        self.transition_history: List[StateTransition] = []
        self.state_entry_hooks: Dict[Enum, List[Callable]] = {}
        self.state_exit_hooks: Dict[Enum, List[Callable]] = {}

        # Record initial state
        self.transition_history.append(
            StateTransition(
                from_state=None,
                to_state=initial_state,
                timestamp=time.time(),
                metadata={"type": "initialization"},
            )
        )

    def transition(
        self, new_state: Enum, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Transition to a new state if valid.

        Args:
            new_state: Target state
            metadata: Optional metadata about the transition

        Returns:
            True if transition succeeded, False otherwise
        """
        if not self._is_valid_transition(new_state):
            print(
                f"⚠️  INVALID TRANSITION: {self.current_state.value} → {new_state.value}"
            )
            return False

        old_state = self.current_state

        # Call exit hooks for current state
        self._call_hooks(self.state_exit_hooks.get(old_state, []), old_state, new_state)

        # Perform transition
        self.current_state = new_state

        # Record transition
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=time.time(),
            metadata=metadata or {},
        )
        self.transition_history.append(transition)

        # Call entry hooks for new state
        self._call_hooks(
            self.state_entry_hooks.get(new_state, []), old_state, new_state
        )

        print(
            f"✅ STATE TRANSITION: {old_state.value} → {new_state.value} "
            f"(metadata: {metadata or {}})"
        )

        return True

    def _is_valid_transition(self, new_state: Enum) -> bool:
        """Check if transition to new_state is valid."""
        # If no valid transitions defined, allow all
        if not self.valid_transitions:
            return True

        # Same state is always valid
        if new_state == self.current_state:
            return True

        # Check if new_state is in valid transitions for current state
        valid_next_states = self.valid_transitions.get(self.current_state, set())
        return new_state in valid_next_states

    def _call_hooks(
        self, hooks: List[Callable], from_state: Enum, to_state: Enum
    ) -> None:
        """Call state hooks."""
        for hook in hooks:
            try:
                hook(from_state, to_state)
            except Exception as e:
                print(f"❌ Error in state hook: {e}")

    def on_enter(self, state: Enum, hook: Callable) -> None:
        """Register a hook to call when entering a state."""
        if state not in self.state_entry_hooks:
            self.state_entry_hooks[state] = []
        self.state_entry_hooks[state].append(hook)

    def on_exit(self, state: Enum, hook: Callable) -> None:
        """Register a hook to call when exiting a state."""
        if state not in self.state_exit_hooks:
            self.state_exit_hooks[state] = []
        self.state_exit_hooks[state].append(hook)

    def in_state(self, state: Enum) -> bool:
        """Check if currently in given state."""
        return self.current_state == state

    def in_any_state(self, states: Set[Enum]) -> bool:
        """Check if currently in any of the given states."""
        return self.current_state in states

    def get_state(self) -> Enum:
        """Get current state."""
        return self.current_state

    def get_transition_history(self) -> List[StateTransition]:
        """Get full transition history."""
        return list(self.transition_history)

    def get_recent_transitions(self, count: int = 5) -> List[StateTransition]:
        """Get N most recent transitions."""
        return self.transition_history[-count:]
