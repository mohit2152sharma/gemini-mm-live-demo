"""
State-aware Client Input Handler.

Handles client WebSocket input and forwards to Gemini, integrating with the
conversation state machine to ensure proper input validation.
"""

import asyncio
import time
from typing import Any, Dict

from google.genai import types
from quart import websocket
from websockets.exceptions import ConnectionClosedOK

from app.core.config import settings
from app.handlers.state_machine_handler import StateMachineCoordinator
from app.state.conversation_state import ConversationState
from app.utils.logging import logger


class StateMachineClientHandler:
    """Handles client WebSocket input with state machine coordination."""

    def __init__(
        self,
        session,
        session_state: Dict[str, Any],
        coordinator: StateMachineCoordinator,
    ):
        """
        Initialize the client handler.

        Args:
            session: Gemini session.
            session_state: Shared session state dictionary.
            coordinator: State machine coordinator.
        """
        self.session = session
        self.session_state = session_state
        self.coordinator = coordinator
        self._audio_log_counter = 0

    async def handle_client_input(self):
        """Main client input handling loop."""
        try:
            while self.session_state["active_processing"]:
                try:
                    client_data = await asyncio.wait_for(
                        websocket.receive(), timeout=0.2
                    )

                    receive_timestamp = time.strftime("%H:%M:%S.%f")[:-3]

                    if isinstance(client_data, str):
                        logger.info(
                            "Received text message from client",
                            timestamp=receive_timestamp,
                        )
                        await self._handle_text_message(client_data)

                    elif isinstance(client_data, bytes):
                        # Log audio occasionally
                        self._audio_log_counter += 1
                        if self._audio_log_counter % 100 == 1:
                            logger.debug(
                                "Received audio data from client",
                                timestamp=receive_timestamp,
                                packet_number=self._audio_log_counter,
                            )
                        await self._handle_audio_data(client_data)

                    else:
                        logger.warning(
                            "Unexpected data type from client",
                            timestamp=receive_timestamp,
                            data_type=type(client_data).__name__,
                        )

                except asyncio.TimeoutError:
                    if not self.session_state["active_processing"]:
                        break
                    continue

                except ConnectionClosedOK:
                    logger.info("Client closed the connection")
                    self.session_state["active_processing"] = False
                    break

                except Exception as e:
                    logger.error(
                        "Error in handle_client_input",
                        error_type=type(e).__name__,
                        error=str(e),
                        exc_info=True,
                    )
                    self.session_state["active_processing"] = False
                    break

        finally:
            self.session_state["active_processing"] = False

    async def _handle_text_message(self, message_text: str):
        """
        Handle text message from client.

        Args:
            message_text: The text message from client.
        """
        if message_text == "CLIENT_AUDIO_READY":
            await self._handle_client_ready_signal()
        else:
            await self._handle_text_prompt(message_text)

    async def _handle_client_ready_signal(self):
        """Handle client audio ready signal and flush buffered audio."""
        self.session_state["client_ready_for_audio"] = True
        mic_buffer = self.session_state["mic_audio_buffer"]

        logger.info(
            "Client audio ready - flushing buffered audio",
            buffer_size=mic_buffer.size(),
        )

        # Flush buffered audio chunks
        buffered_chunks = mic_buffer.flush_all()
        flushed_count = 0

        for buffered_chunk in buffered_chunks:
            try:
                if (
                    isinstance(buffered_chunk, dict)
                    and buffered_chunk.get("type") == "buffered_audio"
                ):
                    # Send metadata first
                    metadata_msg = {
                        "type": "audio_metadata",
                        **buffered_chunk["metadata"],
                        "flushed_by_timeout": True,
                    }
                    await websocket.send_json(metadata_msg)
                    await websocket.send(buffered_chunk["audio_data"])
                    flushed_count += 1
                else:
                    # Fallback for old format
                    await websocket.send(buffered_chunk)
                    flushed_count += 1

            except Exception as e:
                logger.error(
                    "Error sending buffered audio chunk",
                    chunk_number=flushed_count,
                    error=str(e),
                )

        logger.info("Flushed buffered audio chunks", count=flushed_count)

    async def _handle_text_prompt(self, message_text: str):
        """
        Handle text prompt from client.

        Args:
            message_text: The text prompt from client.
        """
        # Check if we can accept user input based on conversation state
        if not self.coordinator.can_accept_user_input():
            logger.warning(
                "User input blocked - conversation state does not allow input",
                state=self.coordinator.get_conversation_state().value,
            )
            return

        # Check if this is a response to pending tool results question
        if await self.coordinator.handle_user_acknowledgment(message_text):
            # The message was handled as an acknowledgment
            logger.info("User message handled as tool result acknowledgment")
            return

        # Transition to USER_SPEAKING
        await self.coordinator.handle_state_transition(
            ConversationState.USER_SPEAKING,
            trigger="user_text_input",
        )

        # Handle special test message
        prompt_for_gemini = message_text
        if message_text == "SEND_TEST_AUDIO_PLEASE":
            prompt_for_gemini = "Hello Gemini, please say 'testing one two three'."

        # Send to Gemini
        try:
            user_content = types.Content(
                role="user", parts=[types.Part(text=prompt_for_gemini)]
            )
            await self.session.send_client_content(turns=user_content)

            logger.info(
                "Sent user text to Gemini",
                message_length=len(prompt_for_gemini),
            )

            # Transition back to IDLE after sending
            await self.coordinator.handle_state_transition(
                ConversationState.IDLE,
                trigger="user_message_sent",
            )

        except Exception as e:
            logger.error(
                "Failed to send user message to Gemini",
                error=str(e),
                exc_info=True,
            )
            # Force back to idle on error
            self.coordinator.conversation_state.force_transition(
                ConversationState.IDLE,
                reason="error_sending_message",
            )

    async def _handle_audio_data(self, audio_chunk: bytes):
        """
        Handle audio data from client.

        Args:
            audio_chunk: Raw audio bytes from client.
        """
        if not audio_chunk:
            logger.warning("Received empty audio chunk")
            return

        try:
            # Send audio to Gemini with the correct parameter
            if settings.GOOGLE_GENAI_USE_VERTEXAI:
                await self.session.send_realtime_input(
                    media=types.Blob(
                        mime_type=f"audio/pcm;rate={settings.INPUT_SAMPLE_RATE}",
                        data=audio_chunk,
                    )
                )
            else:
                await self.session.send_realtime_input(
                    audio=types.Blob(
                        mime_type=f"audio/pcm;rate={settings.INPUT_SAMPLE_RATE}",
                        data=audio_chunk,
                    )
                )

        except Exception as e:
            logger.error(
                "Failed to send audio to Gemini",
                error=str(e),
                exc_info=True,
            )
