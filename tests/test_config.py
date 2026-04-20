"""Tests for autofix/config/schema.py and autofix/config/loader.py."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from autofix.config.loader import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    load_config,
)
from autofix.config.schema import (
    AutoFixConfig,
    GlobalSettings,
    MonitoringConfig,
    ProjectConfig,
    VPSConfig,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ssh_key(tmp_path: Path) -> Path:
    """Create a dummy SSH key file and return its path."""
    key = tmp_path / "id_rsa"
    key.write_text("dummy-key")
    return key


def _valid_project_dict(local_path: str, ssh_key: str) -> dict:
    return {
        "name": "test-project",
        "repo_url": "git@github.com:user/repo.git",
        "local_path": local_path,
        "branch": "main",
        "language": "python",
        "vps": {
            "host": "192.168.1.1",
            "user": "deploy",
            "ssh_key_path": ssh_key,
            "verify_command": "docker ps",
        },
    }


# ---------------------------------------------------------------------------
# ConfigFileNotFoundError
# ---------------------------------------------------------------------------

def test_load_config_missing_file():
    with pytest.raises(ConfigFileNotFoundError) as exc_info:
        load_config("/nonexistent/path/projects.yaml")
    assert "not found" in str(exc_info.value)


# ---------------------------------------------------------------------------
# ConfigParseError
# ---------------------------------------------------------------------------

def test_load_config_invalid_yaml(tmp_path: Path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("key: [unclosed bracket\n")
    with pytest.raises(ConfigParseError):
        load_config(str(bad_yaml))


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def test_missing_vps_field(tmp_path: Path):
    """Fixture projects_invalid_missing_field.yaml should raise ConfigValidationError."""
    # Create a fake ssh key so VPS validation doesn't trigger on valid fixtures
    key = _make_ssh_key(tmp_path)

    bad_yaml = tmp_path / "missing_vps.yaml"
    bad_yaml.write_text(
        "schema_version: '1.0'\n"
        "projects:\n"
        "  - name: broken-project\n"
        "    repo_url: git@github.com:x/y.git\n"
        f"    local_path: /tmp/autofix-test\n"
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(str(bad_yaml))
    assert exc_info.value.errors  # at least one error


def test_duplicate_project_name(tmp_path: Path):
    key = _make_ssh_key(tmp_path)
    yaml_content = (
        "schema_version: '1.0'\n"
        "projects:\n"
        "  - name: dup\n"
        "    repo_url: git@github.com:x/a.git\n"
        "    local_path: /tmp/a\n"
        "    vps:\n"
        "      host: 1.2.3.4\n"
        "      user: u\n"
        f"      ssh_key_path: {key}\n"
        "      verify_command: docker ps\n"
        "  - name: dup\n"
        "    repo_url: git@github.com:x/b.git\n"
        "    local_path: /tmp/b\n"
        "    vps:\n"
        "      host: 1.2.3.5\n"
        "      user: u\n"
        f"      ssh_key_path: {key}\n"
        "      verify_command: docker ps\n"
    )
    f = tmp_path / "dup.yaml"
    f.write_text(yaml_content)
    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(str(f))
    combined = " ".join(exc_info.value.errors)
    assert "Duplicate project name" in combined or "dup" in combined


def test_unsupported_language(tmp_path: Path):
    key = _make_ssh_key(tmp_path)
    yaml_content = (
        "schema_version: '1.0'\n"
        "projects:\n"
        "  - name: rust-proj\n"
        "    repo_url: git@github.com:x/rust.git\n"
        "    local_path: /tmp/rust\n"
        "    language: rust\n"
        "    vps:\n"
        "      host: 1.2.3.4\n"
        "      user: u\n"
        f"      ssh_key_path: {key}\n"
        "      verify_command: docker ps\n"
    )
    f = tmp_path / "rust.yaml"
    f.write_text(yaml_content)
    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(str(f))
    combined = " ".join(exc_info.value.errors)
    assert "rust" in combined or "Unsupported language" in combined


def test_relative_local_path_rejected(tmp_path: Path):
    key = _make_ssh_key(tmp_path)
    yaml_content = (
        "schema_version: '1.0'\n"
        "projects:\n"
        "  - name: rel-proj\n"
        "    repo_url: git@github.com:x/rel.git\n"
        "    local_path: relative/path\n"
        "    vps:\n"
        "      host: 1.2.3.4\n"
        "      user: u\n"
        f"      ssh_key_path: {key}\n"
        "      verify_command: docker ps\n"
    )
    f = tmp_path / "rel.yaml"
    f.write_text(yaml_content)
    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(str(f))
    combined = " ".join(exc_info.value.errors)
    assert "absolute" in combined or "local_path" in combined


def test_too_many_projects(tmp_path: Path):
    key = _make_ssh_key(tmp_path)
    projects = []
    for i in range(11):
        projects.append(
            f"  - name: proj-{i}\n"
            f"    repo_url: git@github.com:x/p{i}.git\n"
            f"    local_path: /tmp/p{i}\n"
            "    vps:\n"
            "      host: 1.2.3.4\n"
            "      user: u\n"
            f"      ssh_key_path: {key}\n"
            "      verify_command: docker ps\n"
        )
    yaml_content = "schema_version: '1.0'\nprojects:\n" + "".join(projects)
    f = tmp_path / "toomany.yaml"
    f.write_text(yaml_content)
    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(str(f))
    combined = " ".join(exc_info.value.errors)
    assert "10" in combined or "Too many" in combined


def test_max_fixes_out_of_range(tmp_path: Path):
    key = _make_ssh_key(tmp_path)
    yaml_content = (
        "schema_version: '1.0'\n"
        "projects:\n"
        "  - name: bad-limits\n"
        "    repo_url: git@github.com:x/b.git\n"
        "    local_path: /tmp/bad\n"
        "    vps:\n"
        "      host: 1.2.3.4\n"
        "      user: u\n"
        f"      ssh_key_path: {key}\n"
        "      verify_command: docker ps\n"
        "    monitoring:\n"
        "      max_fixes_per_hour: 99\n"
    )
    f = tmp_path / "limits.yaml"
    f.write_text(yaml_content)
    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(str(f))
    combined = " ".join(exc_info.value.errors)
    assert "max_fixes_per_hour" in combined or "20" in combined


# ---------------------------------------------------------------------------
# Valid config
# ---------------------------------------------------------------------------

def test_valid_config_loads(tmp_path: Path):
    key = _make_ssh_key(tmp_path)
    yaml_content = (
        "schema_version: '1.0'\n"
        "global:\n"
        "  tmux_session_name: test-session\n"
        "projects:\n"
        "  - name: good-project\n"
        "    repo_url: git@github.com:x/good.git\n"
        "    local_path: /tmp/good\n"
        "    vps:\n"
        "      host: 1.2.3.4\n"
        "      user: deploy\n"
        f"      ssh_key_path: {key}\n"
        "      verify_command: docker ps\n"
    )
    f = tmp_path / "valid.yaml"
    f.write_text(yaml_content)
    config = load_config(str(f))
    assert config.schema_version == "1.0"
    assert config.global_settings.tmux_session_name == "test-session"
    assert len(config.projects) == 1
    assert config.projects[0].name == "good-project"


def test_global_settings_defaults():
    gs = GlobalSettings()
    assert gs.tmux_session_name == "autofix"
    assert gs.watchdog_interval_seconds == 60
    assert gs.claude_command == "claude --dangerously-skip-permissions"


def test_monitoring_defaults():
    m = MonitoringConfig()
    assert m.error_debounce_minutes == 5
    assert m.max_fixes_per_hour == 3
    assert m.blocked_patterns == []
