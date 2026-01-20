"""
Main application entry point for Gemini Live Travel Assistant Backend.

This is the refactored main module that uses modular components for
clean separation of concerns and maintainability. Now includes state
machine-based conversation handling.
"""

import os
import signal
import sys
import uuid

from app.core.app import create_app
from app.utils.logging import logger, request_context

app = create_app()


@app.before_request
def add_request_id():
    request_id = str(uuid.uuid4())
    request_context.set_request_id(request_id)


@app.after_request
def clear_request_context(response):
    request_context.clear_context()
    return response


def cleanup_on_exit():
    """Cleanup function called on application exit."""
    logger.info("Application shutting down gracefully")
    # Add any cleanup logic here if needed
    pass


def signal_handler(signum, frame):
    cleanup_on_exit()
    sys.exit(0)


def print_startup_info():
    """Print startup information including state machine status."""
    disable_state_machines = (
        os.getenv("DISABLE_STATE_MACHINES", "false").lower() == "true"
    )
    use_state_machines = not disable_state_machines

    print("🚀 Starting Gemini Live Travel Assistant Backend...")
    print("🌐 Server will be available at http://0.0.0.0:8000")
    print()
    print("📡 WebSocket Endpoints:")
    print(
        f"   • ws://0.0.0.0:8000/listen      (default - {'state machines' if use_state_machines else 'legacy'})"
    )
    print("   • ws://0.0.0.0:8000/listen/sm   (state machine explicit)")
    print("   • ws://0.0.0.0:8000/listen/legacy (legacy implementation)")
    print()
    print("🔧 API Endpoints:")
    print("   • GET  /api/status                (system status)")
    print("   • GET  /api/config/state-machines (state machine config)")
    print("   • GET  /api/config/endpoints      (endpoint info)")
    print("   • GET  /api/logs                  (get logs)")
    print("   • POST /api/logs/clear            (clear logs)")
    print("   • GET  /ping                      (health check)")
    print()
    print(f"🤖 State Machines: {'✅ ENABLED' if use_state_machines else '❌ DISABLED'}")
    if use_state_machines:
        print("   • Intelligent tool coordination")
        print("   • Sequential result delivery")
        print("   • User confirmation for multiple results")
        print("   • Speech gap detection")
        print("   • Non-blocking tool execution")
    else:
        print("   • Using legacy handlers (set DISABLE_STATE_MACHINES=false to enable)")
    print()


signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

if __name__ == "__main__":
    # This is mainly for development. In production, use hypercorn or another ASGI server
    import hypercorn.asyncio
    import hypercorn.config

    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:8000"]
    config.reload = True

    print_startup_info()

    try:
        hypercorn.asyncio.serve(app, config)
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
        cleanup_on_exit()
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        cleanup_on_exit()
        sys.exit(1)
