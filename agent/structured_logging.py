"""Structured logging formatter with JSON output and context fields.

Provides a JSON formatter that integrates with the standard logging module,
adding fields like session_id, request_id, and timestamp.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class StructuredFormatter(logging.Formatter):
    """JSON-formatted log records for structured logging.

    Outputs each log record as a single-line JSON object with:
    - timestamp (ISO 8601)
    - level
    - logger name
    - message
    - any extra fields passed via logger.info("msg", extra={...})

    Example::

        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logging.getLogger().addHandler(handler)
        logging.getLogger().info("Started", extra={"session_id": "abc123"})
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields (anything not in standard LogRecord attributes)
        standard = set(dir(logging.LogRecord(
            name="", level=0, pathname="", lineno=0,
            msg="", args=(), exc_info=None,
        )))
        for key, value in record.__dict__.items():
            if key not in standard and not key.startswith("_"):
                log_entry[key] = value

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class ColorFormatter(logging.Formatter):
    """Color-coded log formatter for terminal output.

    Colors by level: DEBUG=gray, INFO=default, WARNING=yellow,
    ERROR=red, CRITICAL=red+bold.
    """

    COLORS = {
        logging.DEBUG: "\033[37m",     # gray
        logging.INFO: "\033[0m",       # default
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        record.msg = f"{color}{record.msg}{self.RESET}"
        return super().format(record)


def setup_structured_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: str | None = None,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, output JSON-formatted logs.
        log_file: Optional file path for log output.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    if json_output:
        console.setFormatter(StructuredFormatter())
    else:
        console.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    root.addHandler(console)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(StructuredFormatter())
        root.addHandler(file_handler)
