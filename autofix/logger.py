"""Orchestrator structured logging — writes to autofix.log (JSON, file only).

Terminal output is handled separately by ANSI print() calls in each module.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON using the event's creation time."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": "orchestrator",
            "event": record.getMessage(),
            "detail": record.exc_text or "",
        })


def setup_logger(log_level: str = "INFO", log_dir: str = "./logs") -> logging.Logger:
    """Create and configure the global 'autofix' logger (file handler only)."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("autofix")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()

    formatter = _JsonFormatter()

    # File handler only — terminal output comes from explicit print() calls
    file_handler = logging.FileHandler(Path(log_dir) / "autofix.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """Return the global 'autofix' logger, initialising with defaults if needed."""
    logger = logging.getLogger("autofix")
    if not logger.handlers:
        setup_logger()
    return logger
