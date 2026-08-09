"""
Central logger factory and context manager for structured logging.
"""

import contextvars
import logging
import sys
from typing import Any, Dict, Generator, Optional
from contextlib import contextmanager

from core.config import settings
from core.logging.formatters import ConsoleFormatter, JSONFormatter

# Thread & async task-safe context propagation
_LOG_CONTEXT: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "log_context", default={}
)


class ContextAdapter(logging.LoggerAdapter):
    """LoggerAdapter that automatically merges thread/task-local context into log output."""

    def process(
        self, msg: str, kwargs: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        current_context = _LOG_CONTEXT.get()
        if current_context:
            extra = kwargs.get("extra", {})
            extra.update(current_context)
            kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> logging.LoggerAdapter:
    """
    Get a structured logger instance for a given module or class name.

    Args:
        name: Logger identifier (typically __name__)

    Returns:
        logging.LoggerAdapter: Configured logger adapter
    """
    base_logger = logging.getLogger(name)

    # Avoid duplicate handler additions if already configured
    if not base_logger.handlers:
        base_logger.setLevel(settings.logging.level.value)
        handler = logging.StreamHandler(sys.stdout)

        if settings.app.is_production or settings.logging.format == "json":
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(ConsoleFormatter())

        base_logger.addHandler(handler)
        base_logger.propagate = False

    return ContextAdapter(base_logger, {})


@contextmanager
def LogContext(**kwargs: Any) -> Generator[None, None, None]:
    """
    Context manager to bind key-value context to all logs emitted within a block.

    Example:
        with LogContext(ticker="RELIANCE", trace_id="12345"):
            logger.info("Processing financial report")
    """
    token = _LOG_CONTEXT.set({**_LOG_CONTEXT.get(), **kwargs})
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)
