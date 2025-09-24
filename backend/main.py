"""
Main application entry point for Gemini Live Travel Assistant Backend.

This is the refactored main module that uses modular components for
clean separation of concerns and maintainability.
"""

import signal
import sys

from app.core.app import create_app

app = create_app()


# Note: WebSocket connections handle request_id binding directly in WebSocketHandler


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

    print("🚀 Starting Gemini Live Travel Assistant Backend...")
    print("🌐 Server will be available at http://0.0.0.0:8000")
    print("📡 WebSocket endpoint: ws://0.0.0.0:8000/listen")

    try:
        import asyncio

        asyncio.run(hypercorn.asyncio.serve(app, config))
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)
