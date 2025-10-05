"""
Main application entry point for Gemini Live Travel Assistant Backend.

This is the refactored main module that uses modular components for
clean separation of concerns and maintainability.
"""

import signal
import sys
import uuid

import structlog

from app.core.app import create_app
from utils._logger import bind_request_context

app = create_app()


@app.before_request
def add_request_id():
    request_id = str(uuid.uuid4())
    bind_request_context(request_id=request_id)


@app.after_request
def clear_request_context(response):
    structlog.contextvars.clear_contextvars()
    return response


def signal_handler(signum, frame):
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

if __name__ == "__main__":
    # This is mainly for development. In production, use hypercorn or another ASGI server
    import hypercorn.asyncio
    import hypercorn.config

    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:8000"]
    config.reload = True

    print("🚀 Starting Gemini Live Travel Assistant Backend...")
    print("🌐 Server will be available at http://0.0.0.0:8000")
    print("📡 WebSocket endpoint: ws://0.0.0.0:8000/listen")

    try:
        hypercorn.asyncio.serve(app, config)
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
        cleanup_on_exit()
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        cleanup_on_exit()
        sys.exit(1)
