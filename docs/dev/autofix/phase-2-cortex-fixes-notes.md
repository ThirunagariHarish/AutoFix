# Phase 2 Cortex Review Fix Notes

**Phase:** 2 (Cortex review resolutions)  
**Date:** 2025-01-01  
**Author:** Devin

---

## Summary

Resolved all issues flagged in the Cortex review of Phase 2: 1 blocker, 5 must-fixes, 2 should-fixes, and 5 nits.

---

## Changes Made

### BLK-1 — Go logging: keep `zap` (user confirmed)
- **`docs/architecture/tech-plan.md`**: Updated Files-to-Create table (`go_zerolog.go` → `go_zap.go`) and language→framework mapping (`zerolog` → `zap`).
- **`docs/architecture/architecture.md`**: Updated component diagram label (`go_zerolog.go` → `go_zap.go`).
- No code change needed — `_FRAMEWORK_MAP["go"] = "zap"` and `go_zap.go` were already correct in Phase 2.

### MF-1 — Phase 1 sentinel must use `.autofix_init`, not `log.md`
- **`templates/CLAUDE.md.j2`** Section 3 (Check-first block): Changed `log.md` sentinel to `.autofix_init`.
- **`templates/CLAUDE.md.j2`** Step 3e (`.gitignore` instructions): Added `.autofix_init` to the gitignore block with a note that it is a local machine sentinel and must NOT be committed.
- **`templates/CLAUDE.md.j2`** Step 6: Rewrote to commit only `log.md`, then separately write `.autofix_init` with `initialized_at: <ISO timestamp>` content (not git-added).
- **`tests/test_claude_launcher.py`**: Added `TestSentinelFile` class (4 tests) asserting `.autofix_init` is the sentinel in the Check-first block, Step 6 writes it, and it appears in `.gitignore` instructions.

### MF-2 — `write_claude_md` signature accepts pre-rendered content
- **`autofix/claude_launcher.py`**: Split old `write_claude_md(project, global_settings)` into:
  - `write_claude_md(project, content: str) -> Path` — writes pre-rendered content (Phase 3 watchdog API)
  - `render_and_write_to_disk(project, global_settings) -> Path` — render + write combo
- Updated `render_and_write` alias to call `render_and_write_to_disk`.
- **`tests/test_claude_launcher.py`**: Updated `TestWriteClaudeMd` (4 existing tests) to use new two-step `generate_claude_md` + `write_claude_md` API. Added 2 new tests for `render_and_write_to_disk` and `render_claude_md` alias.

### MF-3 — Add `render_claude_md` as stable alias
- **`autofix/claude_launcher.py`**: Added `render_claude_md(project, global_settings) -> str` as a stable public alias for `generate_claude_md`.
- **`tests/test_claude_launcher.py`**: `test_render_claude_md_alias` asserts output equals `generate_claude_md`.

### MF-4 — Guard SSH streaming block with `{% if vps_enabled %}`
- **`templates/CLAUDE.md.j2`** Section 6 (log.md format template): Wrapped the `## SSH Log Streaming` block in `{% if vps_enabled %}...{% else %}...{% endif %}`. The else branch shows `tail -f {{ local_path }}/{{ log_path }}`.
- Prevents malformed `deploy@ ` SSH commands for VPS-disabled projects.
- **`tests/test_claude_launcher.py`**: Added `TestVpsDisabledNoSshCommands` class (3 tests) asserting no `deploy@ ` appears, `tail -f` appears, and VPS-enabled still shows `ssh -i`.

### MF-5 — SSH Docker log streaming is intentional — document it
- **`docs/architecture/architecture.md`**: Added a "Note — Log Stream Method" callout after the auto-fix cycle sequence diagram, explaining SSH Docker streaming (`vps.enabled=True`) vs local `tail -F` (`vps.enabled=False`).
- **`docs/architecture/tech-plan.md`**: Replaced the vague `2. Tail … for new lines` spec with a detailed conditional spec showing both SSH streaming and local tail commands.
- **`projects.yaml.example`**: Enhanced inline comments for `docker_container_name`, `docker_compose_path`, and `log_stream_command` explaining they are used by the Claude agent for Docker log streaming via SSH.

