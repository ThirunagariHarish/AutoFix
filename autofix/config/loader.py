"""YAML → Pydantic loader with user-friendly error messages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import ValidationError

from autofix.config.schema import AutoFixConfig


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ConfigFileNotFoundError(Exception):
    """Raised when the config file does not exist."""


class ConfigParseError(Exception):
    """Raised on YAML syntax errors."""


class ConfigValidationError(Exception):
    """Raised on Pydantic validation failures; stores list of error strings."""

    def __init__(self, message: str, errors: list[str]) -> None:
        super().__init__(message)
        self.errors = errors


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> AutoFixConfig:
    """Load, parse, and validate a projects.yaml file.

    Raises:
        ConfigFileNotFoundError: if the file doesn't exist.
        ConfigParseError: on YAML syntax errors.
        ConfigValidationError: on Pydantic validation failures.
    """
    path = Path(config_path)

    if not path.exists():
        raise ConfigFileNotFoundError(
            f"projects.yaml not found at {config_path}"
        )

    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigParseError(
            f"YAML parse error in {config_path}: {exc}"
        ) from exc

    try:
        return AutoFixConfig.model_validate(raw)
    except ValidationError as exc:
        errors = _format_errors(exc)
        message = "Config validation failed:\n" + "\n".join(f"  {e}" for e in errors)
        raise ConfigValidationError(message, errors) from exc


def _format_errors(exc: ValidationError) -> list[str]:
    """Turn Pydantic errors into human-readable strings."""
    lines: list[str] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        msg = error.get("msg", "")
        input_data = error.get("input", None)

        # Strip the "Value error, " prefix Pydantic v2 prepends to ValueError messages
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]

        prefix = _build_prefix(loc, input_data)
        lines.append(f"{prefix}{msg}")

    return lines


def _build_prefix(loc: tuple, input_data: Any = None) -> str:
    """Build a human-readable prefix from a Pydantic location tuple."""
    if not loc:
        return ""

    parts = list(loc)

    # Handle global_settings
    if parts and parts[0] in ("global_settings", "global"):
        rest = parts[1:]
        field = ".".join(str(p) for p in rest) if rest else ""
        return f"[global] {field}: " if field else "[global] "

    # Handle projects
    if parts and parts[0] == "projects":
        if len(parts) >= 2 and isinstance(parts[1], int):
            idx = parts[1]
            rest = parts[2:]
            field = ".".join(str(p) for p in rest) if rest else ""
            # Try to extract project name from the input dict (available on model-level errors)
            project_name: Optional[str] = None
            if isinstance(input_data, dict) and "name" in input_data:
                project_name = str(input_data["name"])
            label = f"project '{project_name}'" if project_name else f"project #{idx + 1}"
            return f"[{label}] {field}: " if field else f"[{label}] "
        return "[projects] "

    # Fallback
    field = ".".join(str(p) for p in parts)
    return f"[{field}] "
