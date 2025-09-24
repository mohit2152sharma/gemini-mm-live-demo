import logging
import sys

import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="ISO", utc=True),
        structlog.dev.set_exc_info,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer(colors=True, pad_event=25, sort_keys=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),  # INFO level
    logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)

# Create logger instance for easy import
logger = structlog.get_logger()


def bind_request_context(**kwargs):
    """Bind context variables that will be available to all loggers"""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**kwargs)
