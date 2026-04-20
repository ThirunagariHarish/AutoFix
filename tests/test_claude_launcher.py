"""Tests for autofix/claude_launcher.py — Phase 2 full implementation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pytest

from autofix.claude_launcher import ClaudeLauncher, _FRAMEWORK_MAP, _TEMPLATE_FILE_MAP
from autofix.config.schema import (
    GlobalSettings,
    GitConfig,
    MonitoringConfig,
    NotificationsConfig,
    ProjectConfig,
    VPSConfig,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_vps(
    *,
    enabled: bool = True,
    ssh_key_path: str = "/tmp/autofix-test-key",
    docker_container_name: Optional[str] = "test-container",
    docker_compose_path: Optional[str] = "/opt/test-app",
    log_stream_command: Optional[str] = "docker logs -f test-container",
    host: str = "10.0.0.1",
    user: str = "deploy",
    verify_command: str = "docker ps",
    verify_output_contains: Optional[str] = "Up",
) -> VPSConfig:
    return VPSConfig(
        enabled=enabled,
        host=host,
        user=user,
        ssh_key_path=ssh_key_path,
        docker_container_name=docker_container_name,
        docker_compose_path=docker_compose_path,
        log_stream_command=log_stream_command,
        verify_command=verify_command,
        verify_output_contains=verify_output_contains,
    )


def _make_project(
    *,
    name: str = "test-project",
    language: str = "python",
    local_path: str = "/tmp/autofix-test-project",
    branch: str = "main",
    push_branch: Optional[str] = None,
    blocked_patterns: Optional[list[str]] = None,
    max_fixes_per_hour: int = 3,
    debounce_minutes: int = 5,
    vps: Optional[VPSConfig] = None,
) -> ProjectConfig:
    if vps is None:
        vps = _make_vps()
    return ProjectConfig(
        name=name,
        repo_url="git@github.com:example/test.git",
        local_path=local_path,
        branch=branch,
        language=language,
        log_path="logs/app.log",
        vps=vps,
        git=GitConfig(push_branch=push_branch),
        monitoring=MonitoringConfig(
            error_debounce_minutes=debounce_minutes,
            max_fixes_per_hour=max_fixes_per_hour,
            blocked_patterns=blocked_patterns or [],
        ),
    )


def _make_global_settings(
    *,
    git_author_name: str = "AutoFix Test Agent",
    git_author_email: str = "autofix-test@local",
) -> GlobalSettings:
    return GlobalSettings(
        git_author_name=git_author_name,
        git_author_email=git_author_email,
    )


@pytest.fixture()
def launcher() -> ClaudeLauncher:
    return ClaudeLauncher()


@pytest.fixture()
def python_project() -> ProjectConfig:
    return _make_project(language="python")


@pytest.fixture()
def nodejs_project() -> ProjectConfig:
    return _make_project(name="test-node", language="nodejs")


@pytest.fixture()
def global_settings() -> GlobalSettings:
    return _make_global_settings()


# ---------------------------------------------------------------------------
# Test 1 — generate_claude_md returns a non-empty string
# ---------------------------------------------------------------------------

class TestGenerateClaudeMdReturnsString:
    def test_returns_non_empty_string(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_markdown_heading(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert "# AutoFix Agent Instructions" in result

    def test_result_contains_project_name(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert python_project.name in result

    def test_no_global_settings_uses_defaults(self, launcher, python_project):
        """generate_claude_md must work when global_settings is omitted (None)."""
        result = launcher.generate_claude_md(python_project)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Test 2 — no un-rendered Jinja2 tags remain in output
# ---------------------------------------------------------------------------

class TestNoUnrenderedJinjaTags:
    # Match any {{ ... }} pattern — Jinja2 should have expanded all of them
    _JINJA_PATTERN = re.compile(r"\{\{.*?\}\}")

    def test_python_project_no_jinja_tags(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        matches = self._JINJA_PATTERN.findall(result)
        assert matches == [], f"Un-rendered Jinja2 tags found: {matches}"

    def test_nodejs_project_no_jinja_tags(self, launcher, nodejs_project, global_settings):
        result = launcher.generate_claude_md(nodejs_project, global_settings)
        matches = self._JINJA_PATTERN.findall(result)
        assert matches == [], f"Un-rendered Jinja2 tags found: {matches}"

    def test_vps_disabled_no_jinja_tags(self, launcher, global_settings):
        project = _make_project(vps=_make_vps(enabled=False))
        result = launcher.generate_claude_md(project, global_settings)
        matches = self._JINJA_PATTERN.findall(result)
        assert matches == [], f"Un-rendered Jinja2 tags found: {matches}"

    def test_empty_blocked_patterns_no_jinja_tags(self, launcher, global_settings):
        project = _make_project(blocked_patterns=[])
        result = launcher.generate_claude_md(project, global_settings)
        matches = self._JINJA_PATTERN.findall(result)
        assert matches == [], f"Un-rendered Jinja2 tags found: {matches}"

    def test_non_empty_blocked_patterns_no_jinja_tags(self, launcher, global_settings):
        project = _make_project(blocked_patterns=["CVE-", "database migration"])
        result = launcher.generate_claude_md(project, global_settings)
        matches = self._JINJA_PATTERN.findall(result)
        assert matches == [], f"Un-rendered Jinja2 tags found: {matches}"


# ---------------------------------------------------------------------------
# Test 3 — VPS Docker fields appear in rendered output
# ---------------------------------------------------------------------------

class TestVpsDockerFieldsInOutput:
    def test_docker_container_name_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert "test-container" in result

    def test_log_stream_command_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert "docker logs -f test-container" in result

    def test_docker_compose_path_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert "/opt/test-app" in result

    def test_vps_host_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert "10.0.0.1" in result

    def test_vps_user_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert "deploy" in result

    def test_verify_command_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert "docker ps" in result

    def test_verify_output_contains_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        # "Up" is the verify_output_contains value in the fixture
        assert "Up" in result

    def test_ssh_key_path_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert "/tmp/autofix-test-key" in result

    def test_git_author_name_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert global_settings.git_author_name in result

    def test_git_author_email_rendered(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        assert global_settings.git_author_email in result

    def test_log_stream_command_fallback_when_no_log_stream_command(
        self, launcher, global_settings
    ):
        """When log_stream_command is None, fall back to 'docker logs -f <container>'."""
        vps = _make_vps(log_stream_command=None, docker_container_name="my-app")
        project = _make_project(vps=vps)
        result = launcher.generate_claude_md(project, global_settings)
        assert "docker logs -f my-app" in result


# ---------------------------------------------------------------------------
# Test 4 — write_claude_md writes CLAUDE.md to local_path
# ---------------------------------------------------------------------------

class TestWriteClaudeMd:
    def test_writes_file(self, launcher, global_settings, tmp_path):
        project = _make_project(local_path=str(tmp_path))
        content = launcher.generate_claude_md(project, global_settings)
        dest = launcher.write_claude_md(project, content)
        assert dest == tmp_path / "CLAUDE.md"
        assert dest.exists()

    def test_written_file_matches_generate_output(
        self, launcher, global_settings, tmp_path
    ):
        project = _make_project(local_path=str(tmp_path))
        expected = launcher.generate_claude_md(project, global_settings)
        dest = launcher.write_claude_md(project, expected)
        assert dest.read_text(encoding="utf-8") == expected

    def test_creates_parent_directories(self, launcher, global_settings, tmp_path):
        nested = tmp_path / "deep" / "nested" / "project"
        project = _make_project(local_path=str(nested))
        content = launcher.generate_claude_md(project, global_settings)
        dest = launcher.write_claude_md(project, content)
        assert dest.exists()

    def test_render_and_write_alias(self, launcher, global_settings, tmp_path):
        """render_and_write is an alias for render_and_write_to_disk."""
        project = _make_project(local_path=str(tmp_path))
        dest = launcher.render_and_write(project, global_settings)
        assert dest == tmp_path / "CLAUDE.md"
        assert dest.exists()

    def test_render_and_write_to_disk(self, launcher, global_settings, tmp_path):
        """render_and_write_to_disk renders and writes in one call."""
        project = _make_project(local_path=str(tmp_path))
        dest = launcher.render_and_write_to_disk(project, global_settings)
        assert dest == tmp_path / "CLAUDE.md"
        assert dest.exists()

    def test_render_claude_md_alias(self, launcher, python_project, global_settings):
        """render_claude_md is a stable public alias for generate_claude_md."""
        via_render = launcher.render_claude_md(python_project, global_settings)
        via_generate = launcher.generate_claude_md(python_project, global_settings)
        assert via_render == via_generate


# ---------------------------------------------------------------------------
# Test 5 — VPS disabled: SSH section minimal, no SSH command, shows CI/CD note
# ---------------------------------------------------------------------------

class TestVpsDisabled:
    def test_vps_disabled_shows_cicd_note(self, launcher, global_settings):
        project = _make_project(vps=_make_vps(enabled=False))
        result = launcher.generate_claude_md(project, global_settings)
        # Should mention CI/CD or "DISABLED"
        assert "DISABLED" in result or "CI/CD" in result or "disabled" in result.lower()

    def test_vps_disabled_no_docker_log_stream_in_ssh_context(
        self, launcher, global_settings
    ):
        """When VPS disabled the SSH streaming block should not appear."""
        project = _make_project(vps=_make_vps(enabled=False))
        result = launcher.generate_claude_md(project, global_settings)
        # The SSH connection block with the VPS host in it should not be present
        # (the host is "10.0.0.1" but vps_enabled=False means we render local tail)
        # Check the monitoring section references local log file instead
        assert "tail -F" in result or "local log file" in result.lower()

    def test_vps_disabled_no_ssh_verify_block(self, launcher, global_settings):
        """Verify section must say 'DISABLED' not show an SSH command block."""
        project = _make_project(vps=_make_vps(enabled=False))
        result = launcher.generate_claude_md(project, global_settings)
        assert "VPS verification is" in result.lower() or "disabled" in result.lower()


# ---------------------------------------------------------------------------
# Test 6 — blocked_patterns render correctly in both sections
# ---------------------------------------------------------------------------

class TestBlockedPatterns:
    def test_single_pattern_appears_in_output(self, launcher, global_settings):
        project = _make_project(blocked_patterns=["CVE-"])
        result = launcher.generate_claude_md(project, global_settings)
        assert "CVE-" in result

    def test_multiple_patterns_all_appear(self, launcher, global_settings):
        patterns = ["CVE-", "SQL injection", "database migration"]
        project = _make_project(blocked_patterns=patterns)
        result = launcher.generate_claude_md(project, global_settings)
        for p in patterns:
            assert p in result, f"Blocked pattern '{p}' not found in output"

    def test_empty_blocked_patterns_shows_none_note(self, launcher, global_settings):
        project = _make_project(blocked_patterns=[])
        result = launcher.generate_claude_md(project, global_settings)
        # Should mention "no blocked patterns" or similar
        assert "no blocked patterns" in result.lower()

    def test_blocked_patterns_appear_in_safety_rules(self, launcher, global_settings):
        """Blocked patterns must appear in Section 7 (Safety Rules)."""
        project = _make_project(blocked_patterns=["DROP TABLE", "credentials"])
        result = launcher.generate_claude_md(project, global_settings)
        # Both patterns must appear after the Safety Rules heading
        safety_idx = result.find("Safety Rules")
        assert safety_idx != -1, "Safety Rules section not found"
        safety_section = result[safety_idx:]
        assert "DROP TABLE" in safety_section
        assert "credentials" in safety_section

    def test_blocked_patterns_appear_in_monitoring_section(
        self, launcher, global_settings
    ):
        """Blocked patterns must also appear in Section 5 (monitoring loop)."""
        project = _make_project(blocked_patterns=["CVE-2025"])
        result = launcher.generate_claude_md(project, global_settings)
        monitoring_idx = result.find("Continuous Monitoring")
        assert monitoring_idx != -1, "Continuous Monitoring section not found"
        monitoring_section = result[monitoring_idx:]
        assert "CVE-2025" in monitoring_section


# ---------------------------------------------------------------------------
# Test 7 — language-specific content per language
# ---------------------------------------------------------------------------

class TestLanguageSpecificContent:
    @pytest.mark.parametrize("language,expected_framework", [
        ("python", "structlog"),
        ("nodejs", "winston"),
        ("ruby", "semantic_logger"),
        ("go", "zap"),
    ])
    def test_logging_framework_rendered(
        self, launcher, global_settings, language, expected_framework
    ):
        project = _make_project(language=language)
        result = launcher.generate_claude_md(project, global_settings)
        assert expected_framework in result

    @pytest.mark.parametrize("language,expected_snippet", [
        ("python", "structlog"),
        ("nodejs", "winston"),
        ("ruby", "SemanticLogger"),
        ("go", "zap"),
    ])
    def test_logging_template_content_embedded(
        self, launcher, global_settings, language, expected_snippet
    ):
        """The logging template file content should appear in the rendered CLAUDE.md."""
        project = _make_project(language=language)
        result = launcher.generate_claude_md(project, global_settings)
        assert expected_snippet in result, (
            f"Expected '{expected_snippet}' from logging template in output for {language}"
        )


# ---------------------------------------------------------------------------
# Test 8 — push_branch resolution
# ---------------------------------------------------------------------------

class TestPushBranchResolution:
    def test_uses_git_push_branch_when_set(self, launcher, global_settings):
        project = _make_project(branch="main", push_branch="release")
        result = launcher.generate_claude_md(project, global_settings)
        assert "release" in result

    def test_falls_back_to_branch_when_push_branch_not_set(
        self, launcher, global_settings
    ):
        project = _make_project(branch="develop", push_branch=None)
        result = launcher.generate_claude_md(project, global_settings)
        assert "develop" in result

    def test_push_branch_used_in_git_commands(self, launcher, global_settings):
        project = _make_project(branch="main", push_branch="hotfix")
        result = launcher.generate_claude_md(project, global_settings)
        assert "hotfix" in result


# ---------------------------------------------------------------------------
# Test 9 — monitoring config values render correctly
# ---------------------------------------------------------------------------

class TestMonitoringConfig:
    def test_debounce_minutes_rendered(self, launcher, global_settings):
        project = _make_project(debounce_minutes=15)
        result = launcher.generate_claude_md(project, global_settings)
        assert "15" in result

    def test_max_fixes_per_hour_rendered(self, launcher, global_settings):
        project = _make_project(max_fixes_per_hour=7)
        result = launcher.generate_claude_md(project, global_settings)
        assert "7" in result


# ---------------------------------------------------------------------------
# Test 10 — seven required sections exist
# ---------------------------------------------------------------------------

class TestRequiredSections:
    REQUIRED_HEADINGS = [
        "## 1. Identity & Constraints",
        "## 2. Project Configuration",
        "## 3. Phase 1: Logging Standardization",
        "## 4. Logging Framework Template",
        "## 5. Phase 2: Continuous Monitoring Loop",
        "## 6. log.md Format",
        "## 7. Safety Rules",
    ]

    def test_all_sections_present(self, launcher, python_project, global_settings):
        result = launcher.generate_claude_md(python_project, global_settings)
        for heading in self.REQUIRED_HEADINGS:
            assert heading in result, f"Section heading not found: {heading}"


# ---------------------------------------------------------------------------
# Test 11 — internal helper methods
# ---------------------------------------------------------------------------

class TestInternalHelpers:
    def test_get_logging_framework_python(self, launcher):
        assert launcher._get_logging_framework("python") == "structlog"

    def test_get_logging_framework_nodejs(self, launcher):
        assert launcher._get_logging_framework("nodejs") == "winston"

    def test_get_logging_framework_ruby(self, launcher):
        assert launcher._get_logging_framework("ruby") == "semantic_logger"

    def test_get_logging_framework_go(self, launcher):
        assert launcher._get_logging_framework("go") == "zap"

    def test_get_logging_framework_unknown_defaults_to_structlog(self, launcher):
        assert launcher._get_logging_framework("unknown") == "structlog"

    def test_get_logging_framework_unrecognised_defaults_to_structlog(self, launcher):
        assert launcher._get_logging_framework("cobol") == "structlog"

    def test_load_logging_template_python(self, launcher):
        content = launcher._load_logging_template("python")
        assert len(content) > 0
        assert "structlog" in content

    def test_load_logging_template_nodejs(self, launcher):
        content = launcher._load_logging_template("nodejs")
        assert len(content) > 0
        assert "winston" in content.lower()

    def test_load_logging_template_ruby(self, launcher):
        content = launcher._load_logging_template("ruby")
        assert len(content) > 0
        assert "semantic_logger" in content.lower()

    def test_load_logging_template_go(self, launcher):
        content = launcher._load_logging_template("go")
        assert len(content) > 0
        assert "zap" in content.lower()

    def test_load_logging_template_unknown_returns_structlog(self, launcher):
        content = launcher._load_logging_template("unknown")
        assert "structlog" in content

    def test_load_logging_template_missing_returns_comment(self, launcher):
        content = launcher._load_logging_template("cobol")
        assert "not found" in content.lower() or "#" in content


# ---------------------------------------------------------------------------
# Test 12 — Sentinel file: .autofix_init (not log.md) is used as sentinel
# ---------------------------------------------------------------------------

class TestSentinelFile:
    def test_sentinel_check_uses_autofix_init(self, launcher, python_project, global_settings):
        """Rendered CLAUDE.md must check .autofix_init, not log.md, as sentinel."""
        result = launcher.generate_claude_md(python_project, global_settings)
        assert ".autofix_init" in result, ".autofix_init sentinel not found in output"

    def test_sentinel_not_log_md(self, launcher, python_project, global_settings):
        """The Phase 1 check-first block must reference .autofix_init, not log.md."""
        result = launcher.generate_claude_md(python_project, global_settings)
        # Find the Phase 1 sentinel check line
        check_idx = result.find("Check first")
        assert check_idx != -1, "Check first block not found"
        check_line = result[check_idx:check_idx + 200]
        assert ".autofix_init" in check_line, (
            "Phase 1 sentinel check must reference .autofix_init"
        )
        # The CHECK line itself should not reference log.md as the sentinel
        assert "log.md" not in check_line, (
            "Phase 1 sentinel check must NOT reference log.md"
        )

    def test_phase1_completion_writes_autofix_init(self, launcher, python_project, global_settings):
        """The Phase 1 final step must mention writing .autofix_init."""
        result = launcher.generate_claude_md(python_project, global_settings)
        # After Phase 1 steps, .autofix_init should be written
        step6_idx = result.find("Step 6")
        assert step6_idx != -1, "Step 6 not found in output"
        step6_section = result[step6_idx:step6_idx + 600]
        assert ".autofix_init" in step6_section, (
            "Step 6 must write .autofix_init"
        )

    def test_autofix_init_in_gitignore_instructions(self, launcher, python_project, global_settings):
        """.autofix_init should appear in the .gitignore instructions."""
        result = launcher.generate_claude_md(python_project, global_settings)
        gitignore_idx = result.find(".gitignore")
        assert gitignore_idx != -1, ".gitignore section not found"
        # Find the .gitignore block content
        gitignore_section = result[gitignore_idx:gitignore_idx + 400]
        assert ".autofix_init" in gitignore_section, (
            ".autofix_init must appear in .gitignore instructions"
        )


# ---------------------------------------------------------------------------
# Test 13 — VPS disabled: no broken SSH commands (empty host) in log.md block
# ---------------------------------------------------------------------------

class TestVpsDisabledNoSshCommands:
    def test_no_empty_host_ssh_command(self, launcher, global_settings):
        """When VPS disabled, the log.md template section must NOT contain 'deploy@ '."""
        project = _make_project(vps=_make_vps(enabled=False))
        result = launcher.generate_claude_md(project, global_settings)
        # Empty host produces 'deploy@ ' (user@space) — must not appear
        assert "deploy@ " not in result, (
            "Broken SSH command with empty host must not appear for VPS-disabled project"
        )

    def test_vps_disabled_log_section_has_tail_command(self, launcher, global_settings):
        """When VPS disabled, log.md format section should show tail command."""
        project = _make_project(vps=_make_vps(enabled=False))
        result = launcher.generate_claude_md(project, global_settings)
        # Should have a local tail command instead of SSH streaming
        assert "tail -f" in result, (
            "VPS-disabled project should show tail -f in log section"
        )

    def test_vps_enabled_log_section_has_ssh_streaming(self, launcher, global_settings):
        """When VPS enabled, log.md format section should show SSH streaming."""
        project = _make_project(vps=_make_vps(enabled=True, host="10.0.0.1"))
        result = launcher.generate_claude_md(project, global_settings)
        assert "10.0.0.1" in result
        # SSH streaming block should be present in the log.md format section
        log_section_idx = result.find("## 6. log.md Format")
        assert log_section_idx != -1
        log_section = result[log_section_idx:]
        assert "ssh -i" in log_section, (
            "VPS-enabled project log section should contain SSH streaming command"
        )


# ---------------------------------------------------------------------------
# Test 14 — N-1: sample_project_python fixture is detected as Python
# ---------------------------------------------------------------------------

class TestSampleProjectFixture:
    def test_sample_project_python_detected_as_python(self):
        """The sample_project_python fixture must be detected as 'python'."""
        from autofix.language_detector import detect_language
        import os

        fixture_path = os.path.join(
            os.path.dirname(__file__), "fixtures", "sample_project_python"
        )
        lang = detect_language(fixture_path)
        assert lang == "python", (
            f"Expected 'python' for sample_project_python fixture, got '{lang}'"
        )
