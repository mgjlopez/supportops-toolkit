"""
logger.py — Structured JSON logging for SupportOps.

In production environments logs are ingested by tools like Datadog,
Splunk, or ELK Stack. JSON format makes them parseable and searchable.

Usage:
    from api.logger import get_logger
    log = get_logger(__name__)
    log.info("Ticket created", extra={"ticket_id": 42, "priority": "high"})
"""

import logging
import os
import sys

APP_ENV   = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class JsonFormatter(logging.Formatter):
    """
    Minimal JSON formatter with no external dependencies.
    Outputs one JSON object per line — compatible with Datadog, Splunk, and ELK.
    """
    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, UTC

        payload = {
            "timestamp":   datetime.now(UTC).isoformat(),
            "level":       record.levelname,
            "service":     "supportops-api",
            "environment": APP_ENV,
            "logger":      record.name,
            "msg":         record.getMessage(),
        }

        # Merge any extra fields passed via log.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in (
                "args", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "message",
                "module", "msecs", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "thread",
                "threadName", "taskName",
            ):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    """Returns a logger that outputs structured JSON to stdout."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured — avoid duplicate handlers

    logger.setLevel(LOG_LEVEL)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(LOG_LEVEL)
    handler.setFormatter(JsonFormatter())

    logger.addHandler(handler)
    logger.propagate = False

    return logger
