"""
Structured logging utilities using structlog.
Provides request ID tracking and consistent log formatting across the application.
"""

import inspect
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

import structlog

# Context variables for request tracking
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_session_id: ContextVar[Optional[str]] = ContextVar("session_id", default=None)


def add_request_context(logger, method_name, event_dict):
    """Add request ID and session ID to all log entries."""
    request_id = _request_id.get()
    session_id = _session_id.get()

    if request_id:
        event_dict["request_id"] = request_id
    if session_id:
        event_dict["session_id"] = session_id

    return event_dict


def add_caller_info(logger, method_name, event_dict):
    """Add filename and function name to log entries."""
    frame = inspect.currentframe()
    try:
        # Skip frames: this function -> structlog internals -> caller
        caller_frame = frame
        if caller_frame and caller_frame.f_back and caller_frame.f_back.f_back:
            caller_frame = caller_frame.f_back.f_back.f_back
            if caller_frame:
                filename = os.path.basename(caller_frame.f_code.co_filename)
                function_name = caller_frame.f_code.co_name
                event_dict["filename"] = filename
                event_dict["function"] = function_name
    finally:
        del frame

    return event_dict


def add_timestamp(logger, method_name, event_dict):
    """Add ISO timestamp to log entries."""
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def add_level(logger, method_name, event_dict):
    """Add log level to log entries."""
    event_dict["level"] = method_name.upper()
    return event_dict


# Configure structlog with all required processors
structlog.configure(
    processors=[
        # Custom processors for required fields
        add_request_context,
        add_caller_info,
        add_timestamp,
        add_level,
        # Built-in processors
        structlog.contextvars.merge_contextvars,
        structlog.dev.set_exc_info,
        structlog.processors.StackInfoRenderer(),
        # JSON output for production or console for development
        (
            structlog.processors.JSONRenderer()
            if os.getenv("ENVIRONMENT") == "production"
            else structlog.dev.ConsoleRenderer(
                colors=True, pad_event=25, sort_keys=True
            )
        ),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        int(os.getenv("LOG_LEVEL", logging.INFO))
    ),
    logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)


class RequestContextManager:
    """Manages request context for logging across async operations."""

    @staticmethod
    def set_request_id(request_id: Optional[str] = None) -> str:
        """Set request ID for the current context. Generate one if not provided."""
        if request_id is None:
            request_id = str(uuid.uuid4())
        _request_id.set(request_id)
        return request_id

    @staticmethod
    def set_session_id(session_id: str):
        """Set session ID for the current context."""
        _session_id.set(session_id)

    @staticmethod
    def get_request_id() -> Optional[str]:
        """Get current request ID."""
        return _request_id.get()

    @staticmethod
    def get_session_id() -> Optional[str]:
        """Get current session ID."""
        return _session_id.get()

    @staticmethod
    def clear_context():
        """Clear all context variables."""
        _request_id.set(None)
        _session_id.set(None)

    @staticmethod
    def bind_websocket_context(
        websocket_id: Optional[str] = None, session_id: Optional[str] = None
    ):
        """Bind context for a new websocket connection."""
        request_id = RequestContextManager.set_request_id(websocket_id)
        if session_id:
            RequestContextManager.set_session_id(session_id)
        return request_id


class StructuredLogger:
    """
    Wrapper around structlog logger to ensure consistent usage.
    """

    def __init__(self):
        self._logger = structlog.get_logger()

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self._logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._logger.critical(message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        self._logger.exception(message, **kwargs)


# Global logger instance - import this everywhere
logger = StructuredLogger()

# Global context manager - use for request tracking
request_context = RequestContextManager()


# Legacy compatibility functions for existing code
def bind_request_context(**kwargs):
    """Legacy function for compatibility with existing code."""
    structlog.contextvars.bind_contextvars(**kwargs)


class LogCapture:
    """
    Legacy compatibility class for captured logs.
    Now uses structured logging but maintains the same interface.
    """

    def __init__(self):
        self.captured_logs = []
        self._capturing = False

    def start_capture(self):
        """Start capturing logs (placeholder for compatibility)."""
        self._capturing = True
        logger.info("Log capture started")

    def stop_capture(self):
        """Stop capturing logs (placeholder for compatibility)."""
        self._capturing = False
        logger.info("Log capture stopped")

    def get_logs(self):
        """Get captured logs (returns empty list for compatibility)."""
        return []

    def clear_logs(self):
        """Clear captured logs (placeholder for compatibility)."""
        self.captured_logs.clear()


# Legacy compatibility instance
log_capture = LogCapture()
