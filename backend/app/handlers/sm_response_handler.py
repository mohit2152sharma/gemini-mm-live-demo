"""
State-aware Gemini Response Handler.

Handles responses from Gemini Live API and coordinates with the state machine
to ensure proper sequencing of bot responses and tool result delivery.
"""

import asyncio
import time
from typing import Any, Dict

from quart import websocket
from websockets.exceptions import ConnectionClosedOK

from app.handlers.audio_processor import AudioProcessor
from app.handlers.state_machine_handler import StateMachineCoordinator
from app.handlers.transcription_processor import TranscriptionProcessor
from app.state.conversation_state import ConversationState
from app.utils.logging import logger


class StateMachineResponseHandler:
    """Handles Gemini responses with state machine coordination."""

    def __init__(
        self,
        session,
        session_state: Dict[str, Any],
        coordinator: StateMachineCoordinator,
    ):
        """
        Initialize the response handler.

        Args:
            session: Gemini session.
            session_state: Shared session state dictionary.
            coordinator: State machine coordinator.
        """
        self.session = session
        self.session_state = session_state
        self.coordinator = coordinator

        # Processors
        self.audio_processor = AudioProcessor(session_state)
        self.transcription_processor = TranscriptionProcessor(session_state)

        # Speech tracking
        self._last_audio_timestamp: float = 0
        self._speech_gap_threshold = 1.5  # 1.5 seconds without audio = speech complete
        self._is_tool_response = False
        self._audio_processing_lock = asyncio.Lock()

    async def handle_gemini_responses(self):
        """Main Gemini response handling loop."""
        try:
            while self.session_state["active_processing"]:
                had_activity = False

                async for response in self.session.receive():
                    had_activity = True

                    if not self.session_state["active_processing"]:
                        break

                    await self._process_response(response)

                    # Check for speech completion and coordinate tool delivery
                    await self._check_speech_completion()
                    await self.coordinator.coordinate_tool_delivery()

                    if not self.session_state["active_processing"]:
                        break

                # Small delay if no activity
                if not had_activity and self.session_state["active_processing"]:
                    await asyncio.sleep(0.1)

                    # Still check for speech completion and tool delivery during idle
                    await self._check_speech_completion()
                    await self.coordinator.coordinate_tool_delivery()

        except ConnectionClosedOK:
            logger.info("Connection to client closed")
            self.session_state["active_processing"] = False

        except Exception as e:
            logger.error(
                "Error in handle_gemini_responses",
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            self.session_state["active_processing"] = False

        finally:
            self.session_state["active_processing"] = False

    async def _process_response(self, response):
        """
        Process individual response from Gemini.

        Args:
            response: Response object from Gemini.
        """
        response_timestamp = time.strftime("%H:%M:%S.%f")[:-3]

        try:
            # Handle session updates
            await self._handle_session_updates(response)

            # Handle audio data
            if response.data is not None:
                await self._handle_audio_response(response.data, response_timestamp)

            # Handle server content
            elif response.server_content:
                await self._handle_server_content(
                    response.server_content,
                    response_timestamp,
                )

            # Handle tool calls
            elif response.tool_call:
                await self._handle_tool_call(response.tool_call, response_timestamp)

            # Handle errors
            elif hasattr(response, "error") and response.error:
                await self._handle_error(response.error, response_timestamp)

        except Exception as e:
            logger.error(
                "Error processing response",
                timestamp=response_timestamp,
                error=str(e),
                exc_info=True,
            )

    async def _handle_session_updates(self, response):
        """
        Handle session resumption updates.

        Args:
            response: Response object from Gemini.
        """
        if response.session_resumption_update:
            update = response.session_resumption_update
            if update.resumable and update.new_handle:
                self.session_state["current_session_handle"] = update.new_handle
                logger.info("Session handle updated", new_handle=update.new_handle)

        if hasattr(response, "session_handle") and response.session_handle:
            new_handle = response.session_handle
            if new_handle != self.session_state.get("current_session_handle"):
                self.session_state["current_session_handle"] = new_handle
                logger.info("Session handle updated", new_handle=new_handle)

    async def _handle_audio_response(self, audio_data, timestamp: str):
        """
        Handle audio data from Gemini.

        Args:
            audio_data: Audio data from Gemini.
            timestamp: Timestamp string for logging.
        """
        async with self._audio_processing_lock:
            logger.debug("Received audio data from Gemini", timestamp=timestamp)

            # Update conversation state - bot is speaking
            current_state = self.coordinator.get_conversation_state()
            if current_state != ConversationState.BOT_SPEAKING:
                await self.coordinator.handle_state_transition(
                    ConversationState.BOT_SPEAKING,
                    trigger="gemini_audio_start",
                )
                logger.info("Bot started speaking", timestamp=timestamp)

            # Track last audio timestamp for speech gap detection
            self._last_audio_timestamp = time.time()

            # Process and send audio to client
            await self.audio_processor.process_audio_response(audio_data)

    async def _handle_server_content(self, server_content, timestamp: str):
        """
        Handle server content from Gemini.

        Args:
            server_content: Server content object.
            timestamp: Timestamp string for logging.
        """
        logger.debug("Received server content from Gemini", timestamp=timestamp)

        # Handle interruption
        if server_content.interrupted:
            await self._handle_interruption()

        # Handle turn completion
        if server_content.turn_complete:
            await self._handle_turn_complete(timestamp)

        # Handle transcriptions
        await self.transcription_processor.process_transcriptions(server_content)

        # Handle unhandled content
        await self._handle_unhandled_content(server_content)

    async def _handle_interruption(self):
        """Handle Gemini interruption signal."""
        logger.warning("Gemini sent INTERRUPTED signal")

        # Don't send interrupt if this is a tool response
        if not self._is_tool_response:
            try:
                await websocket.send_json({"type": "interrupt_playback"})
                logger.info("Sent interrupt_playback to client")
            except Exception as e:
                logger.error("Error sending interrupt_playback", error=str(e))
                self.session_state["active_processing"] = False

    async def _handle_turn_complete(self, timestamp: str):
        """
        Handle turn completion signal.

        Args:
            timestamp: Timestamp string for logging.
        """
        logger.info("Turn complete", timestamp=timestamp)

        # Reset tool response flag if set
        if self._is_tool_response:
            logger.info("Resetting tool response flag on turn completion")
            self._is_tool_response = False

        # Transition back to idle after turn completes
        current_state = self.coordinator.get_conversation_state()
        if current_state == ConversationState.BOT_SPEAKING:
            await self.coordinator.handle_state_transition(
                ConversationState.IDLE,
                trigger="turn_complete",
            )

    async def _handle_tool_call(self, tool_call, timestamp: str):
        """
        Handle tool call from Gemini.

        Args:
            tool_call: Tool call object.
            timestamp: Timestamp string for logging.
        """
        function_name = tool_call.function_calls[0].name
        logger.info(
            "Received tool call from Gemini",
            timestamp=timestamp,
            tool_name=function_name,
        )

        # Execute tool via the executor
        try:
            tool_call_id = await self.coordinator.tool_executor.execute_tool_call(
                tool_call
            )
            logger.info(
                "Tool call queued for execution",
                tool_name=function_name,
                tool_call_id=tool_call_id,
            )

        except Exception as e:
            logger.error(
                "Failed to execute tool call",
                tool_name=function_name,
                error=str(e),
                exc_info=True,
            )

    async def _handle_unhandled_content(self, server_content):
        """
        Handle unhandled server content.

        Args:
            server_content: Server content object.
        """
        is_transcription = (
            hasattr(server_content, "input_transcription")
            and server_content.input_transcription
        ) or (
            hasattr(server_content, "output_transcription")
            and server_content.output_transcription
        )

        is_control_signal = (
            (
                hasattr(server_content, "generation_complete")
                and server_content.generation_complete
            )
            or (
                hasattr(server_content, "turn_complete")
                and server_content.turn_complete
            )
            or (hasattr(server_content, "interrupted") and server_content.interrupted)
        )

        if not is_transcription and not is_control_signal:
            unhandled_text = self._extract_unhandled_text(server_content)
            if unhandled_text:
                logger.debug(
                    "Received unhandled server_content text", text=unhandled_text
                )
            elif not hasattr(server_content, "tool_call"):
                logger.debug("Received server_content without known parts")

    def _extract_unhandled_text(self, server_content) -> str:
        """
        Extract unhandled text from server content.

        Args:
            server_content: Server content object.

        Returns:
            Extracted text or empty string.
        """
        unhandled_text = ""

        if hasattr(server_content, "text") and server_content.text:
            unhandled_text = server_content.text
        elif (
            hasattr(server_content, "model_turn")
            and server_content.model_turn
            and hasattr(server_content.model_turn, "parts")
        ):
            for part in server_content.model_turn.parts:
                if part.text:
                    unhandled_text += (" " if unhandled_text else "") + part.text
        elif hasattr(server_content, "output_text") and server_content.output_text:
            unhandled_text = server_content.output_text

        return unhandled_text

    async def _check_speech_completion(self):
        """
        Check if bot has finished speaking based on audio gap.

        Transitions from BOT_SPEAKING to IDLE when no audio received for threshold time.
        """
        current_state = self.coordinator.get_conversation_state()

        # Only check if bot is speaking
        if current_state != ConversationState.BOT_SPEAKING:
            return

        # Check if we have a recent audio timestamp
        if self._last_audio_timestamp == 0:
            return

        # Check time since last audio
        current_time = time.time()
        time_since_audio = current_time - self._last_audio_timestamp

        if time_since_audio > self._speech_gap_threshold:
            logger.info(
                "Speech gap detected - bot finished speaking",
                gap_seconds=f"{time_since_audio:.2f}",
            )

            # Transition back to idle
            await self.coordinator.handle_state_transition(
                ConversationState.IDLE,
                trigger="speech_gap_detected",
            )

            # Reset audio timestamp
            self._last_audio_timestamp = 0

    async def _handle_error(self, error, timestamp: str):
        """
        Handle error responses from Gemini.

        Args:
            error: Error object.
            timestamp: Timestamp string for logging.
        """
        error_details = error
        if hasattr(error, "message"):
            error_details = error.message

        logger.error(
            "Gemini error in response",
            timestamp=timestamp,
            error=str(error_details),
        )

        try:
            await websocket.send(f"[ERROR_FROM_GEMINI]: {str(error_details)}")
        except Exception as e:
            logger.error("Error sending Gemini error to client", error=str(e))
            self.session_state["active_processing"] = False
