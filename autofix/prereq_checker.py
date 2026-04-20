"""Prerequisite checker — verifies tmux, git, claude, and Python version."""

import shutil
import subprocess
import sys


def _run(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 1, "", "not found"
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def check_prerequisites() -> None:
    """Check all prerequisites. Calls sys.exit(2) with a message if any fail."""

    # 1. Python version >= 3.9
    if sys.version_info < (3, 9):
        print("ERROR: Python 3.9+ required.", file=sys.stderr)
        sys.exit(2)

    # 2. tmux >= 3.0
    rc, stdout, _ = _run(["tmux", "-V"])
    if rc != 0 or not stdout:
        print(
            "ERROR: tmux not found. Install with: brew install tmux (macOS) or apt install tmux (Ubuntu)",
            file=sys.stderr,
        )
        sys.exit(2)
    # Parse version string like "tmux 3.3a"
    try:
        version_str = stdout.split()[-1]
        major = int(version_str.split(".")[0])
        if major < 3:
            print(
                f"ERROR: tmux >= 3.0 required, found {version_str}. "
                "Upgrade with: brew upgrade tmux (macOS) or apt upgrade tmux (Ubuntu)",
                file=sys.stderr,
            )
            sys.exit(2)
    except (IndexError, ValueError):
        pass  # If we can't parse, accept and continue

    # 3. git
    if not shutil.which("git"):
        print("ERROR: git not found. Install from: https://git-scm.com/", file=sys.stderr)
        sys.exit(2)

    # 4. claude
    if not shutil.which("claude"):
        print("ERROR: claude CLI not found. Install from Anthropic.", file=sys.stderr)
        sys.exit(2)
