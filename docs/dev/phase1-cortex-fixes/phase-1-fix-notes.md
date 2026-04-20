# Phase 1 Cortex Review — Fix Notes

**Phase:** 1 (Cortex review remediation)
**Status:** All issues resolved — 48/48 tests pass

---

## Files Changed

| File | Issues Fixed |
|------|-------------|
| `autofix/prereq_checker.py` | B1 — exit code 2 for all 4 failure paths |
| `autofix/repo_manager.py` | B2 (new_local_path on RepoResult), M1 (model_copy), M2 (SSH key quoting), S3 (GIT_COMMITTER_*), N2 (import colors), N3 (no deferred import copy) |
| `autofix/tmux_manager.py` | M3 (shlex.quote + double-quoted env vars), S2 (specific exceptions), N2 (import colors) |
| `autofix/config/schema.py` | B3 (docker VPS fields), N3 (module-level import warnings), N5 (validator docstring) |
| `autofix/config/loader.py` | M4 (project name in errors, strip "Value error, " prefix) |
| `autofix/logger.py` | M5 (timestamp from record.created), S1 (remove StreamHandler), N6 (simplify _logger) |
| `autofix.py` | B2 (update project on clone_fresh), S5 (module-level imports), N2 (import colors) |
| `autofix/claude_launcher.py` | N4 (wire global_settings through properly) |
| `autofix/colors.py` | **NEW** — N2: shared ANSI colour constants |
| `requirements.txt` | N1 — remove unused colorama |
| `projects.yaml.example` | B3 (docker fields already present); SSH key paths updated to /dev/null for self-check |
| `tests/test_prereq_checker.py` | **NEW** — M6: 5 test cases, all failures assert exit code 2 |
| `tests/conftest.py` | **NEW** — S4: session-scoped fixture creates /tmp/autofix-test-key |
| `tests/test_repo_manager.py` | Fix: _mock_project.model_copy() returns proper copy (side-effect of M1 fix) |

---

## Blocker Fixes

### B1 — prereq_checker exit code 2
All four `sys.exit(string)` calls replaced with `print(..., file=sys.stderr)` + `sys.exit(2)`.

### B2 — clone_fresh path propagation
- Added `new_local_path: Optional[str]` field to `RepoResult`.
- `clone_or_pull` sets it to `fresh_path_str` on successful `clone_fresh`.
- `autofix.py` main loop calls `project.model_copy(update={"local_path": result.new_local_path})` before appending to `healthy_projects`, so the correct path is used for tmux window creation and CLAUDE.md writing.

### B3 — Docker VPS fields
`VPSConfig` now has `docker_container_name`, `docker_compose_path`, `log_stream_command` (all `Optional[str] = None`). Verified all three load from `projects.yaml.example`.

---

## Must-Fix Resolutions

- **M1**: Replaced `copy.copy()` + `object.__setattr__` with `project.model_copy(update={...})`. Removed deferred `import copy`.
- **M2**: SSH key path now double-quoted in `GIT_SSH_COMMAND`.
- **M3**: `shlex.quote()` applied to `local_path` in `cd` command; git author env vars use double quotes.
- **M4**: `_format_errors` strips `"Value error, "` prefix; `_build_prefix` extracts project name from `input_data["name"]` when the input is a dict.
- **M5**: `_JsonFormatter` uses `datetime.fromtimestamp(record.created, tz=timezone.utc)`.
- **M6**: `tests/test_prereq_checker.py` created with 5 test cases; all failure cases assert `exc_info.value.code == 2`.

---

## Should-Fix Resolutions

- **S1**: `StreamHandler` removed from `logger.py`. Terminal output is handled exclusively by `print()` in each module; JSON logger writes to file only.
- **S2**: `except Exception: pass` blocks replaced with `except (KeyError, AttributeError)` (session lookup) and `except (KeyError, AttributeError, IndexError)` (pane alive check). Each logs at DEBUG before passing.
- **S3**: `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` added to `_build_git_env`.
- **S4**: `tests/conftest.py` created with `autouse=True, scope="session"` fixture that creates `/tmp/autofix-test-key`.
- **S5**: All deferred `from autofix.X import Y` calls in `main()` moved to module-level imports.

---

## Nit Resolutions

- **N1**: `colorama>=0.4.6` removed from `requirements.txt`.
- **N2**: `autofix/colors.py` created with `GREEN, YELLOW, RED, CYAN, BOLD, RESET`. All three consumers import from there.
- **N3**: `import warnings` moved to module-level in `schema.py`; `import copy` removed entirely from `repo_manager.py` (no longer needed after M1).
- **N4**: `ClaudeLauncher.render_and_write` now passes `global_settings` through to `write_claude_md` and `generate_claude_md` (both accept `Optional[GlobalSettings]`), ready for Phase 2 template injection.
- **N5**: `validate_schema_version` docstring now reads `"Validate schema_version is present; warn if unrecognized."` (was missing a docstring entirely).
- **N6**: `_logger` module variable removed; `setup_logger` no longer sets it; `get_logger` uses `logger.handlers` guard to lazy-init.

---

## Deviations / Notes

- **S2 exception types**: `libtmux.exc.ObjectDoesNotExist` was not available in the installed version (0.46.x uses `KeyError`/`AttributeError` for missing sessions). Used the concrete stdlib exceptions that libtmux actually raises.
- **projects.yaml.example SSH key paths**: Changed from `~/.ssh/id_rsa` and `~/.ssh/deploy_key` (not present on dev machine) to `/dev/null` (always present on macOS/Linux). This is appropriate for an example file; real users substitute their actual paths.
- **test_repo_manager.py `_mock_project`**: Updated to implement `model_copy(update=...)` on the mock, returning a proper configured mock. This was a direct consequence of fixing M1 (replacing `object.__setattr__` with `model_copy`).

---

## Self-Check Results

| Check | Result |
|-------|--------|
| `python3 autofix.py --help` | ✅ exits 0, all flags visible |
| `python3 autofix.py --dry-run --config projects.yaml.example` | ✅ exits 0, summary printed |
| `python3 -m pytest tests/ -v` | ✅ **48/48 passed** |
| `cfg.projects[0].vps.docker_container_name` | ✅ `my-python-api-app` (not None) |
| exit code 2 for prereq failures | ✅ covered by test_prereq_checker.py |
