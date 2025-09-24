"""
WebSocket connection handler for Gemini Live API integration.
"""

import asyncio
import json
import traceback
import uuid
from typing import Any, Dict

import structlog
from quart import websocket

from app.core.config import settings
from app.handlers.client_input_handler import ClientInputHandler
from app.handlers.gemini_response_handler import GeminiResponseHandler
from app.services.gemini_client import gemini_manager
from app.tools import (
    Booking_Cancellation_Agent,
    Connect_To_Human_Tool,
    DateChangeAgent,
    Enquiry_Tool,
    Eticket_Sender_Agent,
    Flight_Booking_Details_Agent,
    NameCorrectionAgent,
    ObservabilityAgent,
    SpecialClaimAgent,
    Webcheckin_And_Boarding_Pass_Agent,
    take_a_nap,
)
from app.utils.audio import AudioBuffer
from utils._logger import bind_request_context, logger


class WebSocketHandler:
    """Handles WebSocket connections and Gemini Live API integration."""

    def __init__(self):
        self.available_functions = {
            "take_a_nap": take_a_nap,
            "NameCorrectionAgent": NameCorrectionAgent,
            "SpecialClaimAgent": SpecialClaimAgent,
            "Enquiry_Tool": Enquiry_Tool,
            "Eticket_Sender_Agent": Eticket_Sender_Agent,
            "ObservabilityAgent": ObservabilityAgent,
            "DateChangeAgent": DateChangeAgent,
            "Connect_To_Human_Tool": Connect_To_Human_Tool,
            "Booking_Cancellation_Agent": Booking_Cancellation_Agent,
            "Flight_Booking_Details_Agent": Flight_Booking_Details_Agent,
            "Webcheckin_And_Boarding_Pass_Agent": Webcheckin_And_Boarding_Pass_Agent,
        }

    async def handle_connection(self):
        """Main WebSocket connection handler."""
        connection_start_time = asyncio.get_event_loop().time()

        # Generate unique request ID for this WebSocket connection
        request_id = str(uuid.uuid4())
        bind_request_context(request_id=request_id, connection_type="websocket")
        # logger.bind(request_id=request_id, connection_type="websocket")

        logger.info("New WebSocket connection accepted", connection_id=request_id)

        # Initialize connection state and a queue for graceful tool result delivery
        session_state = self._initialize_session_state(
            connection_start_time, request_id
        )
        tool_results_queue = asyncio.Queue()

        try:
            async with self._create_gemini_session() as session:
                logger.info("Successfully connected to Gemini Live API")

                # Inform the client that the backend is ready
                await websocket.send(
                    json.dumps({"type": "control", "signal": "server_ready"})
                )
                logger.info("Sent 'server_ready' signal to client")

                # Create handlers, passing the queue to the response handler
                client_handler = ClientInputHandler(session, session_state)
                gemini_handler = GeminiResponseHandler(
                    session, session_state, self.available_functions, tool_results_queue
                )

                # Create and run tasks
                forward_task = asyncio.create_task(
                    client_handler.handle_client_input(), name="ClientInputForwarder"
                )
                receive_task = asyncio.create_task(
                    gemini_handler.handle_gemini_responses(), name="GeminiReceiver"
                )

                try:
                    await asyncio.gather(forward_task, receive_task)
                except Exception as e_gather:
                    logger.error(
                        "Exception during task gather",
                        error_type=type(e_gather).__name__,
                        error=str(e_gather),
                    )
                    traceback.print_exc()
                finally:
                    await self._cleanup_tasks(forward_task, receive_task, session_state)

        except asyncio.CancelledError:
            logger.warning("WebSocket connection cancelled (client disconnected)")
        except TimeoutError as e_timeout:
            logger.error("Timeout connecting to Gemini Live API", error=str(e_timeout))
            self._print_timeout_debug_info()
            traceback.print_exc()
        except Exception as e_ws_main:
            logger.error(
                "UNHANDLED error in WebSocket connection",
                error_type=type(e_ws_main).__name__,
                error=str(e_ws_main),
            )
            traceback.print_exc()
        finally:
            logger.info("WebSocket endpoint processing finished")
            # Clear context when connection ends
            structlog.contextvars.clear_contextvars()

    def _initialize_session_state(
        self, connection_start_time: float, request_id: str
    ) -> Dict[str, Any]:
        """Initialize session state for the connection."""
        return {
            "connection_start_time": connection_start_time,
            "request_id": request_id,
            "current_session_handle": None,
            "client_ready_for_audio": False,
            "mic_audio_buffer": AudioBuffer(),
            "gemini_audio_buffer": AudioBuffer(),
            "audio_sequence_counter": 0,
            "active_processing": True,
            "current_user_utterance_id": None,
            "accumulated_user_speech_text": "",
            "current_model_utterance_id": None,
            "accumulated_model_speech_text": "",
        }

    def _create_gemini_session(self):
        """Create and return Gemini Live API session."""
        client = gemini_manager.initialize_client()
        config = gemini_manager.get_live_config()

        logger.info(
            "Attempting to connect to Gemini Live API", model=settings.GEMINI_MODEL_NAME
        )
        logger.info("Travel tool configured with functions")

        return client.aio.live.connect(model=settings.GEMINI_MODEL_NAME, config=config)

    async def _cleanup_tasks(self, forward_task, receive_task, session_state):
        """Clean up asyncio tasks."""
        session_state["active_processing"] = False

        # Cancel tasks if not done
        if not forward_task.done():
            forward_task.cancel()
        if not receive_task.done():
            receive_task.cancel()

        # Wait for task cleanup
        for task, task_name in [
            (forward_task, "forward_task"),
            (receive_task, "receive_task"),
        ]:
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected during cleanup
            except Exception as e_cleanup:
                logger.error(
                    "Error during task cleanup",
                    task_name=task_name,
                    error=str(e_cleanup),
                )
                traceback.print_exc()

    def _print_timeout_debug_info(self):
        """Print debug information for timeout errors."""
        logger.error("Timeout debug info - This could be due to:")
        logger.error("   - Network connectivity issues")
        logger.error("   - API key problems")
        logger.error("   - Google service unavailability")
        logger.error("   - Firewall blocking WebSocket connections")
