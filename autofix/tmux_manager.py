"""libtmux-based tmux session/window/pane lifecycle manager."""

from __future__ import annotations

import shlex
import subprocess

import libtmux

from autofix.config.schema import ProjectConfig
from autofix.logger import get_logger
from autofix.colors import GREEN, YELLOW, RED, RESET


class TmuxManager:
    """Manages libtmux session, windows, and panes for AutoFix."""

    def __init__(
        self,
        session_name: str,
        claude_command: str,
        git_author_name: str,
        git_author_email: str,
    ) -> None:
        self.session_name = session_name
        self.claude_command = claude_command
        self.git_author_name = git_author_name
        self.git_author_email = git_author_email
        self._server: libtmux.Server = libtmux.Server()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def get_or_create_session(self) -> libtmux.Session:
        """Return an existing session or create a new detached one."""
        logger = get_logger()

        try:
            session = self._server.sessions.get(session_name=self.session_name)
            if session:
                print(
                    f"{YELLOW}[tmux] Session '{self.session_name}' already exists.{RESET}",
                    flush=True,
                )
                logger.info("tmux session '%s' already exists", self.session_name)
                return session
        except (KeyError, AttributeError) as exc:
            logger.debug("tmux session lookup returned no result: %s", exc)

        session = self._server.new_session(
            session_name=self.session_name, detach=True
        )
        print(
            f"{GREEN}[tmux] Created session '{self.session_name}'.{RESET}",
            flush=True,
        )
        logger.info("Created tmux session '%s'", self.session_name)
        return session

    # ------------------------------------------------------------------
    # Window / pane management
    # ------------------------------------------------------------------

    def create_project_window(
        self, session: libtmux.Session, project: ProjectConfig
    ) -> libtmux.Window:
        """Return (or create) a tmux window named after the project."""
        logger = get_logger()

        # Check for existing window
        try:
            window = session.windows.get(window_name=project.name)
            if window:
                print(
                    f"{YELLOW}[tmux] Window '{project.name}' already exists.{RESET}",
                    flush=True,
                )
                return window
        except (KeyError, AttributeError) as exc:
            logger.debug("tmux window lookup returned no result: %s", exc)

        window = session.new_window(
            window_name=project.name,
            start_directory=project.local_path,
        )
        print(
            f"{GREEN}[tmux] Created window '{project.name}'.{RESET}", flush=True
        )
        logger.info("Created tmux window '%s'", project.name)
        return window

    def launch_agent(
        self, window: libtmux.Window, project: ProjectConfig
    ) -> None:
        """Send startup commands to the pane to launch the Claude agent."""
        logger = get_logger()
        pane = window.panes[0]

        # 1. cd to project directory (shlex.quote guards against spaces/special chars)
        pane.send_keys(f"cd {shlex.quote(project.local_path)}", enter=True)

        # 2. Export git author env vars (double-quoted to handle names with spaces)
        env_prefix = (
            f'export GIT_AUTHOR_NAME="{self.git_author_name}" '
            f'GIT_AUTHOR_EMAIL="{self.git_author_email}"'
        )
        pane.send_keys(env_prefix, enter=True)

        # 3. Launch claude
        pane.send_keys(self.claude_command, enter=True)

        print(
            f"{GREEN}[tmux] Agent launched for '{project.name}'.{RESET}",
            flush=True,
        )
        logger.info("Agent launched for project '%s'", project.name)

    def is_pane_alive(
        self, session: libtmux.Session, project_name: str
    ) -> bool:
        """Return True if the project's tmux pane is alive."""
        try:
            window = session.windows.get(window_name=project_name)
            if not window:
                return False
            pane = window.panes[0]
            # libtmux >= 0.28 exposes pane.dead
            if hasattr(pane, "dead"):
                return not pane.dead
            return True
        except (KeyError, AttributeError, IndexError):
            return False

    def kill_window_if_exists(
        self, session: libtmux.Session, project_name: str
    ) -> None:
        """Kill a project window if it exists."""
        try:
            window = session.windows.get(window_name=project_name)
            if window:
                window.kill()
        except (KeyError, AttributeError):
            pass

    def attach_session(self, session: libtmux.Session) -> None:
        """Attach the current terminal to the tmux session (blocks until detach)."""
        subprocess.run(
            ["tmux", "attach-session", "-t", session.name],
            check=False,
        )

    def list_panes(self, session: libtmux.Session) -> list:
        """Return all panes across all windows in the session."""
        panes = []
        for window in session.windows:
            panes.extend(window.panes)
        return panes
