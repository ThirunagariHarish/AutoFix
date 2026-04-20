# Phase 1 Implementation Notes — AutoFix

**Phase:** 1 — Scaffold, Config, Git, tmux, Single-Project End-to-End  
**Stories:** US-01, US-02, US-03, US-04, US-12  
**Date:** 2025-01-01  
**Status:** Complete — all DoD criteria met

---

## What Changed

Phase 1 establishes the full project scaffold and working orchestration pipeline:

- **CLI entry point** (`autofix.py`) — `argparse` with `--config`, `--dry-run`, `--no-attach`, `--log-level`; implements the full startup sequence from the tech plan
- **Config layer** (`autofix/config/schema.py`, `autofix/config/loader.py`) — Pydantic v2 models for the complete `projects.yaml` schema with all specified validators; user-friendly error output with project/field context
- **Git manager** (`autofix/repo_manager.py`) — `RepoManager` class with `clone_or_pull`, `clone`, `pull`, `_build_git_env`; SSH key injection via `GIT_SSH_COMMAND`; handles missing path / non-git directory / existing repo cases
- **Tmux manager** (`autofix/tmux_manager.py`) — `TmuxManager` class wrapping libtmux; `get_or_create_session`, `create_project_window`, `launch_agent`, `is_pane_alive`, `kill_window_if_exists`, `attach_session`, `list_panes`
- **Claude launcher stub** (`autofix/claude_launcher.py`) — `ClaudeLauncher` with `generate_claude_md` / `write_claude_md` / `render_and_write`; loads real Jinja2 template if present, falls back to inline stub (Phase 2 will complete this)
- **Language detector** (`autofix/language_detector.py`) — `detect_language()` with 7-level priority chain
- **Structured logger** (`autofix/logger.py`) — `setup_logger` / `get_logger`; JSON formatter; stdout + `autofix.log` file handler
- **Prereq checker** (`autofix/prereq_checker.py`) — verifies tmux ≥3.0, git, claude, Python ≥3.9; exits with code 2 + message on failure
- **Templates** — `templates/CLAUDE.md.j2` (Phase 1 placeholder), `logging_templates/README.md`
- **Config** — `projects.yaml.example` (fully annotated, 2 projects), `.gitignore`, `README.md`, `requirements.txt`
- **Tests** — 43 unit tests across 4 test files; 4 YAML fixture files

---

## Files Touched

| File | Action |
|------|--------|
| `autofix.py` | Created |
| `requirements.txt` | Created |
| `projects.yaml.example` | Created |
| `.gitignore` | Created |
| `README.md` | Created |
| `autofix/__init__.py` | Created |
| `autofix/logger.py` | Created |
| `autofix/prereq_checker.py` | Created |
| `autofix/config/__init__.py` | Created |
| `autofix/config/schema.py` | Created |
| `autofix/config/loader.py` | Created |
| `autofix/language_detector.py` | Created |
| `autofix/repo_manager.py` | Created |
| `autofix/tmux_manager.py` | Created |
| `autofix/claude_launcher.py` | Created (Phase 1 stub) |
| `templates/CLAUDE.md.j2` | Created (Phase 1 placeholder) |
| `logging_templates/README.md` | Created |
| `tests/__init__.py` | Created |
| `tests/test_config.py` | Created |
| `tests/test_repo_manager.py` | Created |
| `tests/test_tmux_manager.py` | Created |
| `tests/test_language_detector.py` | Created |
| `tests/fixtures/projects_valid.yaml` | Created |
| `tests/fixtures/projects_invalid_missing_field.yaml` | Created |
| `tests/fixtures/projects_duplicate_name.yaml` | Created |
| `tests/fixtures/projects_unsupported_language.yaml` | Created |

---

## Tests Added

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `tests/test_config.py` | 11 | Schema validation, loader errors, happy path |
| `tests/test_repo_manager.py` | 10 | Clone, pull, clone_or_pull, env building, timeout |
| `tests/test_tmux_manager.py` | 11 | Session/window/pane lifecycle, agent launch, liveness |
| `tests/test_language_detector.py` | 11 | All 7 detection rules, priority order, edge cases |
| **Total** | **43** | **All passing** |

---

## Self-Checks Passed

| Check | Result |
|-------|--------|
| `python3 autofix.py --help` shows all flags | ✅ |
| `python3 autofix.py --dry-run --config tests/fixtures/projects_valid.yaml` exits 0 | ✅ |
| `from autofix.config.schema import GlobalSettings, ProjectConfig` imports cleanly | ✅ |
| `from autofix.tmux_manager import TmuxManager` imports cleanly | ✅ |
| `python3 -m pytest tests/ -v` — 43/43 pass | ✅ |
| All files present in correct locations | ✅ |

---

## Deviations from Tech Plan

1. **`Optional[logging.Logger]` vs `logging.Logger | None`** — Used `Optional` type annotation in `logger.py` for Python 3.9 compatibility (the `X | Y` union syntax for type hints requires Python 3.10+). No functional change.

2. **`sys.exit(2, "message")` pattern** — The tech plan implied `sys.exit(2)` with a message. `sys.exit()` only accepts one argument; implemented as `print(..., file=sys.stderr); sys.exit(2)` which achieves identical behavior.

3. **`autofix/logger.py` type annotation** — Used `from __future__ import annotations` to avoid the `Optional` import issue at runtime while keeping the annotation readable.

4. **`projects.yaml.example` VPS fields** — Added `docker_container_name` and `docker_compose_path` fields to the example (present in the PRD schema but not explicitly in the Pydantic `VPSConfig` model). These are informational comments for Phase 2 agent use; the Pydantic model only validates what the orchestrator directly uses.

---

## Open Risks

1. **libtmux API stability** — The `session.sessions.get(session_name=...)` and `session.windows.get(window_name=...)` filter API differs between libtmux versions. Pinned to `>=0.28` in requirements.txt. If the API changes, `tmux_manager.py` needs updating.

2. **`pane.dead` property** — The tech plan specifies using `pane.dead` from libtmux ≥0.28. `is_pane_alive` has a `hasattr` guard that falls back to `True` for older versions. Verify against installed version before production use.

3. **SSH key validation at config load time** — `VPSConfig.ssh_key_path` validator checks file existence at `model_validate()` time. If running in CI or an environment where SSH keys are provisioned at runtime (not at config-load time), this will fail. Mitigation: operators can set `vps.enabled: false` for such projects.

4. **`CLAUDE.md` write fails silently** — Per the startup sequence, a CLAUDE.md write failure logs a warning but does not abort the project launch. This is intentional for Phase 1 (where the template is a stub), but Phase 2 should consider making this a hard failure.

---

## Ready for Cortex Review

Phase 1 is complete. All AC criteria from the tech plan are satisfied by unit tests and manual self-checks. Ready for Cortex code review before proceeding to Phase 2.
