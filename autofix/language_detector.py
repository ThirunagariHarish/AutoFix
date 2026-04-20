"""Manifest-based language detection for project repositories."""

from __future__ import annotations

from pathlib import Path


def detect_language(local_path: str) -> str:
    """Detect the primary programming language of a project.

    Detection priority order (first match wins):
      1. go.mod        → "go"
      2. Gemfile       → "ruby"
      3. package.json  → "nodejs"
      4. requirements.txt | pyproject.toml | Pipfile → "python"
      5. *.py in root  → "python"
      6. *.js or *.ts  → "nodejs"
      7. else          → "unknown"

    Args:
        local_path: Absolute path to the project root.

    Returns:
        One of: "python", "nodejs", "ruby", "go", "unknown"
    """
    root = Path(local_path)

    if (root / "go.mod").exists():
        return "go"

    if (root / "Gemfile").exists():
        return "ruby"

    if (root / "package.json").exists():
        return "nodejs"

    if (
        (root / "requirements.txt").exists()
        or (root / "pyproject.toml").exists()
        or (root / "Pipfile").exists()
    ):
        return "python"

    # Fallback: scan root-level files
    try:
        root_files = list(root.iterdir())
    except (PermissionError, FileNotFoundError):
        return "unknown"

    if any(f.suffix == ".py" for f in root_files if f.is_file()):
        return "python"

    if any(f.suffix in (".js", ".ts") for f in root_files if f.is_file()):
        return "nodejs"

    return "unknown"
