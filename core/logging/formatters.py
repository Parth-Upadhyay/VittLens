"""
Log formatters for production JSON output (GCP Cloud Logging / Docker compatible)
and development human-readable text output.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Production-grade JSON formatter aligned with Google Cloud Logging format.

    Google Cloud Logging maps:
    - 'severity' to log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - 'time' or 'timestamp' to ISO 8601 UTC timestamp string
    - 'message' to the formatted log message
    - 'logging.googleapis.com/labels' or extra fields to contextual metadata
    """

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "caller": f"{record.filename}:{record.lineno}",
        }

        # Include exception info if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include extra context fields bound to the log record
        extra_context = {
            key: value
            for key, value in record.__dict__.items()
            if key
            not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }
        }

        if extra_context:
            log_payload["context"] = extra_context

        return json.dumps(log_payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Clean, readable log formatter for local CLI development."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).strftime("%H:%M:%S")
        message = record.getMessage()

        formatted = (
            f"[{timestamp}] {level_color}{record.levelname:<8}{self.RESET} "
            f"[{record.name}:{record.lineno}] {message}"
        )

        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted
