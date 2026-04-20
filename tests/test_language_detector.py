"""Tests for autofix/language_detector.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from autofix.language_detector import detect_language


class TestDetectLanguage:
    def test_detects_go_from_go_mod(self, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module myapp\n\ngo 1.21\n")
        assert detect_language(str(tmp_path)) == "go"

    def test_detects_ruby_from_gemfile(self, tmp_path: Path):
        (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'\n")
        assert detect_language(str(tmp_path)) == "ruby"

    def test_detects_nodejs_from_package_json(self, tmp_path: Path):
        (tmp_path / "package.json").write_text('{"name": "myapp"}\n')
        assert detect_language(str(tmp_path)) == "nodejs"

    def test_detects_python_from_requirements_txt(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\nrequests\n")
        assert detect_language(str(tmp_path)) == "python"

    def test_detects_python_from_pyproject_toml(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[build-system]\nrequires = ["hatchling"]\n')
        assert detect_language(str(tmp_path)) == "python"

    def test_detects_python_from_pipfile(self, tmp_path: Path):
        (tmp_path / "Pipfile").write_text("[packages]\nflask = '*'\n")
        assert detect_language(str(tmp_path)) == "python"

    def test_detects_python_from_py_file_fallback(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        assert detect_language(str(tmp_path)) == "python"

    def test_detects_nodejs_from_js_file_fallback(self, tmp_path: Path):
        (tmp_path / "index.js").write_text("console.log('hello');\n")
        assert detect_language(str(tmp_path)) == "nodejs"

    def test_detects_nodejs_from_ts_file_fallback(self, tmp_path: Path):
        (tmp_path / "app.ts").write_text("const x: number = 1;\n")
        assert detect_language(str(tmp_path)) == "nodejs"

    def test_returns_unknown_for_empty_dir(self, tmp_path: Path):
        assert detect_language(str(tmp_path)) == "unknown"

    def test_go_has_priority_over_gemfile(self, tmp_path: Path):
        """go.mod should win over Gemfile."""
        (tmp_path / "go.mod").write_text("module myapp\n")
        (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'\n")
        assert detect_language(str(tmp_path)) == "go"

    def test_returns_unknown_for_nonexistent_path(self):
        assert detect_language("/nonexistent/path/that/does/not/exist") == "unknown"
