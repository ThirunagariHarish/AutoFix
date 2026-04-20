"""Pytest configuration and session-scoped fixtures shared across all tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def create_test_ssh_key():
    """Create /tmp/autofix-test-key so fixture YAML files that reference it pass VPS validation.

    The VPS Pydantic validator calls Path.exists() on ssh_key_path.
    Without this file the fixture projects_valid.yaml (and any test that
    loads it directly) would fail with a validation error.
    """
    key_path = Path("/tmp/autofix-test-key")
    if not key_path.exists():
        key_path.write_text("dummy-test-ssh-key\n", encoding="utf-8")
    yield
    # Leave the file in /tmp; it is ephemeral and harmless.
