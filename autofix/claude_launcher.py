"""Claude launcher — full Phase 2 implementation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from autofix.config.schema import GlobalSettings, ProjectConfig
from autofix.language_detector import detect_language
from autofix.logger import get_logger

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_LOGGING_TEMPLATES_DIR = Path(__file__).parent.parent / "logging_templates"

# ---------------------------------------------------------------------------
# Language → logging framework / template file mappings
# ---------------------------------------------------------------------------

#: Primary logging framework name per language (rendered into CLAUDE.md).
_FRAMEWORK_MAP: dict[str, str] = {
    "python": "structlog",
    "nodejs": "winston",
    "ruby": "semantic_logger",
    "go": "zap",
    "unknown": "structlog",  # safe default
}

#: logging_templates/ filename per language.
_TEMPLATE_FILE_MAP: dict[str, str] = {
    "python": "python_structlog.py",
    "nodejs": "nodejs_winston.js",
    "ruby": "ruby_semantic_logger.rb",
    "go": "go_zap.go",
    "unknown": "python_structlog.py",
}


class ClaudeLauncher:
    """Renders and writes CLAUDE.md to each project's local_path.

    Phase 2 full implementation:
    - Loads ``templates/CLAUDE.md.j2`` with Jinja2
    - Injects all project + global_settings fields as template context
    - Loads the appropriate logging template snippet from ``logging_templates/``
    """

    def __init__(self, template_dir: Optional[str] = None) -> None:
        if template_dir is None:
            template_dir = str(_TEMPLATES_DIR)
        self._env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape([]),
            keep_trailing_newline=True,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_language(self, project: ProjectConfig) -> str:
        """Return the concrete language string, auto-detecting if needed."""
        if project.language != "auto":
            return project.language
        return detect_language(project.local_path)

    def _get_logging_framework(self, language: str) -> str:
        """Return the canonical logging framework name for *language*."""
        return _FRAMEWORK_MAP.get(language, "structlog")

    def _load_logging_template(self, language: str) -> str:
        """Read and return the logging snippet file for *language*.

        Falls back to a one-line comment when the file is absent.
        """
        filename = _TEMPLATE_FILE_MAP.get(language, "python_structlog.py")
        template_path = _LOGGING_TEMPLATES_DIR / filename
        try:
            return template_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return f"# Logging template not found for language: {language}\n"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_claude_md(
        self,
        project: ProjectConfig,
        global_settings: Optional[GlobalSettings] = None,
    ) -> str:
        """Render ``templates/CLAUDE.md.j2`` and return the rendered string.

        All project fields and global settings are injected as Jinja2 context
        variables. The returned string contains no un-rendered ``{{ }}`` tags.
        """
        if global_settings is None:
            global_settings = GlobalSettings()

        language = self._resolve_language(project)
        logging_framework = self._get_logging_framework(language)
        logging_template_content = self._load_logging_template(language)

        push_branch = project.git.push_branch or project.branch
        ssh_key_path = os.path.expanduser(project.vps.ssh_key_path)

        vps = project.vps
        docker_container_name = vps.docker_container_name or ""
        docker_compose_path = vps.docker_compose_path or ""

        # Build a sensible log stream command if not explicitly configured
        if vps.log_stream_command:
            log_stream_command = vps.log_stream_command
        elif docker_container_name:
            log_stream_command = f"docker logs -f {docker_container_name}"
        else:
            log_stream_command = "docker logs -f <container>"

        context: dict = {
            # --- project identity ---
            "project_name": project.name,
            "language": language,
            "local_path": project.local_path,
            "log_path": project.log_path,
            "branch": project.branch,
            "push_branch": push_branch,
            # --- VPS core ---
            "vps_enabled": vps.enabled,
            "vps_host": vps.host if vps.enabled else "",
            "vps_user": vps.user,
            "ssh_key_path": ssh_key_path,
            "verify_command": vps.verify_command,
            "verify_output_contains": vps.verify_output_contains or "",
            "verify_timeout": vps.verify_timeout_seconds,
            # --- VPS Docker / compose ---
            "vps_docker_container_name": docker_container_name,
            "vps_docker_compose_path": docker_compose_path,
            "vps_log_stream_command": log_stream_command,
            # --- monitoring config ---
            "debounce_minutes": project.monitoring.error_debounce_minutes,
            "max_fixes_per_hour": project.monitoring.max_fixes_per_hour,
            "blocked_patterns": project.monitoring.blocked_patterns,
            # --- git / global ---
            "git_author_name": global_settings.git_author_name,
            "git_author_email": global_settings.git_author_email,
            # --- logging ---
            "logging_framework": logging_framework,
            "logging_template_content": logging_template_content,
        }

        template = self._env.get_template("CLAUDE.md.j2")
        return template.render(**context)

    def write_claude_md(self, project: ProjectConfig, content: str) -> Path:
        """Write pre-rendered CLAUDE.md content to project.local_path/CLAUDE.md.

        Creates parent directories as needed.
        Phase 3 watchdog calls this with a pre-rendered string.
        """
        out = Path(project.local_path).expanduser() / "CLAUDE.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        return out

    def render_and_write_to_disk(
        self,
        project: ProjectConfig,
        global_settings: Optional[GlobalSettings] = None,
    ) -> Path:
        """Render CLAUDE.md from template and write to disk; returns the path written."""
        content = self.generate_claude_md(project, global_settings)
        path = self.write_claude_md(project, content)
        get_logger().info("CLAUDE.md written to %s", path)
        return path

    def render_claude_md(
        self,
        project: ProjectConfig,
        global_settings: Optional[GlobalSettings] = None,
    ) -> str:
        """Alias for generate_claude_md — stable public API for Phase 3 watchdog."""
        return self.generate_claude_md(project, global_settings)

    def render_and_write(
        self,
        project: ProjectConfig,
        global_settings: Optional[GlobalSettings] = None,
    ) -> Path:
        """Render and write CLAUDE.md; alias for render_and_write_to_disk."""
        return self.render_and_write_to_disk(project, global_settings)
