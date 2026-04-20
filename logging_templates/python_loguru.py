# AutoFix Standard Logging — Python (loguru)
# ============================================
# Add to requirements.txt:
#   loguru>=0.7.0
#
# Place this module at: app/logging_config.py  (or logging_config.py)
# Then call configure_logging() from your entry point (main.py, app.py,
# wsgi.py, asgi.py) BEFORE importing any application module.
#
# Usage:
#   from loguru import logger
#   logger.info("server_started", port=8080)
#   logger.error("db_connection_failed: {host}", host=db_host)
#   logger.exception("unhandled_exception")  # automatically captures exc_info
#
# IMPORTANT FOR AUTOFIX MONITORING:
# loguru's serialize=True produces nested JSON:
#   {"text": "...", "record": {"level": {"name": "ERROR"}, "time": {...}, ...}}
# The AutoFix monitoring loop handles this via alias: it checks both
#   "level" (top-level, structlog/winston/zap format) AND
#   "record.level.name" (loguru nested format).
# AutoFix searches for '"level":{"name":"error"}' or '"level":"error"' patterns.

import sys
from pathlib import Path

from loguru import logger


def configure_logging(log_file: str = "logs/app.log", level: str = "INFO") -> None:
    """Configure loguru for JSON output to both file and stdout.

    Args:
        log_file: Path (relative to project root) where log lines are written.
        level:    Minimum log level string, e.g. "INFO", "DEBUG", "WARNING".
    """
    # Ensure the logs directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Remove the default stderr handler
    logger.remove()

    # JSON file handler — 50 MB per file, keep 7 files, serialize=True → JSON output
    logger.add(
        log_file,
        level=level.upper(),
        serialize=True,                 # Outputs structured JSON lines
        rotation="50 MB",
        retention=7,
        encoding="utf-8",
        backtrace=True,                 # Include full stack trace in exceptions
        diagnose=True,                  # Show variable values in tracebacks
    )

    # JSON stdout handler (Docker reads stdout for `docker logs -f`)
    logger.add(
        sys.stdout,
        level=level.upper(),
        serialize=True,
        backtrace=True,
        diagnose=False,                 # Disable in stdout to avoid leaking locals
    )

    # Optional: capture stdlib logging (e.g. from third-party libraries)
    import logging

    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
            try:
                lvl = logger.level(record.levelname).name
            except ValueError:
                lvl = record.levelno  # type: ignore[assignment]
            frame, depth = sys._getframe(6), 6
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back  # type: ignore[assignment]
                depth += 1
            logger.opt(depth=depth, exception=record.exc_info).log(
                lvl, record.getMessage()
            )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


# ---------------------------------------------------------------------------
# Example entry-point wiring (add to main.py / app.py):
# ---------------------------------------------------------------------------
#
#   from app.logging_config import configure_logging
#   configure_logging(log_file="logs/app.log", level="INFO")
#
#   from loguru import logger
#
#   # Informational event
#   logger.info("Application started | version={version}", version="1.0.0")
#
#   # Error with context (keyword args become extra JSON fields)
#   try:
#       connect_db()
#   except Exception as exc:
#       logger.error("Database connection failed | host={host}", host=DB_HOST)
#
#   # Exception with auto-captured traceback
#   try:
#       risky_operation()
#   except Exception:
#       logger.exception("Unhandled exception in risky_operation")