### SF-1 — Loguru nested schema note for monitoring loop detection
- **`logging_templates/python_loguru.py`**: Added prominent `IMPORTANT FOR AUTOFIX MONITORING` comment explaining loguru's `serialize=True` nested JSON format and the dual field-path check.
- **`templates/CLAUDE.md.j2`** Section 5.3a–b: Updated per-line parsing to explicitly list level field paths in order (`line["level"]` → `line["record"]["level"]["name"]` → `line["levelname"]`). Updated `b. Extract fields` to include all three level paths and `line["text"]` for loguru's top-level text field.

### SF-2 — Remove unused `config_path` parameter
- **`autofix.py`**: Removed `config_path: str` parameter from `_dry_run_render_claude_mds`. Updated the single call site to omit the argument.

### N-1 — Wire sample_project_python into a test
- **`tests/test_claude_launcher.py`**: Added `TestSampleProjectFixture.test_sample_project_python_detected_as_python` asserting `detect_language` returns `"python"` for `tests/fixtures/sample_project_python/`.

### N-2 — Change commit tag from `[autofix-setup]` to `[autofix]`
- **`templates/CLAUDE.md.j2`**: Changed `[autofix-setup]` → `[autofix]` in all commit messages (Step 4 logging standardization commit, Step 6 log.md commit) and in the Safety Rules commit format table.

### N-3 — Remove double blank line at autofix.py:126
- **`autofix.py`**: Removed extra blank line between `_dry_run_render_claude_mds` and `_print_dry_run_summary`.

### N-4 — Broaden Jinja2 unrendered tag regex in tests
- **`tests/test_claude_launcher.py`**: Changed `r"\{\{(?!\s*'|\s*\")"` to `r"\{\{.*?\}\}"` in `TestNoUnrenderedJinjaTags`. This catches any remaining `{{ }}` pattern the old negative-lookahead missed.

### N-5 — Add comment in python_structlog.py noting `event` key
- **`logging_templates/python_structlog.py`**: Added `IMPORTANT FOR AUTOFIX MONITORING` comment explaining structlog uses `event` (not `message`) and how AutoFix maps it when parsing log lines.

---

## Files Touched

| File | Change type |
|---|---|
| `autofix/claude_launcher.py` | MF-2, MF-3 |
| `autofix.py` | SF-2, N-3 |
| `templates/CLAUDE.md.j2` | MF-1, MF-4, SF-1, N-2 |
| `tests/test_claude_launcher.py` | MF-1 tests, MF-2 tests, MF-4 tests, N-1, N-4 |
| `logging_templates/python_loguru.py` | SF-1 |
| `logging_templates/python_structlog.py` | N-5 |
| `docs/architecture/architecture.md` | BLK-1 (diagram), MF-5 |
| `docs/architecture/tech-plan.md` | BLK-1, MF-5 |
| `projects.yaml.example` | MF-5 |

---

## Tests Added

- `TestSentinelFile` (4 tests) — MF-1
- `TestVpsDisabledNoSshCommands` (3 tests) — MF-4
- `TestSampleProjectFixture` (1 test) — N-1
- `TestWriteClaudeMd.test_render_and_write_to_disk` — MF-2
- `TestWriteClaudeMd.test_render_claude_md_alias` — MF-3

**Total tests:** 116 (all pass)

---

## Self-Check Results

1. `python3 -m pytest tests/ -v` → **116 passed in 0.49s**
2. Sentinel check → **`.autofix_init` found 4× in rendered CLAUDE.md; `deploy@ ` absent for VPS-disabled project**
3. `python3 autofix.py --dry-run --config projects.yaml.example` → **exit 0, 23,431 chars rendered**

---

## Deviations from Spec

None. All changes implement exactly what was specified in the Cortex review.

---

## Open Risks

None. All Cortex review items resolved. Ready for Cortex re-review.
