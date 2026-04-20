"""Tests for autofix/repo_manager.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autofix.repo_manager import RepoManager, RepoResult


def _mock_project(
    name: str = "test-proj",
    local_path: str = "/tmp/test-proj",
    repo_url: str = "git@github.com:x/y.git",
    branch: str = "main",
    ssh_key: str | None = None,
):
    project = MagicMock()
    project.name = name
    project.local_path = local_path
    project.repo_url = repo_url
    project.branch = branch
    project.vps = MagicMock()
    project.vps.ssh_key_path = ssh_key

    # Support the model_copy(update={...}) call used by clone_fresh path
    def _model_copy(update=None):
        overrides = update or {}
        return _mock_project(
            name=overrides.get("name", project.name),
            local_path=overrides.get("local_path", project.local_path),
            repo_url=overrides.get("repo_url", project.repo_url),
            branch=overrides.get("branch", project.branch),
            ssh_key=project.vps.ssh_key_path,
        )

    project.model_copy = _model_copy
    return project


class TestRepoManager:
    def setup_method(self):
        self.manager = RepoManager("Test Agent", "test@autofix.local")

    def test_clone_success(self, tmp_path: Path):
        """clone() returns RepoResult(success=True, action='clone') on rc=0."""
        project = _mock_project(local_path=str(tmp_path / "new-repo"))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("autofix.repo_manager.subprocess.run", return_value=mock_result):
            result = self.manager.clone(project)

        assert result.success is True
        assert result.action == "clone"
        assert result.project_name == project.name

    def test_clone_failure(self, tmp_path: Path):
        """clone() returns RepoResult(success=False) when git exits nonzero."""
        project = _mock_project(local_path=str(tmp_path / "fail-repo"))

        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "Repository not found"

        with patch("autofix.repo_manager.subprocess.run", return_value=mock_result):
            result = self.manager.clone(project)

        assert result.success is False
        assert result.action == "clone"
        assert result.error == "Repository not found"

    def test_pull_success(self, tmp_path: Path):
        """pull() returns RepoResult(success=True, action='pull') on rc=0."""
        repo_dir = tmp_path / "existing-repo"
        repo_dir.mkdir()
        project = _mock_project(local_path=str(repo_dir))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Already up to date."
        mock_result.stderr = ""

        with patch("autofix.repo_manager.subprocess.run", return_value=mock_result):
            result = self.manager.pull(project)

        assert result.success is True
        assert result.action == "pull"

    def test_pull_failure(self, tmp_path: Path):
        """pull() returns RepoResult(success=False) on nonzero exit."""
        repo_dir = tmp_path / "fail-pull-repo"
        repo_dir.mkdir()
        project = _mock_project(local_path=str(repo_dir))

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error: failed to push some refs"

        with patch("autofix.repo_manager.subprocess.run", return_value=mock_result):
            result = self.manager.pull(project)

        assert result.success is False
        assert "failed" in result.error.lower() or result.error

    def test_clone_or_pull_clones_when_path_missing(self, tmp_path: Path):
        """clone_or_pull() calls clone when local_path doesn't exist."""
        missing_path = tmp_path / "nonexistent"
        project = _mock_project(local_path=str(missing_path))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("autofix.repo_manager.subprocess.run", return_value=mock_result):
            result = self.manager.clone_or_pull(project)

        assert result.action == "clone"

    def test_clone_or_pull_pulls_when_git_repo_exists(self, tmp_path: Path):
        """clone_or_pull() calls pull when local_path is a git repo."""
        repo_dir = tmp_path / "existing-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        project = _mock_project(local_path=str(repo_dir))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Already up to date."
        mock_result.stderr = ""

        with patch("autofix.repo_manager.subprocess.run", return_value=mock_result):
            result = self.manager.clone_or_pull(project)

        assert result.action == "pull"

    def test_clone_or_pull_handles_non_git_directory(self, tmp_path: Path):
        """clone_or_pull() handles existing non-git directory gracefully."""
        not_git = tmp_path / "not-a-repo"
        not_git.mkdir()
        project = _mock_project(local_path=str(not_git))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("autofix.repo_manager.subprocess.run", return_value=mock_result):
            result = self.manager.clone_or_pull(project)

        assert result.action == "clone_fresh"

    def test_build_git_env_sets_author(self):
        """_build_git_env includes git author info."""
        project = _mock_project(ssh_key=None)
        env = self.manager._build_git_env(project)
        assert env["GIT_AUTHOR_NAME"] == "Test Agent"
        assert env["GIT_AUTHOR_EMAIL"] == "test@autofix.local"
        assert env["GIT_TERMINAL_PROMPT"] == "0"

    def test_build_git_env_sets_ssh_command_when_key_provided(self, tmp_path: Path):
        """_build_git_env includes GIT_SSH_COMMAND when SSH key is set."""
        key = str(tmp_path / "id_rsa")
        project = _mock_project(ssh_key=key)
        env = self.manager._build_git_env(project)
        assert "GIT_SSH_COMMAND" in env
        assert key in env["GIT_SSH_COMMAND"]

    def test_clone_timeout(self, tmp_path: Path):
        """clone() handles timeout gracefully."""
        import subprocess
        project = _mock_project(local_path=str(tmp_path / "timeout-repo"))

        with patch(
            "autofix.repo_manager.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=120),
        ):
            result = self.manager.clone(project)

        assert result.success is False
        assert "timeout" in result.error.lower()
