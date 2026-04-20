"""Tests for autofix/notifier.py — Phase 3."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from io import BytesIO

import pytest

from autofix.notifier import Notifier, SUPPORTED_EVENTS
from autofix.config.schema import (
    ProjectConfig,
    NotificationsConfig,
    VPSConfig,
    GlobalSettings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ssh_key(tmp_path: Path) -> Path:
    key = tmp_path / "id_rsa"
    key.write_text("dummy-key")
    return key


def _make_project(
    name: str = "test-proj",
    webhook_url: str = "",
    on_events: list[str] | None = None,
    tmp_path: Path | None = None,
    *,
    notifications: NotificationsConfig | None = None,
) -> ProjectConfig:
    """Build a minimal ProjectConfig with optional notification settings."""
    if tmp_path is None:
        # Create a dummy key in /tmp for tests that don't supply tmp_path.
        key_path = "/tmp/autofix-test-key"
    else:
        key_path = str(_make_ssh_key(tmp_path))

    if notifications is None and (webhook_url or on_events is not None):
        notifications = NotificationsConfig(
            webhook_url=webhook_url or None,
            on_events=on_events or [],
        )

    return ProjectConfig(
        name=name,
        repo_url="git@github.com:org/repo.git",
        local_path="/tmp/test-proj",
        branch="main",
        vps=VPSConfig(
            host="1.2.3.4",
            user="deploy",
            ssh_key_path=key_path,
            verify_command="docker ps",
        ),
        notifications=notifications,
    )


def _make_notifier(*projects: ProjectConfig) -> Notifier:
    return Notifier(list(projects))


# Fake urllib response object that behaves like a context-manager.
class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return b""


# ---------------------------------------------------------------------------
# Basic no-op cases
# ---------------------------------------------------------------------------


class TestNotifierNoOp:
    def test_no_op_when_webhook_url_empty(self):
        """No HTTP call if webhook_url is empty string."""
        project = _make_project(
            webhook_url="",
            on_events=["fix_applied"],
        )
        notifier = _make_notifier(project)
        with patch("urllib.request.urlopen") as mock_open:
            result = notifier.notify(project, "fix_applied")
        mock_open.assert_not_called()
        assert result is False

    def test_no_op_when_webhook_url_is_none(self):
        """No HTTP call if webhook_url is None."""
        notifications = NotificationsConfig(webhook_url=None, on_events=["fix_applied"])
        project = _make_project(notifications=notifications)
        notifier = _make_notifier(project)
        with patch("urllib.request.urlopen") as mock_open:
            result = notifier.notify(project, "fix_applied")
        mock_open.assert_not_called()
        assert result is False

    def test_no_op_when_event_not_in_on_events(self):
        """No HTTP call if the event isn't in on_events."""
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],  # fix_failed is NOT listed
        )
        notifier = _make_notifier(project)
        with patch("urllib.request.urlopen") as mock_open:
            result = notifier.notify(project, "fix_failed")
        mock_open.assert_not_called()
        assert result is False

    def test_no_op_when_notifications_is_none(self):
        """No HTTP call if the project has no notifications block at all."""
        project = _make_project()  # no notifications
        notifier = _make_notifier(project)
        with patch("urllib.request.urlopen") as mock_open:
            result = notifier.notify(project, "fix_applied")
        mock_open.assert_not_called()
        assert result is False

    def test_no_op_for_project_with_no_webhook(self):
        """Project with no notifications configured → no HTTP call, returns False."""
        project = _make_project()  # no notifications block
        notifier = _make_notifier(project)
        with patch("urllib.request.urlopen") as mock_open:
            result = notifier.notify(project, "fix_applied")
        mock_open.assert_not_called()
        assert result is False

    def test_no_op_empty_on_events_list(self):
        """Empty on_events → no HTTP call even if webhook_url is set."""
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=[],
        )
        notifier = _make_notifier(project)
        with patch("urllib.request.urlopen") as mock_open:
            result = notifier.notify(project, "fix_applied")
        mock_open.assert_not_called()
        assert result is False


