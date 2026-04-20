"""Watchdog thread — detects dead Claude panes and respawns them.

Phase 3 implementation (US-10, US-11, US-15).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from autofix.config.schema import GlobalSettings, ProjectConfig
from autofix.logger import get_logger

if TYPE_CHECKING:  # avoid circular imports at runtime
    from autofix.claude_launcher import ClaudeLauncher
    from autofix.notifier import Notifier
    from autofix.repo_manager import RepoManager
    from autofix.tmux_manager import TmuxManager

# Number of crashes within the rolling window to declare a crash-loop.
# Fires at 6+ crashes (> threshold).
_CRASH_LOOP_THRESHOLD = 5

# Rolling window duration (seconds) for crash-loop detection.
_CRASH_WINDOW_SECONDS = 600  # 10 minutes


class Watchdog(threading.Thread):
    """Background thread that polls tmux panes and respawns dead ones.

    Crash-loop protection: if a project crashes >5 times within 10
    minutes the watchdog suspends restarts for 10 minutes, then
    automatically resumes — preventing an infinite-restart storm.
    """

    def __init__(
        self,
        tmux_manager: "TmuxManager",
        claude_launcher: "ClaudeLauncher",
        repo_manager: "RepoManager",
        projects: list[ProjectConfig],
        global_settings: GlobalSettings,
        notifier: "Notifier | None" = None,
        interval_seconds: int = 60,
    ) -> None:
        super().__init__(daemon=True, name="watchdog")
        self._tmux_manager = tmux_manager
        self._claude_launcher = claude_launcher
        self._repo_manager = repo_manager
        self._projects = list(projects)
        self._global_settings = global_settings
        self._notifier = notifier
        # Prefer the value baked into global_settings; *interval_seconds*
        # acts as a fallback (kept for test convenience).
        self._interval = global_settings.watchdog_interval_seconds or interval_seconds

        self._stop_event = threading.Event()

        # Per-project crash timestamps (used for crash-loop detection).
        self._crash_times: dict[str, list[float]] = defaultdict(list)

        # Per-project pause-until timestamp (replaces permanent ban).
        # When _paused_until[name] > time.time() the project is in the
        # timed 10-minute back-off window; the guard expires automatically
        # on the next poll tick after the timestamp passes — no extra code needed.
        self._paused_until: dict[str, float] = {}  # project_name -> resume timestamp

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Poll every interval_seconds. For each project, check if pane is alive.
        Respawn if dead (unless in crash-loop pause window)."""
        get_logger().info("[watchdog] Started. Polling every %ds.", self._interval)
        while not self._stop_event.is_set():
            # Wait for interval, but wake immediately when stop is requested.
            self._stop_event.wait(self._interval)
            if self._stop_event.is_set():
                break
            try:
                self._check_projects()
            except Exception as exc:  # noqa: BLE001 — watchdog must never crash
                get_logger().error("[watchdog] Unexpected error in poll loop: %s", exc)
        get_logger().info("[watchdog] Stopped.")

    def stop(self) -> None:
        """Signal the watchdog thread to stop cleanly."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_projects(self) -> None:
        """One full sweep across all monitored projects."""
        try:
            session = self._tmux_manager.get_or_create_session()
        except Exception as exc:  # noqa: BLE001
            get_logger().error("[watchdog] Cannot get tmux session: %s", exc)
            return

        now = time.time()

        for project in self._projects:
            name = project.name

            # Still within the 10-minute crash-loop pause window — skip.
            if self._paused_until.get(name, 0) > now:
                get_logger().info(
                    "[watchdog] '%s' is in crash-loop pause; skipping.", name
                )
                continue

            alive = self._tmux_manager.is_pane_alive(session, name)
            if alive:
                continue  # happy path — nothing to do

            # ---- Pane is dead ----------------------------------------
            get_logger().warning("[watchdog] Pane dead for project '%s'", name)

            # Prune crash times outside the rolling 10-minute window.
            recent: list[float] = [
                t for t in self._crash_times[name]
                if now - t < _CRASH_WINDOW_SECONDS
            ]

            if len(recent) > _CRASH_LOOP_THRESHOLD:   # fires at 6+ crashes
                # Crash-loop detected — enter timed 10-minute pause.
                pause_seconds = 600  # 10 minutes
                self._paused_until[name] = now + pause_seconds
                self._crash_times[name] = []  # reset so resume starts with a clean slate
                get_logger().warning(
                    "[watchdog] [%s] crash loop detected — suspending respawn for 10 minutes",
                    name,
                )
                get_logger().error(
                    "[watchdog] Crash-loop detected for '%s' (%d crashes in 10 min)",
                    name,
                    len(recent),
                )
                if self._notifier is not None:
                    self._notifier.notify(
                        project,
                        "crash_loop_detected",
                        payload={
                            "detail": (
                                f"Suspended respawning for 10 minutes after "
                                f"{_CRASH_LOOP_THRESHOLD + 1}+ crashes"
                            )
                        },
                    )
                continue

            # Safe to respawn — record this crash first.
            recent.append(now)
            self._crash_times[name] = recent

            self._respawn(session, project)

    def _respawn(self, session, project: ProjectConfig) -> None:  # noqa: ANN001
        """Kill the dead window and spin up a fresh agent pane."""
        name = project.name
        try:
            # 1. Pull latest code (tolerate failure — still respawn)
            result = self._repo_manager.clone_or_pull(project)
            if not result.success:
                get_logger().warning(
                    "[watchdog] [%s] git pull failed during respawn — continuing with existing code",
                    name,
                )

            # 2. Re-render CLAUDE.md so the agent gets fresh instructions.
            content = self._claude_launcher.render_claude_md(
                project, self._global_settings
            )
            self._claude_launcher.write_claude_md(project, content)

            # 3. Kill the stale window (it may still exist but be zombie).
            self._tmux_manager.kill_window_if_exists(session, name)

            # 4. Create a fresh window + pane and launch the agent.
            window = self._tmux_manager.create_project_window(session, project)
            self._tmux_manager.launch_agent(window, project)

            get_logger().info("[watchdog] Project '%s' respawned", name)

            if self._notifier is not None:
                self._notifier.notify(
                    project,
                    "pane_respawned",
                    payload={"detail": "Pane respawned after crash"},
                )

        except Exception as exc:  # noqa: BLE001
            get_logger().error(
                "[watchdog] Respawn failed for '%s': %s",
                name,
                exc,
            )
