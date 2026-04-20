"""Pydantic v2 models for projects.yaml schema."""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator
from pydantic import ConfigDict


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class GlobalSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tmux_session_name: str = "autofix"
    watchdog_interval_seconds: int = 60
    claude_command: str = "claude --dangerously-skip-permissions"
    git_author_name: str = "AutoFix Agent"
    git_author_email: str = "autofix@local"
    log_dir: str = "./logs"

    @field_validator("watchdog_interval_seconds")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("watchdog_interval_seconds must be > 0")
        return v


class VPSConfig(BaseModel):
    host: str
    user: str
    ssh_key_path: str
    verify_command: str
    verify_output_contains: Optional[str] = None
    verify_timeout_seconds: int = 30
    enabled: bool = True
    docker_container_name: Optional[str] = None
    docker_compose_path: Optional[str] = None
    log_stream_command: Optional[str] = None  # e.g. "docker logs -f my-api-app"

    @field_validator("verify_timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("verify_timeout_seconds must be > 0")
        return v

    @field_validator("ssh_key_path")
    @classmethod
    def validate_ssh_key(cls, v: str) -> str:
        resolved = Path(v).expanduser()
        if not resolved.exists():
            raise ValueError(f"SSH key not found: {resolved}")
        return str(resolved)


class GitConfig(BaseModel):
    push_branch: Optional[str] = None
    pull_before_fix: bool = True
    commit_sign: bool = False


class MonitoringConfig(BaseModel):
    error_debounce_minutes: int = 5
    max_fixes_per_hour: int = 3
    blocked_patterns: list[str] = []

    @field_validator("error_debounce_minutes")
    @classmethod
    def validate_debounce(cls, v: int) -> int:
        if v < 1:
            raise ValueError("error_debounce_minutes must be >= 1")
        return v

    @field_validator("max_fixes_per_hour")
    @classmethod
    def validate_max_fixes(cls, v: int) -> int:
        if not (1 <= v <= 20):
            raise ValueError("max_fixes_per_hour must be between 1 and 20")
        return v


class NotificationsConfig(BaseModel):
    webhook_url: Optional[str] = None
    on_events: list[str] = []

    @field_validator("on_events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        valid = {
            "fix_applied",
            "fix_failed",
            "verification_failed",
            # Phase 3 watchdog events
            "crash_loop_detected",
            "pane_respawned",
        }
        for event in v:
            if event not in valid:
                raise ValueError(
                    f"Invalid event '{event}'. Valid values: {', '.join(sorted(valid))}"
                )
        return v


_VALID_LANGUAGES = {"python", "nodejs", "ruby", "go", "auto"}
_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class ProjectConfig(BaseModel):
    name: str
    repo_url: str
    local_path: str
    branch: str = "main"
    language: str = "auto"
    log_path: str = "logs/app.log"
    vps: VPSConfig
    git: GitConfig = GitConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    notifications: Optional[NotificationsConfig] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_PATTERN.match(v):
            raise ValueError(
                f"Project name '{v}' is invalid. Must match pattern [a-zA-Z0-9_-]+"
            )
        return v

    @field_validator("local_path")
    @classmethod
    def validate_local_path(cls, v: str) -> str:
        # Expand ~ first
        expanded = str(Path(v).expanduser())
        if not expanded.startswith("/"):
            raise ValueError(f"local_path must be an absolute path: '{v}'")
        return expanded

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in _VALID_LANGUAGES:
            raise ValueError(
                f"Unsupported language '{v}'. Must be one of: python, nodejs, ruby, go, auto"
            )
        return v


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------

class AutoFixConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str
    global_settings: GlobalSettings = GlobalSettings()
    projects: list[ProjectConfig]

    @model_validator(mode="before")
    @classmethod
    def remap_global_key(cls, data: Any) -> Any:
        """Allow 'global' as key in YAML (Python keyword workaround)."""
        if isinstance(data, dict) and "global" in data and "global_settings" not in data:
            data = dict(data)
            data["global_settings"] = data.pop("global")
        return data

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        """Validate schema_version is present; warn if unrecognized."""
        if not v:
            raise ValueError("schema_version is required")
        if v != "1.0":
            warnings.warn(
                f"schema_version '{v}' is unrecognized. Expected '1.0'.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("projects")
    @classmethod
    def validate_projects(cls, v: list[ProjectConfig]) -> list[ProjectConfig]:
        if len(v) < 1:
            raise ValueError("At least one project is required")
        if len(v) > 10:
            raise ValueError(
                f"Too many projects: {len(v)}. Maximum supported in v1 is 10."
            )
        names = [p.name for p in v]
        seen: set[str] = set()
        for name in names:
            if name in seen:
                raise ValueError(f"Duplicate project name: {name}")
            seen.add(name)
        return v
