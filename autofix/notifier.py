"""Webhook notifier — fire-and-forget HTTP POST on AutoFix events.

Phase 3 implementation (US-16).

Uses only stdlib (urllib.request) — no extra dependencies.
All errors are swallowed and logged at WARNING level; the notifier
must never raise exceptions to callers.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from autofix.config.schema import ProjectConfig

# Canonical set of events that AutoFix can emit.
SUPPORTED_EVENTS: frozenset[str] = frozenset({
    "fix_applied",
    "fix_failed",
    "verification_failed",
    "crash_loop_detected",
    "pane_respawned",
})

_TIMEOUT_SECONDS = 10


class Notifier:
    """Send webhook notifications for AutoFix events.

    For each ``notify()`` call the notifier:
      1. Checks whether the project has a ``webhook_url`` and whether
         the event is in ``on_events``.
      2. If both conditions hold, POSTs a JSON payload to the webhook.

    Any HTTP or network error is caught, logged at WARNING level, and
    the method returns ``False`` — it never raises.
    """

    def __init__(self, projects: list[ProjectConfig]) -> None:
        # Build a fast name→config lookup map (kept for potential future use).
        self._projects: dict[str, ProjectConfig] = {
            p.name: p for p in projects
        }
        self._logger = logging.getLogger("autofix")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def notify(
        self,
        project: ProjectConfig,
        event: str,
        payload: dict | None = None,
    ) -> bool:
        """Send a webhook notification if the event is configured for this project.

        Args:
            project: The ProjectConfig object for the project.
            event: One of SUPPORTED_EVENTS (or any string — unknown events
                   simply won't match anything in on_events and will no-op).
            payload: Optional dict with extra fields (e.g. ``error_summary``,
                     ``commit_sha``, ``verification_status``).

        Returns:
            True if notification was sent, False otherwise.
        """
        if project is None:
            return False

        notifications = project.notifications
        if notifications is None:
            return False

        webhook_url: Optional[str] = notifications.webhook_url
        if not webhook_url:
            return False

        if event not in notifications.on_events:
            return False

        # All conditions met — send the webhook.
        return self._send(project, event, payload or {}, webhook_url)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        project: ProjectConfig,
        event: str,
        payload: dict,
    ) -> bytes:
        """Serialise the notification payload to UTF-8 JSON bytes."""
        body = {
            "project": project.name,
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "autofix",
            "error_summary": payload.get("error_summary", ""),
            "commit_sha": payload.get("commit_sha", ""),
            "verification_status": payload.get("verification_status", ""),
        }
        return json.dumps(body, ensure_ascii=False).encode("utf-8")

    def _send(
        self,
        project: ProjectConfig,
        event: str,
        payload: dict,
        webhook_url: str,
    ) -> bool:
        """POST the payload to *webhook_url*; swallow all exceptions.

        Returns:
            True on HTTP success, False if an exception was caught.
        """
        try:
            data = self._build_payload(project, event, payload)
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS):
                pass  # response body is intentionally ignored
            self._logger.info(
                "[notifier] Sent '%s' notification for project '%s'",
                event,
                project.name,
            )
            return True
        except Exception as exc:  # noqa: BLE001 — must never raise
            self._logger.warning(
                "[notifier] Failed to send '%s' notification for '%s': %s",
                event,
                project.name,
                exc,
            )
            return False
