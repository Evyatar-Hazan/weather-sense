"""
Logging configuration for structured JSON logging.
"""
import json
import logging
import sys
import uuid
from typing import Any, Dict


class StructuredJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Add structured fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        if hasattr(record, "task"):
            log_entry["task"] = record.task

        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        if hasattr(record, "status"):
            log_entry["status"] = record.status

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_level: str = "INFO") -> None:
    """Setup structured logging configuration."""
    # Create formatter
    formatter = StructuredJSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler with structured formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)


def get_logger_with_context(
    name: str, request_id: str = None, task: str = None
) -> logging.Logger:
    """Get logger with contextual information."""
    logger = logging.getLogger(name)

    # Create a custom logger adapter
    if request_id or task:
        extra_context = {}
        if request_id:
            extra_context["request_id"] = request_id
        if task:
            extra_context["task"] = task

        return logging.LoggerAdapter(logger, extra_context)

    return logger


def log_request(
    logger: logging.Logger,
    request_id: str,
    task: str,
    duration_ms: int,
    status: str,
    message: str = "",
) -> None:
    """Log a request with structured fields."""
    logger.info(
        message,
        extra={
            "request_id": request_id,
            "task": task,
            "duration_ms": duration_ms,
            "status": status,
        },
    )
