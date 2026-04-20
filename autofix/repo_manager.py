"""Git clone / pull manager with SSH key support."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from autofix.config.schema import ProjectConfig
from autofix.logger import get_logger
from autofix.colors import GREEN, YELLOW, RED, RESET


def _info(project_name: str, msg: str) -> None:
    print(f"{GREEN}[{project_name}]{RESET} {msg}", flush=True)
    get_logger().info("[%s] %s", project_name, msg)


def _warn(project_name: str, msg: str) -> None:
    print(f"{YELLOW}[{project_name}] WARNING: {msg}{RESET}", flush=True)
    get_logger().warning("[%s] %s", project_name, msg)


def _error(project_name: str, msg: str) -> None:
    print(f"{RED}[{project_name}] ERROR: {msg}{RESET}", flush=True)
    get_logger().error("[%s] %s", project_name, msg)


@dataclass
class RepoResult:
    success: bool
    action: str  # "clone" | "pull" | "clone_fresh" | "skip"
    project_name: str
    error: Optional[str] = None
    new_local_path: Optional[str] = None  # Set when action=="clone_fresh" to signal updated path


class RepoManager:
    """Manages git clone and pull operations for projects."""

    def __init__(self, git_author_name: str, git_author_email: str) -> None:
        self.git_author_name = git_author_name
        self.git_author_email = git_author_email

    def clone_or_pull(self, project: ProjectConfig) -> RepoResult:
        """Clone the repo if it doesn't exist, pull if it does."""
        local_path = Path(project.local_path)

        if not local_path.exists():
            _info(project.name, f"Local path not found; cloning {project.repo_url}")
            return self.clone(project)

        if not (local_path / ".git").exists():
            timestamp = int(time.time())
            fresh_path_str = f"{project.local_path}_fresh_{timestamp}"
            _warn(
                project.name,
                f"Directory exists but is not a git repo. "
                f"Cloning fresh to {fresh_path_str}",
            )
            # Use model_copy to avoid bypassing Pydantic validators (M1)
            fresh_project = project.model_copy(update={"local_path": fresh_path_str})
            result = self.clone(fresh_project)
            return RepoResult(
                success=result.success,
                action="clone_fresh",
                project_name=project.name,
                error=result.error,
                new_local_path=fresh_path_str if result.success else None,
            )

        _info(project.name, f"Repo exists at {local_path}; pulling branch {project.branch}")
        return self.pull(project)

    def clone(self, project: ProjectConfig) -> RepoResult:
        """Run git clone."""
        cmd = [
            "git",
            "clone",
            "--branch",
            project.branch,
            project.repo_url,
            project.local_path,
        ]
        env = self._build_git_env(project)
        _info(project.name, f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            _error(project.name, "git clone timeout after 120s")
            return RepoResult(
                success=False,
                action="clone",
                project_name=project.name,
                error="git clone timeout after 120s",
            )

        if result.returncode == 0:
            _info(project.name, "Clone succeeded.")
            return RepoResult(success=True, action="clone", project_name=project.name)
        else:
            err = result.stderr.strip()
            _error(project.name, f"Clone failed: {err}")
            return RepoResult(
                success=False, action="clone", project_name=project.name, error=err
            )

    def pull(self, project: ProjectConfig) -> RepoResult:
        """Run git pull."""
        cmd = ["git", "pull", "origin", project.branch]
        env = self._build_git_env(project)
        _info(project.name, f"Running: {' '.join(cmd)} in {project.local_path}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=project.local_path,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            _error(project.name, "git pull timed out after 60s")
            return RepoResult(
                success=False,
                action="pull",
                project_name=project.name,
                error="git pull timed out",
            )

        if result.returncode == 0:
            _info(project.name, f"Pull succeeded: {result.stdout.strip()}")
            return RepoResult(success=True, action="pull", project_name=project.name)
        else:
            err = result.stderr.strip()
            _error(project.name, f"Pull failed: {err}")
            return RepoResult(
                success=False, action="pull", project_name=project.name, error=err
            )

    def _build_git_env(self, project: ProjectConfig) -> dict[str, str]:
        """Build environment dict for git subprocesses."""
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = self.git_author_name
        env["GIT_AUTHOR_EMAIL"] = self.git_author_email
        env["GIT_TERMINAL_PROMPT"] = "0"

        # SSH key from VPS config
        if hasattr(project, "vps") and project.vps and project.vps.ssh_key_path:
            key = project.vps.ssh_key_path  # already expanded by Pydantic validator
            env["GIT_SSH_COMMAND"] = (
                f'ssh -i "{key}" -o StrictHostKeyChecking=no -o BatchMode=yes'
            )

        env["GIT_COMMITTER_NAME"] = self.git_author_name
        env["GIT_COMMITTER_EMAIL"] = self.git_author_email

        return env
