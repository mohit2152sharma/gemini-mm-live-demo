"""
API route definitions with state machine integration.
"""

import os
from datetime import datetime, timezone

from quart import Blueprint, jsonify

from app.data.travel_mock_data import GLOBAL_LOG_STORE, clear_global_log_store
from app.utils.logging import log_capture

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/logs", methods=["GET"])
async def get_logs():
    """API endpoint to fetch captured logs."""
    # Combine logs from global store and captured stdout logs
    captured_logs = log_capture.get_logs()
    combined_logs = list(GLOBAL_LOG_STORE) + captured_logs

    return jsonify(combined_logs)


@api_bp.route("/api/logs/clear", methods=["POST"])
async def clear_logs():
    """API endpoint to clear all logs."""
    try:
        clear_global_log_store()
        log_capture.clear_logs()  # Also clear captured logs
        return jsonify(
            {
                "status": "success",
                "message": "All logs cleared successfully",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Failed to clear logs: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )


@api_bp.route("/api/status", methods=["GET"])
async def get_status():
    """Get current system status including state machine configuration."""
    disable_state_machines = (
        os.getenv("DISABLE_STATE_MACHINES", "false").lower() == "true"
    )
    use_state_machines = not disable_state_machines

    return jsonify(
        {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "configuration": {
                "state_machines_enabled": use_state_machines,
                "handler_type": "state_machine" if use_state_machines else "legacy",
                "environment_override": os.getenv("DISABLE_STATE_MACHINES", "not_set"),
            },
            "endpoints": {
                "default": "/listen (uses state machines by default)",
                "state_machine": "/listen/sm (explicit state machine)",
                "legacy": "/listen/legacy (original implementation)",
            },
            "version": "2.0.0-state-machine",
        }
    )


@api_bp.route("/api/config/state-machines", methods=["GET"])
async def get_state_machine_config():
    """Get state machine configuration details."""
    disable_state_machines = (
        os.getenv("DISABLE_STATE_MACHINES", "false").lower() == "true"
    )
    use_state_machines = not disable_state_machines

    return jsonify(
        {
            "state_machines": {
                "enabled": use_state_machines,
                "conversation_states": [
                    "IDLE",
                    "USER_SPEAKING",
                    "BOT_SPEAKING",
                    "WAITING_FOR_USER",
                ],
                "tool_states": [
                    "IDLE",
                    "PENDING",
                    "EXECUTING",
                    "COMPLETED",
                    "DELIVERING",
                    "FAILED",
                ],
                "features": {
                    "intelligent_tool_coordination": True,
                    "sequential_result_delivery": True,
                    "user_confirmation_for_multiple_results": True,
                    "speech_gap_detection": True,
                    "non_blocking_tool_execution": True,
                    "state_transition_validation": True,
                },
                "configuration": {
                    "speech_gap_threshold_seconds": 1.5,
                    "delivery_check_interval_seconds": 0.5,
                    "multiple_result_confirmation": True,
                },
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@api_bp.route("/api/config/endpoints", methods=["GET"])
async def get_endpoint_info():
    """Get information about WebSocket endpoints."""
    return jsonify(
        {
            "websocket_endpoints": {
                "/listen": {
                    "description": "Main WebSocket endpoint",
                    "default_behavior": "Uses state machines (configurable via DISABLE_STATE_MACHINES env var)",
                    "state_machines": "enabled_by_default",
                    "recommended": True,
                },
                "/listen/sm": {
                    "description": "Explicit state machine endpoint",
                    "default_behavior": "Always uses state machine implementation",
                    "state_machines": "always_enabled",
                    "recommended": "for_testing",
                },
                "/listen/legacy": {
                    "description": "Legacy endpoint (redirects to state machines)",
                    "default_behavior": "Uses state machine implementation (legacy handlers removed)",
                    "state_machines": "enabled",
                    "recommended": "deprecated",
                },
            },
            "configuration": {
                "current_default": (
                    "state_machine"
                    if not os.getenv("DISABLE_STATE_MACHINES", "false").lower()
                    == "true"
                    else "legacy"
                ),
                "environment_variable": "DISABLE_STATE_MACHINES",
                "override_instructions": "Set DISABLE_STATE_MACHINES=true to use legacy handlers by default",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@api_bp.route("/ping", methods=["GET", "HEAD"])
async def ping():
    """Simple ping endpoint for connection quality testing."""
    return jsonify(
        {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
    )
