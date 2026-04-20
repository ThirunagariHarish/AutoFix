# AutoFix Standard Logging — Python (structlog)
# ================================================
# Add to requirements.txt:
#   structlog>=23.0.0
#
# Place this module at: app/logging_config.py  (or logging_config.py)
# Then call configure_logging() from your entry point (main.py, app.py,
# wsgi.py, asgi.py) BEFORE importing any application module.
#
# Usage:
#   import structlog
#   logger = structlog.get_logger(__name__)
#   logger.info("server_started", port=8080, service="my-api")
#   logger.error("db_connection_failed", error=str(e), host=db_host)
#
# IMPORTANT FOR AUTOFIX MONITORING:
# structlog uses "event" as the primary message key (NOT "message").
# The canonical log schema maps: event → message field.
# AutoFix checks line["event"] ?? line["message"] ?? line["msg"] when extracting
# the human-readable description from a structlog JSON line.
#
# The produced JSON schema matches AutoFix canonical format:
#   {"timestamp": "...", "level": "error", "logger": "module.path",
#    "event": "message text", ...extra context fields...}

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog


def configure_logging(log_file: str = "logs/app.log", level: str = "INFO") -> None:
    """Configure structlog for JSON output to both file and stdout.

    Args:
        log_file: Path (relative to project root) where log lines are written.
        level:    Minimum log level string, e.g. "INFO", "DEBUG", "WARNING".
    """
    # Ensure the logs directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors applied to every log record
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    # Rotating file handler — 50 MB per file, keep 7 files
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=50 * 1024 * 1024,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Console handler — same JSON format (Docker reads stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Example entry-point wiring (add to main.py / app.py):
# ---------------------------------------------------------------------------
#
#   from app.logging_config import configure_logging
#   configure_logging(log_file="logs/app.log", level="INFO")
#
#   import structlog
#   logger = structlog.get_logger(__name__)
#
#   # Informational event
#   logger.info("application_started", version="1.0.0", env="production")
#
#   # Error with exception context
#   try:
#       connect_db()
#   except Exception as exc:
#       logger.error("database_connection_failed", error=str(exc), host=DB_HOST)
#
#   # Critical with full exception info
#   try:
#       risky_operation()
#   except Exception:
#       logger.critical("fatal_startup_error", exc_info=True)
