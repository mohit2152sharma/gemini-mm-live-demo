"""
WebSocket route definitions with state machine integration.
"""

import os

from quart import Blueprint

from app.handlers.websocket_handler import WebSocketHandler
from app.utils.logging import logger

websocket_bp = Blueprint("websocket", __name__)


@websocket_bp.websocket("/listen")
async def websocket_endpoint():
    """
    WebSocket endpoint for Gemini Live API communication.

    Uses state machine-based conversation handling by default.
    Set DISABLE_STATE_MACHINES=true environment variable to use legacy handlers.
    """
    # Check environment variable for override
    disable_state_machines = (
        os.getenv("DISABLE_STATE_MACHINES", "false").lower() == "true"
    )
    use_state_machines = not disable_state_machines

    logger.info(
        "WebSocket connection starting",
        use_state_machines=use_state_machines,
        handler_type="state_machine" if use_state_machines else "legacy",
    )

    handler = WebSocketHandler(use_state_machines=use_state_machines)
    await handler.handle_connection()


@websocket_bp.websocket("/listen/legacy")
async def websocket_legacy_endpoint():
    """
    Legacy WebSocket endpoint - redirects to state machine implementation.

    Legacy handlers have been removed. This endpoint now uses state machines
    for consistent behavior across all connections.
    """
    logger.info("Legacy endpoint requested - using state machine handlers")

    handler = WebSocketHandler(use_state_machines=True)
    await handler.handle_connection()


@websocket_bp.websocket("/listen/sm")
async def websocket_state_machine_endpoint():
    """
    State machine WebSocket endpoint.

    This endpoint explicitly uses the new state machine implementation.
    Useful for testing or when you want to ensure state machines are used.
    """
    logger.info("WebSocket connection starting with state machine handlers")

    handler = WebSocketHandler(use_state_machines=True)
    await handler.handle_connection()
