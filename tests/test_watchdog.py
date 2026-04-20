"""Tests for autofix/watchdog.py — Phase 3."""

from __future__ import annotations

import time
import threading
from unittest.mock import MagicMock, patch

import pytest

from autofix.watchdog import Watchdog, _CRASH_LOOP_THRESHOLD, _CRASH_WINDOW_SECONDS
from autofix.config.schema import GlobalSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_global_settings(interval: int = 1) -> GlobalSettings:
    """Return a GlobalSettings with a very short watchdog interval for tests."""
    return GlobalSettings(watchdog_interval_seconds=interval)


def _make_project(name: str = "test-proj") -> MagicMock:
    """Return a minimal mock ProjectConfig."""
    p = MagicMock()
    p.name = name
    p.local_path = f"/tmp/{name}"
    return p


def _make_repo_manager() -> MagicMock:
    """Return a mock RepoManager whose clone_or_pull always succeeds."""
    rm = MagicMock()
    rm.clone_or_pull.return_value = MagicMock(success=True)
    return rm


def _make_watchdog(
    projects=None,
    interval: int = 1,
    tmux_manager=None,
    claude_launcher=None,
    repo_manager=None,
    notifier=None,
) -> Watchdog:
    """Build a Watchdog with sensible mock dependencies."""
    if projects is None:
        projects = [_make_project("proj-a")]
    gs = _make_global_settings(interval)
    tmux = tmux_manager or MagicMock()
    launcher = claude_launcher or MagicMock()
    repo_mgr = repo_manager or _make_repo_manager()
    mock_notifier = notifier or MagicMock()
    return Watchdog(
        tmux_manager=tmux,
        claude_launcher=launcher,
        repo_manager=repo_mgr,
        projects=projects,
        global_settings=gs,
        notifier=mock_notifier,
        interval_seconds=interval,
    )


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestWatchdogInit:
    def test_is_a_daemon_thread(self):
        wd = _make_watchdog()
        assert wd.daemon is True

    def test_thread_name(self):
        wd = _make_watchdog()
        assert wd.name == "watchdog"

    def test_interval_taken_from_global_settings(self):
        gs = GlobalSettings(watchdog_interval_seconds=42)
        wd = Watchdog(
            tmux_manager=MagicMock(),
            claude_launcher=MagicMock(),
            repo_manager=_make_repo_manager(),
            projects=[_make_project()],
            global_settings=gs,
            notifier=MagicMock(),
        )
        assert wd._interval == 42

    def test_stop_event_initially_clear(self):
        wd = _make_watchdog()
        assert not wd._stop_event.is_set()

    def test_crash_times_initially_empty(self):
        wd = _make_watchdog()
        assert len(wd._crash_times) == 0

    def test_paused_until_initially_empty(self):
        wd = _make_watchdog()
        assert len(wd._paused_until) == 0

    def test_projects_stored(self):
        p1 = _make_project("alpha")
        p2 = _make_project("beta")
        wd = _make_watchdog(projects=[p1, p2])
        assert len(wd._projects) == 2


# ---------------------------------------------------------------------------
# stop() signals the event
# ---------------------------------------------------------------------------


class TestWatchdogStop:
    def test_stop_sets_event(self):
        wd = _make_watchdog()
        assert not wd._stop_event.is_set()
        wd.stop()
        assert wd._stop_event.is_set()

    def test_run_exits_quickly_after_stop(self):
        """run() should return within 2 seconds after stop() is called."""
        wd = _make_watchdog(interval=30)  # long interval — would block forever
        wd.start()
        time.sleep(0.05)  # let the thread enter wait()
        wd.stop()
        wd.join(timeout=2)
        assert not wd.is_alive(), "Watchdog thread should have stopped"

    def test_run_loops_at_least_once_before_stop(self):
        """Verify _check_projects is called at least once during a normal cycle."""
        wd = _make_watchdog(interval=60)  # long interval — bypassed via mock
        check_called = threading.Event()

        def check_and_stop():
            check_called.set()
            wd.stop()

        wd._check_projects = MagicMock(side_effect=check_and_stop)
        # Replace blocking wait with a non-blocking check so the test runs fast.
        wd._stop_event.wait = lambda timeout=None: wd._stop_event.is_set()

        wd.start()
        assert check_called.wait(timeout=5), "_check_projects was never called"
        wd.join(timeout=3)
        assert wd._check_projects.call_count >= 1


# ---------------------------------------------------------------------------
# Dead pane triggers respawn
# ---------------------------------------------------------------------------


