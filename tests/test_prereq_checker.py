"""Tests for autofix/prereq_checker.py — covers all 5 code paths (AC-1.9)."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from autofix.prereq_checker import check_prerequisites


class TestCheckPrerequisites:
    """All failure paths must call sys.exit with code 2 (AC-1.9)."""

    def test_tmux_not_installed_exits_2(self):
        """sys.exit(2) when tmux binary is not found (rc != 0, stdout empty)."""
        with patch(
            "autofix.prereq_checker._run", return_value=(1, "", "not found")
        ), pytest.raises(SystemExit) as exc_info:
            check_prerequisites()
        assert exc_info.value.code == 2

    def test_tmux_version_too_old_exits_2(self):
        """sys.exit(2) when tmux reports a version < 3.0."""
        with patch(
            "autofix.prereq_checker._run", return_value=(0, "tmux 2.9", "")
        ), pytest.raises(SystemExit) as exc_info:
            check_prerequisites()
        assert exc_info.value.code == 2

    def test_git_not_installed_exits_2(self):
        """sys.exit(2) when git is not on PATH."""
        def _which(cmd: str):
            # tmux passes the version check; git is missing
            return None if cmd == "git" else f"/usr/bin/{cmd}"

        with patch(
            "autofix.prereq_checker._run", return_value=(0, "tmux 3.3a", "")
        ), patch(
            "autofix.prereq_checker.shutil.which", side_effect=_which
        ), pytest.raises(SystemExit) as exc_info:
            check_prerequisites()
        assert exc_info.value.code == 2

    def test_claude_not_installed_exits_2(self):
        """sys.exit(2) when claude CLI is not on PATH."""
        def _which(cmd: str):
            # tmux and git pass; claude is missing
            return None if cmd == "claude" else f"/usr/bin/{cmd}"

        with patch(
            "autofix.prereq_checker._run", return_value=(0, "tmux 3.3a", "")
        ), patch(
            "autofix.prereq_checker.shutil.which", side_effect=_which
        ), pytest.raises(SystemExit) as exc_info:
            check_prerequisites()
        assert exc_info.value.code == 2

    def test_all_prerequisites_present_returns_normally(self):
        """check_prerequisites() returns without calling sys.exit when all are present."""
        def _which(cmd: str):
            return f"/usr/bin/{cmd}"

        with patch(
            "autofix.prereq_checker._run", return_value=(0, "tmux 3.3a", "")
        ), patch(
            "autofix.prereq_checker.shutil.which", side_effect=_which
        ):
            # Must not raise SystemExit
            check_prerequisites()