# ---------------------------------------------------------------------------
# Correct payload sent when event matches
# ---------------------------------------------------------------------------


class TestNotifierPayload:
    def _capture_payload(
        self,
        project: ProjectConfig,
        event: str,
        payload: dict | None = None,
    ) -> dict:
        """Helper: call notify and capture the JSON payload sent to urlopen."""
        notifier = _make_notifier(project)
        captured: list[bytes] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.data)
            return _FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            notifier.notify(project, event, payload)

        assert len(captured) == 1, "Expected exactly one HTTP call"
        return json.loads(captured[0].decode("utf-8"))

    def test_payload_project_field(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        payload = self._capture_payload(project, "fix_applied")
        assert payload["project"] == "test-proj"

    def test_payload_event_field(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        payload = self._capture_payload(project, "fix_applied")
        assert payload["event"] == "fix_applied"

    def test_payload_source_field(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        payload = self._capture_payload(project, "fix_applied")
        assert payload["source"] == "autofix"

    def test_payload_error_summary_field(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        payload = self._capture_payload(
            project, "fix_applied", payload={"error_summary": "Some error detail"}
        )
        assert payload["error_summary"] == "Some error detail"

    def test_payload_commit_sha_field(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        payload = self._capture_payload(
            project, "fix_applied", payload={"commit_sha": "abc123"}
        )
        assert payload["commit_sha"] == "abc123"

    def test_payload_verification_status_field(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        payload = self._capture_payload(
            project, "fix_applied", payload={"verification_status": "passed"}
        )
        assert payload["verification_status"] == "passed"

    def test_payload_timestamp_is_iso8601(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        payload = self._capture_payload(project, "fix_applied")
        ts = payload["timestamp"]
        # ISO 8601 timestamps contain 'T' and end with '+00:00' or 'Z'
        assert "T" in ts

    def test_payload_all_keys_present(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        payload = self._capture_payload(project, "fix_applied")
        for key in (
            "project", "event", "error_summary", "commit_sha",
            "verification_status", "timestamp", "source",
        ):
            assert key in payload, f"Missing key: {key}"

    def test_payload_empty_fields_when_no_payload_dict(self):
        """error_summary/commit_sha/verification_status default to empty string."""
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        payload = self._capture_payload(project, "fix_applied")
        assert payload["error_summary"] == ""
        assert payload["commit_sha"] == ""
        assert payload["verification_status"] == ""

    def test_correct_webhook_url_used(self):
        url = "https://hooks.example.com/xyz123"
        project = _make_project(
            webhook_url=url,
            on_events=["fix_failed"],
        )
        notifier = _make_notifier(project)
        captured_urls: list[str] = []

        def fake_urlopen(req, timeout=None):
            captured_urls.append(req.full_url)
            return _FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            notifier.notify(project, "fix_failed")

        assert captured_urls == [url]

    def test_content_type_header(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        notifier = _make_notifier(project)
        headers_seen: list[dict] = []

        def fake_urlopen(req, timeout=None):
            headers_seen.append(dict(req.headers))
            return _FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            notifier.notify(project, "fix_applied")

        assert len(headers_seen) == 1
        # Header names are capitalised by urllib.
        header_keys_lower = {k.lower() for k in headers_seen[0]}
        assert "content-type" in header_keys_lower

    def test_http_method_is_post(self):
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        notifier = _make_notifier(project)
        methods: list[str] = []

        def fake_urlopen(req, timeout=None):
            methods.append(req.method)
            return _FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            notifier.notify(project, "fix_applied")

        assert methods == ["POST"]

    def test_notify_returns_true_on_success(self):
        """notify() must return True when the HTTP call succeeds."""
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        notifier = _make_notifier(project)

        with patch("urllib.request.urlopen", return_value=_FakeResponse()):
            result = notifier.notify(project, "fix_applied")

        assert result is True

    def test_phase3_events_accepted(self):
        """Phase 3 events crash_loop_detected and pane_respawned must work."""
        for event in ("crash_loop_detected", "pane_respawned"):
            notifications = NotificationsConfig(
                webhook_url="https://hooks.example.com/abc",
                on_events=[event],
            )
            project = _make_project(notifications=notifications)
            notifier = _make_notifier(project)
            sent: list[bytes] = []

            def fake_urlopen(req, timeout=None):
                sent.append(req.data)
                return _FakeResponse()

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                notifier.notify(project, event)

            assert len(sent) == 1, f"Expected HTTP call for event '{event}'"

    def test_timeout_value_is_10_seconds(self):
        """Webhook requests must use a 10-second timeout."""
        from autofix.notifier import _TIMEOUT_SECONDS
        assert _TIMEOUT_SECONDS == 10

        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        notifier = _make_notifier(project)
        timeouts_seen: list = []

        def fake_urlopen(req, timeout=None):
            timeouts_seen.append(timeout)
            return _FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            notifier.notify(project, "fix_applied")

        assert timeouts_seen == [10]


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------


class TestNotifierExceptionHandling:
    def test_urlopen_exception_is_swallowed(self):
        """An HTTP error must NOT propagate to the caller."""
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        notifier = _make_notifier(project)
        with patch(
            "urllib.request.urlopen",
            side_effect=Exception("Network unreachable"),
        ):
            # Must NOT raise
            result = notifier.notify(project, "fix_applied")
        assert result is False

    def test_timeout_exception_is_swallowed(self):
        """Timeout errors must also be swallowed."""
        import socket

        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        notifier = _make_notifier(project)
        with patch(
            "urllib.request.urlopen",
            side_effect=socket.timeout("timed out"),
        ):
            notifier.notify(project, "fix_applied")  # must not raise

    def test_value_error_in_send_is_swallowed(self):
        """Any internal error must not propagate."""
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied"],
        )
        notifier = _make_notifier(project)
        with patch(
            "urllib.request.urlopen",
            side_effect=ValueError("bad url"),
        ):
            notifier.notify(project, "fix_applied")  # must not raise

    def test_project_with_no_notifications_does_not_raise(self):
        """notify() for a project with no notifications must return silently."""
        project = _make_project()  # no notifications
        notifier = Notifier([])
        result = notifier.notify(project, "fix_applied")  # must not raise
        assert result is False


# ---------------------------------------------------------------------------
# Multiple-project routing
# ---------------------------------------------------------------------------


class TestNotifierMultiProject:
    def test_only_correct_project_is_notified(self):
        """Events for project A must not trigger webhooks for project B."""
        proj_a = _make_project(
            name="proj-a",
            webhook_url="https://hooks.example.com/a",
            on_events=["fix_applied"],
        )
        proj_b = _make_project(
            name="proj-b",
            webhook_url="https://hooks.example.com/b",
            on_events=["fix_applied"],
        )

        notifier = Notifier([proj_a, proj_b])
        urls_called: list[str] = []

        def fake_urlopen(req, timeout=None):
            urls_called.append(req.full_url)
            return _FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            notifier.notify(proj_a, "fix_applied")

        assert urls_called == ["https://hooks.example.com/a"]

    def test_two_events_two_calls(self):
        """Two notify() calls for the same project produce two HTTP POSTs."""
        project = _make_project(
            webhook_url="https://hooks.example.com/abc",
            on_events=["fix_applied", "fix_failed"],
        )
        notifier = _make_notifier(project)
        calls: list = []

        def fake_urlopen(req, timeout=None):
            calls.append(req.data)
            return _FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            notifier.notify(project, "fix_applied")
            notifier.notify(project, "fix_failed")

        assert len(calls) == 2


# ---------------------------------------------------------------------------
# SUPPORTED_EVENTS constant
# ---------------------------------------------------------------------------


class TestSupportedEvents:
    def test_all_five_events_present(self):
        expected = {
            "fix_applied",
            "fix_failed",
            "verification_failed",
            "crash_loop_detected",
            "pane_respawned",
        }
        assert expected == set(SUPPORTED_EVENTS)