class TestWatchdogRespawn:
    def _make_wd_with_dead_pane(self, project_name: str = "dead-proj"):
        """Set up a watchdog where the named project's pane is dead."""
        project = _make_project(project_name)
        tmux = MagicMock()
        launcher = MagicMock()
        repo_mgr = _make_repo_manager()
        mock_notifier = MagicMock()
        launcher.render_claude_md.return_value = "# CLAUDE.md content"

        # Pane is dead → is_pane_alive returns False
        tmux.is_pane_alive.return_value = False
        tmux.get_or_create_session.return_value = MagicMock()
        new_window = MagicMock()
        tmux.create_project_window.return_value = new_window

        wd = _make_watchdog(
            projects=[project],
            tmux_manager=tmux,
            claude_launcher=launcher,
            repo_manager=repo_mgr,
            notifier=mock_notifier,
        )
        return wd, tmux, launcher, project

    def test_dead_pane_triggers_create_project_window(self):
        wd, tmux, launcher, project = self._make_wd_with_dead_pane()
        wd._check_projects()
        tmux.create_project_window.assert_called_once()

    def test_dead_pane_triggers_launch_agent(self):
        wd, tmux, launcher, project = self._make_wd_with_dead_pane()
        wd._check_projects()
        tmux.launch_agent.assert_called_once()

    def test_dead_pane_renders_claude_md(self):
        wd, tmux, launcher, project = self._make_wd_with_dead_pane()
        wd._check_projects()
        launcher.render_claude_md.assert_called_once_with(project, wd._global_settings)

    def test_dead_pane_writes_claude_md(self):
        wd, tmux, launcher, project = self._make_wd_with_dead_pane()
        wd._check_projects()
        launcher.write_claude_md.assert_called_once()

    def test_dead_pane_kills_existing_window_first(self):
        wd, tmux, launcher, project = self._make_wd_with_dead_pane()
        wd._check_projects()
        tmux.kill_window_if_exists.assert_called_once()

    def test_alive_pane_does_not_trigger_respawn(self):
        project = _make_project("alive-proj")
        tmux = MagicMock()
        tmux.is_pane_alive.return_value = True  # alive
        tmux.get_or_create_session.return_value = MagicMock()
        launcher = MagicMock()

        wd = _make_watchdog(
            projects=[project],
            tmux_manager=tmux,
            claude_launcher=launcher,
        )
        wd._check_projects()
        tmux.create_project_window.assert_not_called()
        launcher.render_claude_md.assert_not_called()

    def test_crash_counter_incremented_on_respawn(self):
        wd, tmux, launcher, project = self._make_wd_with_dead_pane("count-proj")
        wd._check_projects()
        assert len(wd._crash_times["count-proj"]) == 1

    def test_respawn_exception_does_not_propagate(self):
        """Respawn errors must not crash the watchdog poll loop."""
        project = _make_project("exception-proj")
        tmux = MagicMock()
        tmux.is_pane_alive.return_value = False
        tmux.get_or_create_session.return_value = MagicMock()
        launcher = MagicMock()
        launcher.render_claude_md.side_effect = RuntimeError("template error")

        wd = _make_watchdog(
            projects=[project],
            tmux_manager=tmux,
            claude_launcher=launcher,
        )
        # Must not raise
        wd._check_projects()

    def test_repo_manager_called_during_respawn(self):
        """repo_manager.clone_or_pull must be called on every respawn."""
        wd, tmux, launcher, project = self._make_wd_with_dead_pane()
        wd._check_projects()
        wd._repo_manager.clone_or_pull.assert_called_once_with(project)

    def test_failed_pull_does_not_prevent_respawn(self):
        """A failed git pull must NOT prevent the pane from being respawned."""
        wd, tmux, launcher, project = self._make_wd_with_dead_pane()
        failed_result = MagicMock()
        failed_result.success = False
        wd._repo_manager.clone_or_pull.return_value = failed_result

        wd._check_projects()

        # Respawn must still happen despite the pull failure.
        tmux.create_project_window.assert_called_once()
        tmux.launch_agent.assert_called_once()

    def test_notifier_called_with_pane_respawned_on_success(self):
        """notifier.notify must be called with 'pane_respawned' after a successful respawn."""
        wd, tmux, launcher, project = self._make_wd_with_dead_pane()
        wd._check_projects()
        wd._notifier.notify.assert_called_once()
        call_args = wd._notifier.notify.call_args
        assert call_args[0][0] is project
        assert call_args[0][1] == "pane_respawned"


# ---------------------------------------------------------------------------
# Crash-loop detection
# ---------------------------------------------------------------------------


