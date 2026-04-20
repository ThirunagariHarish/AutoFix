"""Tests for autofix/tmux_manager.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from autofix.tmux_manager import TmuxManager


def _make_manager():
    with patch("autofix.tmux_manager.libtmux.Server"):
        manager = TmuxManager(
            session_name="test-autofix",
            claude_command="claude --dangerously-skip-permissions",
            git_author_name="Test Agent",
            git_author_email="test@autofix.local",
        )
    return manager


def _mock_project(name="test-proj", local_path="/tmp/test"):
    p = MagicMock()
    p.name = name
    p.local_path = local_path
    return p


class TestTmuxManager:
    def test_init_sets_attributes(self):
        manager = _make_manager()
        assert manager.session_name == "test-autofix"
        assert manager.claude_command == "claude --dangerously-skip-permissions"
        assert manager.git_author_name == "Test Agent"

    def test_get_or_create_session_returns_existing(self):
        manager = _make_manager()
        existing_session = MagicMock()
        existing_session.name = "test-autofix"
        manager._server.sessions.get = MagicMock(return_value=existing_session)

        session = manager.get_or_create_session()

        assert session is existing_session
        manager._server.new_session.assert_not_called()

    def test_get_or_create_session_creates_new(self):
        manager = _make_manager()
        manager._server.sessions.get = MagicMock(return_value=None)
        new_session = MagicMock()
        manager._server.new_session = MagicMock(return_value=new_session)

        session = manager.get_or_create_session()

        assert session is new_session
        manager._server.new_session.assert_called_once_with(
            session_name="test-autofix", detach=True
        )

    def test_create_project_window_returns_existing(self):
        manager = _make_manager()
        project = _mock_project()
        mock_session = MagicMock()
        existing_window = MagicMock()
        mock_session.windows.get = MagicMock(return_value=existing_window)

        window = manager.create_project_window(mock_session, project)

        assert window is existing_window
        mock_session.new_window.assert_not_called()

    def test_create_project_window_creates_new(self):
        manager = _make_manager()
        project = _mock_project(name="new-proj", local_path="/tmp/new")
        mock_session = MagicMock()
        mock_session.windows.get = MagicMock(return_value=None)
        new_window = MagicMock()
        mock_session.new_window = MagicMock(return_value=new_window)

        window = manager.create_project_window(mock_session, project)

        assert window is new_window
        mock_session.new_window.assert_called_once_with(
            window_name="new-proj",
            start_directory="/tmp/new",
        )

    def test_launch_agent_sends_keys(self):
        manager = _make_manager()
        project = _mock_project(name="test-proj", local_path="/tmp/test")
        mock_window = MagicMock()
        mock_pane = MagicMock()
        mock_window.panes = [mock_pane]

        manager.launch_agent(mock_window, project)

        # Should have called send_keys at least 3 times
        assert mock_pane.send_keys.call_count >= 3

        calls = [str(c) for c in mock_pane.send_keys.call_args_list]
        combined = " ".join(calls)
        assert "/tmp/test" in combined
        assert "claude" in combined

    def test_is_pane_alive_returns_true_for_existing_pane(self):
        manager = _make_manager()
        mock_session = MagicMock()
        mock_window = MagicMock()
        mock_pane = MagicMock()
        mock_pane.dead = False
        mock_window.panes = [mock_pane]
        mock_session.windows.get = MagicMock(return_value=mock_window)

        result = manager.is_pane_alive(mock_session, "test-proj")
        assert result is True

    def test_is_pane_alive_returns_false_for_missing_window(self):
        manager = _make_manager()
        mock_session = MagicMock()
        mock_session.windows.get = MagicMock(return_value=None)

        result = manager.is_pane_alive(mock_session, "nonexistent")
        assert result is False

    def test_list_panes_returns_all_panes(self):
        manager = _make_manager()
        mock_session = MagicMock()
        pane1, pane2, pane3 = MagicMock(), MagicMock(), MagicMock()
        win1 = MagicMock()
        win1.panes = [pane1, pane2]
        win2 = MagicMock()
        win2.panes = [pane3]
        mock_session.windows = [win1, win2]

        panes = manager.list_panes(mock_session)
        assert len(panes) == 3
        assert pane1 in panes
        assert pane3 in panes

    def test_attach_session_calls_subprocess(self):
        manager = _make_manager()
        mock_session = MagicMock()
        mock_session.name = "test-autofix"

        with patch("autofix.tmux_manager.subprocess.run") as mock_run:
            manager.attach_session(mock_session)

        mock_run.assert_called_once_with(
            ["tmux", "attach-session", "-t", "test-autofix"],
            check=False,
        )
