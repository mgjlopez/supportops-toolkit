"""
logger.py — Centralized structured JSON logging for SupportOps.

Every log line is a JSON object, which makes logs:
  - Parseable by log aggregators (Datadog, Splunk, ELK, CloudWatch)
  - Filterable by field (level, module, ticket_id, etc.)
  - Consistent across all services

Usage:
    from api.logger import get_logger
    log = get_logger(__name__)
    log.info("Ticket created", extra={"ticket_id": 42, "priority": "high"})

Output:
    {"timestamp": "2026-05-12T10:00:00Z", "level": "INFO",
     "module": "api.routers.tickets", "message": "Ticket created",
     "ticket_id": 42, "priority": "high"}
"""

import logging
import os
import sys
from pythonjsonlogger.json import JsonFormatter


def get_logger(name: str) -> logging.Logger:
    """Returns a JSON-formatted logger for the given module name."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured, avoid duplicate handlers

    level = logging.DEBUG if os.getenv("APP_ENV") == "development" else logging.INFO
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={
            "asctime":   "timestamp",
            "levelname": "level",
            "name":      "module",
            "message":   "message",
        },
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    return logger