class TestCrashLoopDetection:
    def _wd_with_pre_seeded_crashes(
        self, project_name: str, crash_count: int, ago_seconds: float = 0
    ) -> tuple[Watchdog, MagicMock, MagicMock]:
        """Build a watchdog pre-seeded with *crash_count* recent crashes."""
        project = _make_project(project_name)
        tmux = MagicMock()
        tmux.is_pane_alive.return_value = False
        tmux.get_or_create_session.return_value = MagicMock()
        tmux.create_project_window.return_value = MagicMock()
        launcher = MagicMock()
        launcher.render_claude_md.return_value = ""
        repo_mgr = _make_repo_manager()
        mock_notifier = MagicMock()

        wd = _make_watchdog(
            projects=[project],
            tmux_manager=tmux,
            claude_launcher=launcher,
            repo_manager=repo_mgr,
            notifier=mock_notifier,
        )
        # Pre-seed crash times within the rolling window.
        now = time.time() - ago_seconds
        wd._crash_times[project_name] = [now - i for i in range(crash_count)]
        return wd, tmux, launcher

    def test_five_crashes_still_allows_respawn(self):
        """Five recent crashes == threshold → still below >threshold, so respawn."""
        wd, tmux, launcher = self._wd_with_pre_seeded_crashes("proj", 5)
        wd._check_projects()
        tmux.create_project_window.assert_called_once()
        assert wd._paused_until.get("proj", 0) <= time.time()

    def test_six_crashes_triggers_crash_loop(self):
        """Six recent crashes > threshold → crash-loop declared, no respawn."""
        wd, tmux, launcher = self._wd_with_pre_seeded_crashes("proj", 6)
        wd._check_projects()
        assert wd._paused_until.get("proj", 0) > time.time()
        tmux.create_project_window.assert_not_called()

    def test_seventh_crash_not_respawned_when_in_pause(self):
        """After crash-loop pause is set, subsequent checks skip respawn."""
        wd, tmux, launcher = self._wd_with_pre_seeded_crashes("proj", 6)
        # First check → declares crash-loop pause
        wd._check_projects()
        # Reset call counts
        tmux.create_project_window.reset_mock()
        # Second check → still in pause, should not respawn
        wd._check_projects()
        tmux.create_project_window.assert_not_called()

    def test_pause_expires_allows_respawn(self):
        """After the 10-min pause expires, a dead pane should be respawned again."""
        wd, tmux, launcher = self._wd_with_pre_seeded_crashes("proj", 6)
        # First check → declares crash-loop pause
        wd._check_projects()
        assert wd._paused_until.get("proj", 0) > time.time()
        tmux.create_project_window.reset_mock()

        # Artificially expire the pause by setting it to the past.
        wd._paused_until["proj"] = time.time() - 1

        # Second check → pause expired, should respawn.
        wd._check_projects()
        tmux.create_project_window.assert_called_once()

    def test_old_crashes_outside_window_do_not_count(self):
        """Crashes older than 10 min must NOT count toward crash-loop threshold."""
        # Pre-seed 6 crashes, but all > 10 min ago (outside the rolling window).
        wd, tmux, launcher = self._wd_with_pre_seeded_crashes(
            "proj", 6, ago_seconds=_CRASH_WINDOW_SECONDS + 60
        )
        wd._check_projects()
        # Should have respawned (old crashes pruned from window).
        tmux.create_project_window.assert_called_once()
        assert wd._paused_until.get("proj", 0) <= time.time()

    def test_crash_loop_reset_after_window_passes(self):
        """If crash times fall outside the 10-min window, a fresh crash is OK."""
        project = _make_project("reset-proj")
        tmux = MagicMock()
        tmux.is_pane_alive.return_value = False
        tmux.get_or_create_session.return_value = MagicMock()
        tmux.create_project_window.return_value = MagicMock()
        launcher = MagicMock()
        launcher.render_claude_md.return_value = ""

        wd = _make_watchdog(
            projects=[project],
            tmux_manager=tmux,
            claude_launcher=launcher,
            repo_manager=_make_repo_manager(),
            notifier=MagicMock(),
        )

        # Seed exactly 5 crashes that just expired (barely outside window).
        expired = time.time() - (_CRASH_WINDOW_SECONDS + 10)
        wd._crash_times["reset-proj"] = [expired - i for i in range(5)]

        # This call will prune all expired entries → only 0 recent crashes.
        # Should NOT be in crash-loop pause.
        wd._check_projects()

        assert wd._paused_until.get("reset-proj", 0) <= time.time()
        tmux.create_project_window.assert_called_once()

    def test_notifier_called_with_crash_loop_detected(self):
        """notifier.notify must be called with 'crash_loop_detected' when crash-loop fires."""
        wd, tmux, launcher = self._wd_with_pre_seeded_crashes("proj", 6)
        wd._check_projects()
        wd._notifier.notify.assert_called_once()
        call_args = wd._notifier.notify.call_args
        # First positional arg is the project, second is the event name.
        assert call_args[0][1] == "crash_loop_detected"

    def test_session_error_does_not_raise(self):
        """If get_or_create_session fails, _check_projects must not raise."""
        project = _make_project("err-proj")
        tmux = MagicMock()
        tmux.get_or_create_session.side_effect = RuntimeError("tmux gone")
        launcher = MagicMock()

        wd = _make_watchdog(
            projects=[project],
            tmux_manager=tmux,
            claude_launcher=launcher,
        )
        wd._check_projects()  # should not raise
