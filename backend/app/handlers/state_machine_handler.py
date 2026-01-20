"""
State Machine Coordination Handler.

This module coordinates between conversation and tool state machines to ensure
proper sequencing of user input, bot responses, and tool result delivery.
"""

import asyncio
import time

from google.genai import types

from app.state.conversation_state import ConversationState, ConversationStateMachine
from app.state.tool_executor import ToolExecutor
from app.state.tool_state import ToolStateMachine
from app.utils.logging import logger


class StateMachineCoordinator:
    """
    Coordinates conversation and tool state machines.

    Implements the core logic for:
    - Queueing tool results when bot is speaking
    - Delivering results when conversation is idle
    - Asking user about multiple pending results
    """

    def __init__(
        self,
        session,
        conversation_state: ConversationStateMachine,
        tool_state: ToolStateMachine,
        tool_executor: ToolExecutor,
    ):
        """
        Initialize the coordinator.

        Args:
            session: Gemini session.
            conversation_state: Conversation state machine.
            tool_state: Tool state machine.
            tool_executor: Tool executor.
        """
        self.session = session
        self.conversation_state = conversation_state
        self.tool_state = tool_state
        self.tool_executor = tool_executor

        # Coordination state
        self._last_delivery_check = time.time()
        self._delivery_check_interval = 0.5  # Check every 500ms

    async def coordinate_tool_delivery(self) -> bool:
        """
        Coordinate delivery of pending tool results based on conversation state.

        Returns:
            bool: True if a delivery action was taken.
        """
        # Check if enough time has passed since last check
        current_time = time.time()
        if current_time - self._last_delivery_check < self._delivery_check_interval:
            return False

        self._last_delivery_check = current_time

        # Check if there are pending results
        if not self.tool_state.has_pending_results():
            return False

        # Check conversation state
        conv_state = self.conversation_state.get_state()

        # Don't deliver if bot is speaking or user is speaking
        if conv_state in [
            ConversationState.BOT_SPEAKING,
            ConversationState.USER_SPEAKING,
        ]:
            logger.debug(
                "Deferring tool delivery - conversation in progress",
                conversation_state=conv_state.value,
                pending_count=self.tool_state.get_pending_count(),
            )
            return False

        # Don't deliver if we're already waiting for user acknowledgment
        if self.tool_state.is_awaiting_user_ack():
            logger.debug("Deferring tool delivery - awaiting user acknowledgment")
            return False

        # Conversation is IDLE - we can deliver
        return await self._handle_idle_delivery()

    async def _handle_idle_delivery(self) -> bool:
        """
        Handle tool delivery when conversation is idle.

        Returns:
            bool: True if a delivery action was taken.
        """
        pending_count = self.tool_state.get_pending_count()

        if pending_count == 0:
            return False

        # If there's only one pending result, deliver it immediately
        if pending_count == 1:
            logger.info("Delivering single pending tool result")
            return await self.tool_executor.deliver_next_pending_result()

        # Multiple pending results - ask user first
        if not self.tool_state.is_awaiting_user_ack():
            await self._ask_user_about_pending_results()
            return True

        return False

    async def _ask_user_about_pending_results(self):
        """
        Ask user via Gemini if they want to hear about pending tool results.
        """
        pending_count = self.tool_state.get_pending_count()
        tool_names = self.tool_executor.get_pending_tool_names()

        # Mark as awaiting acknowledgment
        self.tool_state.set_awaiting_user_ack(True)

        # Transition to waiting for user
        self.conversation_state.transition(
            ConversationState.WAITING_FOR_USER,
            trigger="asking_about_pending_results",
        )

        try:
            if pending_count == 1:
                prompt = f"I have the result from {tool_names[0]} ready. Would you like to hear it?"
            else:
                if pending_count == 2:
                    tools_list = f"{tool_names[0]} and {tool_names[1]}"
                else:
                    tools_list = ", ".join(tool_names[:-1]) + f", and {tool_names[-1]}"
                prompt = f"I have results from {pending_count} tools ready: {tools_list}. Would you like to hear them?"

            # Send prompt to Gemini
            user_content = types.Content(role="user", parts=[types.Part(text=prompt)])
            await self.session.send_client_content(turns=user_content)

            logger.info(
                "Asked user about pending tool results",
                pending_count=pending_count,
                tools=tool_names,
            )

        except Exception as e:
            logger.error(
                "Failed to ask user about pending results",
                error=str(e),
                exc_info=True,
            )
            # Reset state on failure
            self.tool_state.set_awaiting_user_ack(False)
            self.conversation_state.transition(
                ConversationState.IDLE,
                trigger="error_asking_about_results",
            )

    async def handle_user_acknowledgment(self, user_message: str) -> bool:
        """
        Handle user's response about wanting to hear pending tool results.

        Args:
            user_message: The user's message text.

        Returns:
            bool: True if the message was handled as an acknowledgment.
        """
        if not self.tool_state.is_awaiting_user_ack():
            return False

        user_message_lower = user_message.lower().strip()

        # Check for positive responses
        positive_indicators = [
            "yes",
            "sure",
            "okay",
            "ok",
            "yeah",
            "yep",
            "please",
            "go ahead",
            "tell me",
            "hear",
            "show",
        ]
        negative_indicators = [
            "no",
            "not now",
            "later",
            "skip",
            "nope",
            "pass",
            "don't",
        ]

        has_positive = any(ind in user_message_lower for ind in positive_indicators)
        has_negative = any(ind in user_message_lower for ind in negative_indicators)

        if has_positive and not has_negative:
            # User wants to hear results
            logger.info("User confirmed - delivering pending tool results")
            self.tool_state.set_awaiting_user_ack(False)
            self.conversation_state.transition(
                ConversationState.IDLE,
                trigger="user_confirmed_results",
            )

            # Deliver all pending results sequentially
            await self._deliver_all_pending_results()
            return True

        elif has_negative:
            # User declined
            logger.info("User declined to hear pending tool results")
            self.tool_state.set_awaiting_user_ack(False)
            self.conversation_state.transition(
                ConversationState.IDLE,
                trigger="user_declined_results",
            )
            # Keep results pending for later
            return True

        else:
            # Ambiguous response - ask for clarification
            logger.info("User response ambiguous - asking for clarification")
            try:
                clarification = "I'm not sure. Could you please say 'yes' if you want to hear the tool results, or 'no' if you'd prefer to skip them for now?"
                user_content = types.Content(
                    role="user", parts=[types.Part(text=clarification)]
                )
                await self.session.send_client_content(turns=user_content)
            except Exception as e:
                logger.error("Failed to ask for clarification", error=str(e))
                # Reset on error
                self.tool_state.set_awaiting_user_ack(False)
                self.conversation_state.transition(
                    ConversationState.IDLE,
                    trigger="error_clarification",
                )

            return True

    async def _deliver_all_pending_results(self):
        """
        Deliver all pending tool results sequentially.
        """
        while self.tool_state.has_pending_results():
            success = await self.tool_executor.deliver_next_pending_result()
            if not success:
                logger.error("Failed to deliver pending tool result")
                break

            # Brief delay between deliveries
            await asyncio.sleep(0.3)

        logger.info("Finished delivering all pending tool results")

    async def handle_state_transition(
        self,
        new_state: ConversationState,
        trigger: str = "",
    ) -> bool:
        """
        Handle a conversation state transition and trigger any necessary actions.

        Args:
            new_state: The new conversation state.
            trigger: Description of what triggered the transition.

        Returns:
            bool: True if transition was successful.
        """
        success = self.conversation_state.transition(new_state, trigger)

        if success and new_state == ConversationState.IDLE:
            # When returning to idle, check for pending tool results
            await self.coordinate_tool_delivery()

        return success

    def can_accept_user_input(self) -> bool:
        """
        Check if user input can be accepted in the current state.

        Returns:
            bool: True if input can be accepted.
        """
        return self.conversation_state.can_accept_user_input()

    def get_conversation_state(self) -> ConversationState:
        """
        Get the current conversation state.

        Returns:
            Current ConversationState.
        """
        return self.conversation_state.get_state()

    def get_status_summary(self) -> dict:
        """
        Get a summary of the coordinator's state.

        Returns:
            Dictionary with status information.
        """
        return {
            "conversation_state": self.conversation_state.get_state().value,
            "tool_status": self.tool_state.get_status_summary(),
            "can_accept_input": self.can_accept_user_input(),
        }
