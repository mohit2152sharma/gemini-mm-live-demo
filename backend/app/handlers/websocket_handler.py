"""
WebSocket connection handler for Gemini Live API integration.
"""

import asyncio
import json
import traceback
import uuid
from datetime import datetime
from typing import Any, Callable, Dict

from pydantic import BaseModel
from quart import websocket

from app.core.config import settings
from app.services.gemini_client import gemini_manager
from app.tools import AllTools, create_available_functions
from app.utils.audio import AudioBuffer
from app.utils.logging import logger, request_context


class SessionState(BaseModel):
    user_id: str
    session_id: str
    connection_start_time: datetime
    processed_tool_calls: dict[str, str]
    pending_tool_calls: dict[str, str]
    total_tool_calls: int


class WebSocketHandler:
    """Handles WebSocket connections and Gemini Live API integration."""

    def __init__(self, use_state_machines: bool = True):
        self.available_functions: Dict[str, Callable] = {}
        self.discovered_tool_names = AllTools.list_valid_tool_names()
        self.use_state_machines = use_state_machines

        logger.info(
            "Initialized WebSocketHandler tool catalog",
            tool_count=len(self.discovered_tool_names),
            tools=self.discovered_tool_names,
            use_state_machines=use_state_machines,
        )

    async def handle_connection(self):
        """Main WebSocket connection handler."""
        connection_start_time = asyncio.get_event_loop().time()

        # Generate unique request ID for this WebSocket connection
        connection_id = str(uuid.uuid4())
        request_context.bind_websocket_context(websocket_id=connection_id)

        logger.info("New WebSocket connection accepted", connection_id=connection_id)

        # Initialize connection state and a queue for graceful tool result delivery
        session_state = self._initialize_session_state(
            connection_start_time, connection_id
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

                if not self.available_functions:
                    if not self.discovered_tool_names:
                        self.discovered_tool_names = AllTools.list_valid_tool_names()
                    self.available_functions = create_available_functions(
                        session, tool_results_queue
                    )
                    logger.info(
                        "Bound tool implementations for session",
                        tool_count=len(self.available_functions),
                        tools=list(self.available_functions.keys()),
                    )

                # Create handlers based on configuration
                if self.use_state_machines:
                    logger.info("Using NEW state machine-based handlers")

                    # Import new state machine components
                    from app.handlers.sm_client_handler import StateMachineClientHandler
                    from app.handlers.sm_response_handler import (
                        StateMachineResponseHandler,
                    )
                    from app.handlers.state_machine_handler import (
                        StateMachineCoordinator,
                    )
                    from app.state.conversation_state import ConversationStateMachine
                    from app.state.tool_executor import ToolExecutor
                    from app.state.tool_state import ToolStateMachine

                    # Create state machines
                    conversation_state = ConversationStateMachine()
                    tool_state = ToolStateMachine()

                    # Create tool executor
                    tool_executor = ToolExecutor(
                        session,
                        tool_state,
                        self.available_functions,
                        tool_results_queue,
                    )

                    # Create coordinator
                    coordinator = StateMachineCoordinator(
                        session,
                        conversation_state,
                        tool_state,
                        tool_executor,
                    )

                    # Create handlers
                    client_handler = StateMachineClientHandler(
                        session,
                        session_state,
                        coordinator,
                    )

                    gemini_handler = StateMachineResponseHandler(
                        session,
                        session_state,
                        coordinator,
                    )

                    logger.info(
                        "State machines initialized",
                        conversation_state="IDLE",
                        tool_state="IDLE",
                    )

                else:
                    logger.warning(
                        "Legacy handlers not available - using state machines",
                        reason="legacy_handlers_removed",
                    )

                    # Import state machine components (fallback to state machines)
                    from app.handlers.sm_client_handler import StateMachineClientHandler
                    from app.handlers.sm_response_handler import (
                        StateMachineResponseHandler,
                    )
                    from app.handlers.state_machine_handler import (
                        StateMachineCoordinator,
                    )
                    from app.state.conversation_state import ConversationStateMachine
                    from app.state.tool_executor import ToolExecutor
                    from app.state.tool_state import ToolStateMachine

                    # Create state machines
                    conversation_state = ConversationStateMachine()
                    tool_state = ToolStateMachine()

                    # Create tool executor
                    tool_executor = ToolExecutor(
                        session,
                        tool_state,
                        self.available_functions,
                        tool_results_queue,
                    )

                    # Create coordinator
                    coordinator = StateMachineCoordinator(
                        session,
                        conversation_state,
                        tool_state,
                        tool_executor,
                    )

                    # Create handlers
                    client_handler = StateMachineClientHandler(
                        session,
                        session_state,
                        coordinator,
                    )

                    gemini_handler = StateMachineResponseHandler(
                        session,
                        session_state,
                        coordinator,
                    )

                    logger.info(
                        "Fallback: Using state machine handlers",
                        conversation_state="IDLE",
                        tool_state="IDLE",
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
            request_context.clear_context()

    def _initialize_session_state(
        self, connection_start_time: float, connection_id: str
    ) -> Dict[str, Any]:
        """Initialize session state for the connection."""
        return {
            "connection_start_time": connection_start_time,
            "connection_id": connection_id,
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
