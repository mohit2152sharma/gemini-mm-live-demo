"""
Conversation state manager for tracking overall conversation flow.
"""

import time
from typing import Optional

from app.core.state_machine import ConversationState, StateMachine


class ConversationStateManager:
    """
    Manages conversation-level state transitions and speech timing.
    """

    # Speech gap threshold - if no audio for this long, consider speech complete
    SPEECH_COMPLETION_THRESHOLD = 1.5  # seconds

    def __init__(self):
        """Initialize conversation state manager."""
        # Define valid state transitions
        valid_transitions = {
            ConversationState.IDLE: {
                ConversationState.USER_SPEAKING,
                ConversationState.BOT_SPEAKING,
                ConversationState.TOOL_EXECUTING,
                ConversationState.DELIVERING_TOOL_RESULT,
            },
            ConversationState.USER_SPEAKING: {
                ConversationState.IDLE,
                ConversationState.BOT_SPEAKING,
                ConversationState.TOOL_EXECUTING,
            },
            ConversationState.BOT_SPEAKING: {
                ConversationState.IDLE,
                ConversationState.TOOL_EXECUTING,
                ConversationState.AWAITING_USER_ACK,
                ConversationState.DELIVERING_TOOL_RESULT,
            },
            ConversationState.TOOL_EXECUTING: {
                ConversationState.IDLE,
                ConversationState.BOT_SPEAKING,
                ConversationState.DELIVERING_TOOL_RESULT,
            },
            ConversationState.AWAITING_USER_ACK: {
                ConversationState.IDLE,
                ConversationState.DELIVERING_TOOL_RESULT,
                ConversationState.BOT_SPEAKING,
            },
            ConversationState.DELIVERING_TOOL_RESULT: {
                ConversationState.IDLE,
                ConversationState.BOT_SPEAKING,
                ConversationState.AWAITING_USER_ACK,
            },
        }

        self.state_machine = StateMachine(
            initial_state=ConversationState.IDLE, valid_transitions=valid_transitions
        )

        # Speech timing tracking
        self.speech_start_time: Optional[float] = None
        self.last_audio_timestamp: Optional[float] = None

    def transition(self, new_state: ConversationState, **metadata) -> bool:
        """
        Transition to a new conversation state.

        Args:
            new_state: Target conversation state
            **metadata: Additional metadata about the transition

        Returns:
            True if transition succeeded
        """
        return self.state_machine.transition(new_state, metadata=metadata)

    def get_state(self) -> ConversationState:
        """Get current conversation state."""
        return self.state_machine.get_state()

    def in_state(self, state: ConversationState) -> bool:
        """Check if in given state."""
        return self.state_machine.in_state(state)

    # Predicate methods for common checks

    def is_idle(self) -> bool:
        """Check if conversation is idle."""
        return self.in_state(ConversationState.IDLE)

    def is_bot_speaking(self) -> bool:
        """Check if bot is currently speaking."""
        return self.in_state(ConversationState.BOT_SPEAKING)

    def is_awaiting_user_ack(self) -> bool:
        """Check if waiting for user acknowledgment."""
        return self.in_state(ConversationState.AWAITING_USER_ACK)

    def is_delivering_result(self) -> bool:
        """Check if currently delivering a tool result."""
        return self.in_state(ConversationState.DELIVERING_TOOL_RESULT)

    def can_deliver_tool_result(self) -> bool:
        """
        Check if we can deliver a tool result right now.

        Tool results can be delivered when:
        - Conversation is idle
        - We're not awaiting user acknowledgment
        - Bot is not actively speaking
        """
        return self.is_idle() or self.in_state(ConversationState.TOOL_EXECUTING)

    def can_accept_user_input(self) -> bool:
        """Check if we can accept user input right now."""
        # Can always accept user input unless we're in the middle of delivering
        return not self.is_delivering_result()

    # Speech timing methods

    def start_speech(self) -> None:
        """Mark that bot has started speaking."""
        current_time = time.time()
        self.speech_start_time = current_time
        self.last_audio_timestamp = current_time
        self.transition(ConversationState.BOT_SPEAKING, trigger="audio_received")

    def update_audio_timestamp(self) -> None:
        """Update timestamp when audio data is received."""
        self.last_audio_timestamp = time.time()

    def check_speech_completion(self) -> bool:
        """
        Check if speech has completed based on audio gap.

        Returns:
            True if speech should be considered complete
        """
        if not self.is_bot_speaking():
            return False

        if self.last_audio_timestamp is None:
            return False

        time_since_audio = time.time() - self.last_audio_timestamp
        return time_since_audio > self.SPEECH_COMPLETION_THRESHOLD

    def end_speech(self) -> None:
        """Mark that bot has stopped speaking."""
        if self.is_bot_speaking():
            speech_duration = None
            if self.speech_start_time:
                speech_duration = time.time() - self.speech_start_time

            self.transition(
                ConversationState.IDLE,
                trigger="speech_complete",
                speech_duration=speech_duration,
            )

            self.speech_start_time = None
            self.last_audio_timestamp = None

    def get_speech_duration(self) -> Optional[float]:
        """Get current speech duration if speaking."""
        if not self.is_bot_speaking() or not self.speech_start_time:
            return None
        return time.time() - self.speech_start_time

    def get_time_since_audio(self) -> Optional[float]:
        """Get time since last audio packet."""
        if self.last_audio_timestamp is None:
            return None
        return time.time() - self.last_audio_timestamp

    # Tool coordination methods

    def start_tool_execution(self) -> bool:
        """Transition to tool executing state."""
        return self.transition(ConversationState.TOOL_EXECUTING, trigger="tool_called")

    def start_awaiting_acknowledgment(self) -> bool:
        """Transition to awaiting user acknowledgment."""
        return self.transition(
            ConversationState.AWAITING_USER_ACK, trigger="multiple_results_pending"
        )

    def start_delivering_result(self) -> bool:
        """Transition to delivering tool result state."""
        return self.transition(
            ConversationState.DELIVERING_TOOL_RESULT, trigger="delivering_result"
        )

    def finish_delivering_result(self) -> bool:
        """Transition back to idle after delivering result."""
        return self.transition(ConversationState.IDLE, trigger="result_delivered")

    # Debug methods

    def get_transition_history(self):
        """Get state transition history."""
        return self.state_machine.get_transition_history()

    def get_recent_transitions(self, count: int = 5):
        """Get recent state transitions."""
        return self.state_machine.get_recent_transitions(count)

    def print_state_summary(self) -> None:
        """Print current state summary for debugging."""
        state = self.get_state()
        print(f"\n{'='*60}")
        print(f"Conversation State: {state.value}")
        print(f"Is Bot Speaking: {self.is_bot_speaking()}")
        print(f"Can Deliver Results: {self.can_deliver_tool_result()}")
        print(f"Can Accept Input: {self.can_accept_user_input()}")

        if self.speech_start_time:
            duration = self.get_speech_duration()
            print(f"Speech Duration: {duration:.2f}s" if duration else "N/A")

        if self.last_audio_timestamp:
            time_since = self.get_time_since_audio()
            print(f"Time Since Audio: {time_since:.2f}s" if time_since else "N/A")

        print(f"{'='*60}\n")
