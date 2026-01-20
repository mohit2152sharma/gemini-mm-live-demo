"""
Conversation State Machine for managing user/bot interaction flow.

This module defines the conversation states and manages transitions between them,
ensuring proper coordination of user input and bot responses.
"""

import time
from enum import Enum
from typing import Dict, List, Optional

from app.utils.logging import logger


class ConversationState(Enum):
    """Enum representing the different conversation states."""

    IDLE = "idle"
    USER_SPEAKING = "user_speaking"
    BOT_SPEAKING = "bot_speaking"
    WAITING_FOR_USER = "waiting_for_user"


class ConversationStateMachine:
    """
    Manages conversation state transitions and validates state changes.

    The state machine ensures that user input and bot responses are coordinated
    properly and prevents invalid state transitions.
    """

    # Define valid state transitions
    VALID_TRANSITIONS: Dict[ConversationState, List[ConversationState]] = {
        ConversationState.IDLE: [
            ConversationState.USER_SPEAKING,
            ConversationState.BOT_SPEAKING,
            ConversationState.WAITING_FOR_USER,
        ],
        ConversationState.USER_SPEAKING: [
            ConversationState.IDLE,
            ConversationState.BOT_SPEAKING,
        ],
        ConversationState.BOT_SPEAKING: [
            ConversationState.IDLE,
            ConversationState.USER_SPEAKING,  # Allow interruption
        ],
        ConversationState.WAITING_FOR_USER: [
            ConversationState.USER_SPEAKING,
            ConversationState.IDLE,
        ],
    }

    def __init__(self):
        """Initialize the conversation state machine."""
        self._current_state = ConversationState.IDLE
        self._state_history: List[Dict] = []
        self._state_start_time = time.time()

    def get_state(self) -> ConversationState:
        """Get the current conversation state."""
        return self._current_state

    def can_accept_user_input(self) -> bool:
        """
        Check if the conversation can accept user input in the current state.

        Returns:
            bool: True if user input can be accepted, False otherwise.
        """
        # User can provide input when:
        # - System is IDLE
        # - Bot is speaking (user can interrupt)
        # - System is waiting for user response
        return self._current_state in [
            ConversationState.IDLE,
            ConversationState.BOT_SPEAKING,
            ConversationState.WAITING_FOR_USER,
        ]

    def can_bot_speak(self) -> bool:
        """
        Check if the bot can start speaking in the current state.

        Returns:
            bool: True if bot can speak, False otherwise.
        """
        # Bot can speak when not already speaking and user is not actively speaking
        return self._current_state != ConversationState.BOT_SPEAKING

    def transition(self, new_state: ConversationState, trigger: str = "") -> bool:
        """
        Transition to a new state if the transition is valid.

        Args:
            new_state: The state to transition to.
            trigger: Optional description of what triggered the transition.

        Returns:
            bool: True if transition was successful, False otherwise.
        """
        if new_state == self._current_state:
            # Already in the target state
            return True

        # Check if transition is valid
        if new_state not in self.VALID_TRANSITIONS.get(self._current_state, []):
            logger.warning(
                "Invalid state transition attempted",
                from_state=self._current_state.value,
                to_state=new_state.value,
                trigger=trigger,
            )
            return False

        # Record the transition in history
        duration = time.time() - self._state_start_time
        self._state_history.append(
            {
                "from_state": self._current_state.value,
                "to_state": new_state.value,
                "trigger": trigger,
                "duration_seconds": duration,
                "timestamp": time.time(),
            }
        )

        old_state = self._current_state
        self._current_state = new_state
        self._state_start_time = time.time()

        logger.info(
            "Conversation state transition",
            from_state=old_state.value,
            to_state=new_state.value,
            trigger=trigger,
            duration_seconds=f"{duration:.2f}",
        )

        return True

    def force_transition(self, new_state: ConversationState, reason: str = ""):
        """
        Force a transition to a new state, bypassing validation.

        Use this only in exceptional cases like error recovery.

        Args:
            new_state: The state to force transition to.
            reason: Reason for forcing the transition.
        """
        logger.warning(
            "Forcing conversation state transition",
            from_state=self._current_state.value,
            to_state=new_state.value,
            reason=reason,
        )

        duration = time.time() - self._state_start_time
        self._state_history.append(
            {
                "from_state": self._current_state.value,
                "to_state": new_state.value,
                "trigger": f"FORCED: {reason}",
                "duration_seconds": duration,
                "timestamp": time.time(),
            }
        )

        self._current_state = new_state
        self._state_start_time = time.time()

    def get_state_history(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get the history of state transitions.

        Args:
            limit: Maximum number of recent transitions to return. None for all.

        Returns:
            List of state transition records.
        """
        if limit is None:
            return self._state_history.copy()
        return self._state_history[-limit:]

    def reset(self):
        """Reset the state machine to IDLE state."""
        logger.info("Resetting conversation state machine")
        self._current_state = ConversationState.IDLE
        self._state_history.clear()
        self._state_start_time = time.time()
