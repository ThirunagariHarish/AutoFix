# Technical Implementation Plan — AutoFix

**Version:** 1.0  
**Author:** Atlas (Architect)  
**Date:** 2025-01-01  
**Architecture:** `docs/architecture/architecture.md`  
**PRD:** `docs/product/autofix/PRD.md`

---

## Overview

AutoFix is implemented in three phases. Each phase produces a self-contained, testable increment. Devin implements one phase at a time and must not begin a subsequent phase until the prior phase's DoD is fully met.

| Phase | Theme | Stories Covered | Key Deliverable |
|---|---|---|---|
| **Phase 1** | Scaffold + Config + Git + tmux + Single-project end-to-end | US-01, US-02, US-03, US-04, US-12 | Working orchestrator that starts one project in tmux |
| **Phase 2** | CLAUDE.md template + Agent instructions + Logging templates | US-05, US-06, US-07, US-08, US-09, US-13, US-17 | Claude agent fully instrumented with all language templates |
| **Phase 3** | Watchdog + Notifications + Dry-run + Hardening | US-10, US-11, US-14, US-15, US-16, US-18 | Production-ready multi-project system with auto-recovery |

---

## Phase 1 — Scaffold, Config, Git, tmux, Single-Project End-to-End

### Goal
A working orchestrator that: reads and validates `projects.yaml`, clones/pulls a single project's Git repo, creates a tmux session with one window for that project, and launches `claude --dangerously-skip-permissions` in that window. No agent intelligence yet — just the infrastructure scaffolding.

### Stories Covered
- **US-01** (P0): Single-command startup
- **US-02** (P0): Config-driven project definition
- **US-03** (P0): Automatic repo clone/pull
- **US-04** (P0): Per-project tmux pane
- **US-12** (P1): Config validation with actionable errors

### Files to Create

| File | Purpose |
|---|---|
| `autofix.py` | Orchestrator entry point |
| `autofix/__init__.py` | Package init |
| `autofix/logger.py` | Orchestrator structured logging |
| `autofix/prereq_checker.py` | tmux / claude / git prerequisite checks |
| `autofix/config/__init__.py` | Config subpackage init |
| `autofix/config/schema.py` | All Pydantic v2 models |
| `autofix/config/loader.py` | YAML load + validate |
| `autofix/repo_manager.py` | git clone / git pull |
| `autofix/tmux_manager.py` | libtmux session/window/pane lifecycle |
| `autofix/language_detector.py` | Manifest-based language detection |
| `requirements.txt` | Pinned deps: pyyaml, pydantic, jinja2, libtmux, requests |
| `projects.yaml.example` | Documented example config |
| `.gitignore` | Exclude: `projects.yaml`, `autofix.log`, `__pycache__`, `*.pyc` |
| `tests/__init__.py` | Test package |
| `tests/test_config.py` | Config schema + loader tests |
| `tests/test_repo_manager.py` | Git operation tests |
| `tests/test_tmux_manager.py` | TmuxManager unit tests |
| `tests/test_language_detector.py` | Language detection tests |
| `tests/fixtures/projects_valid.yaml` | Valid multi-project fixture |
| `tests/fixtures/projects_invalid_missing_field.yaml` | Missing required field fixture |
| `tests/fixtures/projects_duplicate_name.yaml` | Duplicate name fixture |
| `tests/fixtures/projects_unsupported_language.yaml` | Invalid language fixture |

### Dependencies on Prior Phases
None — this is Phase 1.

### Detailed Specifications

---

#### `autofix/config/schema.py`

Define the following Pydantic v2 models. All optional fields must have explicit defaults.

**`GlobalSettings` model:**
```
Fields:
  tmux_session_name: str = "autofix"
  watchdog_interval_seconds: int = 60        # > 0
  claude_command: str = "claude --dangerously-skip-permissions"
  git_author_name: str = "AutoFix Agent"
  git_author_email: str = "autofix@local"
  log_dir: str = "./logs"
```

**`VPSConfig` model:**
```
Fields:
  host: str                                  # Required
  user: str                                  # Required
  ssh_key_path: str                          # Required; ~ expanded; existence validated
  verify_command: str                        # Required
  verify_output_contains: Optional[str] = None
  verify_timeout_seconds: int = 30           # > 0
  enabled: bool = True                       # Set False for CI/CD-deployed projects
```

**`GitConfig` model:**
```
Fields:
  push_branch: Optional[str] = None          # Defaults to project.branch at runtime
  pull_before_fix: bool = True
  commit_sign: bool = False
```

**`MonitoringConfig` model:**
```
Fields:
  error_debounce_minutes: int = 5            # >= 1
  max_fixes_per_hour: int = 3               # 1 <= x <= 20
  blocked_patterns: list[str] = []
```

**`NotificationsConfig` model:**
```
Fields:
  webhook_url: Optional[str] = None
  on_events: list[str] = []                  # Valid values: fix_applied, fix_failed, verification_failed
```

**`ProjectConfig` model:**
```
Fields:
  name: str                                  # Required; matches pattern [a-zA-Z0-9_-]+
  repo_url: str                              # Required
  local_path: str                            # Required; must be absolute path
  branch: str = "main"
  language: str = "auto"                     # python|nodejs|ruby|go|auto
  log_path: str = "logs/app.log"
  vps: VPSConfig                             # Required
  git: GitConfig = GitConfig()
  monitoring: MonitoringConfig = MonitoringConfig()
  notifications: Optional[NotificationsConfig] = None
```

**`AutoFixConfig` (root model):**
```
Fields:
  schema_version: str                        # Required; warn if != "1.0"
  global_settings: GlobalSettings = GlobalSettings()    # key in YAML: "global"
  projects: list[ProjectConfig]              # Required; 1 <= len <= 10; names must be unique
```

**Validation rules (implement as Pydantic validators):**
1. `local_path` must be an absolute path (starts with `/`). Error: `"local_path must be an absolute path: {value}"`
2. `language` must be one of: `["python", "nodejs", "ruby", "go", "auto"]`. Error: `"Unsupported language '{value}'. Must be one of: python, nodejs, ruby, go, auto"`
3. `ssh_key_path`: expand `~`, check file exists at validation time. Error: `"SSH key not found: {resolved_path}"`
4. `max_fixes_per_hour` must be 1–20. Error: `"max_fixes_per_hour must be between 1 and 20"`
5. `projects` list: names must be unique. Error: `"Duplicate project name: {name}"`
6. `projects` list: length must be 1–10. Error: `"Too many projects: {n}. Maximum supported in v1 is 10."`
7. `schema_version` must be present. Error: `"schema_version is required"`
8. YAML key `global` must map to `global_settings` field (use `model_config` alias).

---

#### `autofix/config/loader.py`

**Function: `load_config(config_path: str) -> AutoFixConfig`**

Steps:
1. Check file exists at `config_path`. If not: raise `ConfigFileNotFoundError(f"projects.yaml not found at {config_path}")`.
2. Open and parse YAML. If YAML parse error: raise `ConfigParseError(f"YAML parse error in {config_path}: {e}")` with line number.
3. Call `AutoFixConfig.model_validate(data)`. If `ValidationError`: raise `ConfigValidationError` containing all field errors formatted as:
   ```
   Config validation failed:
     [project: my-api] local_path must be an absolute path: 'relative/path'
     [project: my-api] SSH key not found: /home/user/.ssh/missing_key
     [global] max_fixes_per_hour must be between 1 and 20
   ```
4. Return validated `AutoFixConfig`.

**Custom exception classes to define (in `autofix/config/loader.py`):**
- `ConfigFileNotFoundError(Exception)`
- `ConfigParseError(Exception)`
- `ConfigValidationError(Exception)` — stores list of error strings

---

#### `autofix/prereq_checker.py`

**Function: `check_prerequisites() -> None`**

Check in order:
1. `tmux -V` — parse version >= 3.0. If missing: `SystemExit("ERROR: tmux not found. Install with: brew install tmux (macOS) or apt install tmux (Ubuntu)")`
2. `which git` — if not found: `SystemExit("ERROR: git not found. Install from: https://git-scm.com/")`
3. `which claude` — if not found: `SystemExit("ERROR: claude CLI not found. Install from Anthropic.")`
4. Python version >= 3.9 (check `sys.version_info`). If not: `SystemExit("ERROR: Python 3.9+ required.")`

All `SystemExit` calls use exit code 2.

---

#### `autofix/repo_manager.py`

**`RepoResult` dataclass:**
```
@dataclass
class RepoResult:
    success: bool
    action: str          # "clone" | "pull" | "skip"
    project_name: str
    error: Optional[str] = None
```

**`RepoManager` class:**

Constructor: `__init__(self, git_author_name: str, git_author_email: str)`

Methods:

**`clone_or_pull(project: ProjectConfig) -> RepoResult`:**
- If `local_path` directory does not exist → call `self.clone(project)`
- If `local_path` exists but is not a git repo (no `.git/`) → log warning; attempt clone to `{local_path}_fresh_{timestamp}` → return result with action `"clone_fresh"`
- If `local_path` exists and is a git repo → call `self.pull(project)`

**`clone(project: ProjectConfig) -> RepoResult`:**
- Command: `git clone --branch {branch} {repo_url} {local_path}`
- Timeout: 120 seconds
- On success: `RepoResult(success=True, action="clone", project_name=project.name)`
- On failure: `RepoResult(success=False, action="clone", project_name=project.name, error=stderr)`

**`pull(project: ProjectConfig) -> RepoResult`:**
- Command: `git pull origin {branch}` with cwd=`local_path`
- Timeout: 60 seconds
- On success: `RepoResult(success=True, action="pull", project_name=project.name)`
- On failure: `RepoResult(success=False, action="pull", project_name=project.name, error=stderr)`

**`_build_git_env(project: ProjectConfig) -> dict`:**
- Returns a copy of `os.environ` with:
  - `GIT_AUTHOR_NAME = self.git_author_name`
  - `GIT_AUTHOR_EMAIL = self.git_author_email`
  - `GIT_SSH_COMMAND = "ssh -i {expanded_ssh_key_path} -o StrictHostKeyChecking=no -o BatchMode=yes"`
  - `GIT_TERMINAL_PROMPT = "0"` (prevents interactive credential prompts)

---

#### `autofix/tmux_manager.py`

**`TmuxManager` class:**

Constructor: `__init__(self, session_name: str, claude_command: str, git_author_name: str, git_author_email: str)`

Private: `self._server: libtmux.Server = libtmux.Server()`

Methods:

**`get_or_create_session() -> libtmux.Session`:**
- Try `self._server.find_where({"session_name": self.session_name})`
- If found: return it (log "session exists, attaching")
- If not: return `self._server.new_session(session_name=self.session_name, detach=True)`

**`create_project_window(session: libtmux.Session, project: ProjectConfig) -> libtmux.Window`:**
- Check if window named `project.name` already exists: `session.find_where({"window_name": project.name})`
- If exists: return it (idempotent)
- If not: `session.new_window(window_name=project.name, start_directory=project.local_path)`
- Return window

**`launch_agent(window: libtmux.Window, project: ProjectConfig) -> None`:**
- Get first pane: `pane = window.panes[0]`
- Send sequence of commands:
  1. `pane.send_keys(f"cd {project.local_path}", enter=True)`
  2. Build env prefix: `f"export GIT_AUTHOR_NAME='{self.git_author_name}' GIT_AUTHOR_EMAIL='{self.git_author_email}'"`
  3. `pane.send_keys(env_prefix, enter=True)`
  4. `pane.send_keys(self.claude_command, enter=True)`

**`is_pane_alive(session: libtmux.Session, project_name: str) -> bool`:**
- Find window: `session.find_where({"window_name": project_name})`
- If window not found: return `False`
- Get pane: `window.panes[0]`
- Check: `not pane.dead` (libtmux >= 0.28 provides `pane.dead` property)
- Return result

**`kill_window_if_exists(session: libtmux.Session, project_name: str) -> None`:**
- Find window by name; if found call `window.kill_window()`

**`attach_session(session: libtmux.Session) -> None`:**
- Call `subprocess.run(["tmux", "attach-session", "-t", session.name])`
- This blocks until the operator detaches from tmux (Ctrl+B then D)

---

#### `autofix/language_detector.py`

**Function: `detect_language(local_path: str) -> str`**

Returns one of: `"python"`, `"nodejs"`, `"ruby"`, `"go"`, `"unknown"`

Detection logic (priority order — check for file existence):
1. `go.mod` → `"go"`
2. `Gemfile` → `"ruby"`
3. `package.json` → `"nodejs"`
4. `requirements.txt` OR `pyproject.toml` OR `Pipfile` → `"python"`
5. `*.py` files in root (any) → `"python"` (fallback)
6. `*.js` or `*.ts` files in root → `"nodejs"` (fallback)
7. Else → `"unknown"`

---

#### `autofix.py` — Main Entry Point

**CLI:** Use `argparse`.

Arguments:
- `--config`: path to `projects.yaml` (default: `./projects.yaml`)
- `--dry-run`: flag; if set, validate config + show plan, then exit 0 without side effects
- `--no-attach`: flag; if set, don't attach to tmux after launch (useful for background/daemon use)
- `--log-level`: `DEBUG|INFO|WARNING|ERROR` (default: `INFO`)

**Startup sequence (implement as `main()` function):**

```
1. Parse args
2. Initialize logger (autofix/logger.py) → writes to stdout + autofix.log
3. check_prerequisites() → exit(2) on failure
4. load_config(args.config) → exit(1) on failure; print errors
5. If --dry-run: print validated config summary, exit(0)
6. Initialize RepoManager, TmuxManager, ClaudeLauncher
7. For each project in config.projects:
     a. result = repo_manager.clone_or_pull(project)
     b. If result.success is False: log error; add to failed_projects list; continue
     c. claude_launcher.render_and_write(project, config.global_settings)
     d. Log: "CLAUDE.md written to {project.local_path}/CLAUDE.md"
8. If all projects failed: exit(3)
9. session = tmux_manager.get_or_create_session()
10. For each project NOT in failed_projects:
      a. window = tmux_manager.create_project_window(session, project)
      b. tmux_manager.launch_agent(window, project)
      c. Log: "Agent launched for {project.name}"
11. (Phase 3: start watchdog thread here)
12. If not --no-attach: tmux_manager.attach_session(session)
13. Else: print(f"tmux session '{session_name}' running. Attach with: tmux attach -t {session_name}")
```

---

#### `autofix/logger.py`

**Function: `setup_logger(log_level: str, log_dir: str) -> logging.Logger`**

- Creates a Python `logging.Logger` named `"autofix"`
- Adds two handlers:
  1. `StreamHandler(sys.stdout)` — for terminal visibility
  2. `FileHandler(f"{log_dir}/autofix.log")` — for persistence
- Both handlers use a JSON formatter that produces:
  ```json
  {"ts": "...", "level": "INFO", "component": "orchestrator", "event": "...", "detail": "..."}
  ```
- Returns the logger

**Function: `get_logger() -> logging.Logger`** — returns the global `"autofix"` logger.

---

#### `projects.yaml.example`

Produce a fully commented example with two projects (one Python, one Node.js) showing every possible field with inline comments explaining each field's purpose and valid values. This file is the primary user-facing documentation for config.

---

### Phase 1 Acceptance Criteria (DoD)

All of the following must be true before Devin moves to Phase 2:

**AC-1.1** Running `python autofix.py --config tests/fixtures/projects_valid.yaml --dry-run` exits 0 and prints a human-readable summary of the loaded config without creating any tmux session or running git operations.

**AC-1.2** Running `python autofix.py --config nonexistent.yaml` exits 1 with message: `"ERROR: projects.yaml not found at nonexistent.yaml"`.

**AC-1.3** Running `python autofix.py --config tests/fixtures/projects_invalid_missing_field.yaml` exits 1 and prints an error message identifying the project name and missing field.

**AC-1.4** Running `python autofix.py --config tests/fixtures/projects_duplicate_name.yaml` exits 1 with message: `"Duplicate project name: {name}"`.

**AC-1.5** Running `python autofix.py --config tests/fixtures/projects_unsupported_language.yaml` exits 1 with message identifying the invalid language value.

**AC-1.6** All unit tests in `tests/test_config.py`, `tests/test_repo_manager.py`, `tests/test_tmux_manager.py`, `tests/test_language_detector.py` pass.

**AC-1.7** Given a `projects.yaml` pointing to a real (accessible) git repo, running `python autofix.py --no-attach` creates a tmux session named `"autofix"`, creates one window named after the project, and sends `claude --dangerously-skip-permissions` to the pane.

**AC-1.8** `CLAUDE.md` is written to `{local_path}/CLAUDE.md` before the agent is launched (even if the template is a stub in Phase 1 — full template is Phase 2).

**AC-1.9** If `tmux` is not installed, `autofix.py` exits 2 with: `"ERROR: tmux not found. Install with: brew install tmux (macOS) or apt install tmux (Ubuntu)"`.

**AC-1.10** `autofix.log` is created in `./logs/` and contains JSON-line entries for all orchestrator events.

---

### Phase 1 Test Hooks (for Quill QA)

- **Config validation**: run with each invalid fixture; assert exit code + stderr substring
- **Dry-run**: assert exit 0, no tmux session created, no git ops performed
- **Startup sequence**: with `--no-attach`; inspect tmux session with `tmux list-windows` after run
- **Git clone**: point to real public repo; assert `local_path` exists after run
- **Git pull**: run twice; second run should `pull` not `clone`

---

## Phase 2 — CLAUDE.md Template + Agent Instruction Design + Logging Templates

### Goal
Produce the complete `CLAUDE.md.j2` Jinja2 template and all language-specific logging templates that fully instruct the Claude agent. After Phase 2, a Claude agent spawned in a project pane will: check for `.autofix_init`, standardize logging, enter the monitoring loop, detect errors, apply fixes, test, commit, push, SSH-verify, and maintain `log.md`.

### Stories Covered
- **US-05** (P0): Logging standardization enforcement
- **US-06** (P0): Continuous log monitoring
- **US-07** (P0): Auto-fix: detect → fix → commit → push
- **US-08** (P0): VPS deployment verification via SSH
- **US-09** (P0): Continuous loop after fix
- **US-13** (P1): CLAUDE.md per-project instruction file
- **US-17** (P1): log.md created at logging standardization

### Files to Create

| File | Purpose |
|---|---|
| `templates/CLAUDE.md.j2` | Full Jinja2 agent instruction template |
| `autofix/claude_launcher.py` | Complete implementation (stub was Phase 1) |
| `logging_templates/python_structlog.py` | structlog JSON config snippet + instructions |
| `logging_templates/python_loguru.py` | loguru JSON config snippet + instructions |
| `logging_templates/nodejs_winston.js` | winston JSON config snippet + instructions |
| `logging_templates/nodejs_pino.js` | pino JSON config snippet + instructions |
| `logging_templates/ruby_semantic_logger.rb` | semantic_logger config snippet |
| `logging_templates/go_zap.go` | zap config snippet |
| `tests/test_claude_launcher.py` | Template rendering tests |
| `tests/fixtures/sample_project_python/` | Minimal Python project fixture for E2E test |

### Dependencies on Prior Phases
- Phase 1 must be complete: `AutoFixConfig`, `ProjectConfig`, `language_detector` all available

### Detailed Specifications

---

#### `templates/CLAUDE.md.j2`

The template must render a valid Markdown document. All Jinja2 variables listed below must be present and documented in the template. The rendered document must be human-readable and precisely instruct the agent.

**Jinja2 variables available in the template context:**

```
project_name          : str   — project.name
language              : str   — resolved language (never "auto" in rendered output)
local_path            : str   — project.local_path
log_path              : str   — project.log_path (relative to local_path)
branch                : str   — project.branch
push_branch           : str   — project.git.push_branch or project.branch
vps_enabled           : bool  — project.vps.enabled
vps_host              : str   — project.vps.host (empty string if vps_enabled=False)
vps_user              : str   — project.vps.user
ssh_key_path          : str   — project.vps.ssh_key_path (expanded path)
verify_command        : str   — project.vps.verify_command
verify_output_contains: str   — project.vps.verify_output_contains or ""
verify_timeout        : int   — project.vps.verify_timeout_seconds
debounce_minutes      : int   — project.monitoring.error_debounce_minutes
max_fixes_per_hour    : int   — project.monitoring.max_fixes_per_hour
blocked_patterns      : list  — project.monitoring.blocked_patterns
git_author_name       : str   — global.git_author_name
git_author_email      : str   — global.git_author_email
logging_framework     : str   — primary framework for language (see matrix below)
logging_template_content: str — rendered content of the appropriate logging_template file
```

**Language → logging_framework mapping (baked into `claude_launcher.py`, not the template):**

```
python  → "structlog"          (logging_templates/python_structlog.py)
nodejs  → "winston"            (logging_templates/nodejs_winston.js)
ruby    → "semantic_logger"    (logging_templates/ruby_semantic_logger.rb)
go      → "zap"                (logging_templates/go_zap.go)
unknown → "structlog"          (default fallback; agent will detect language itself)
```

**Template section structure (every section is REQUIRED):**

**Section 1 — Identity & Constraints:**
```
# AutoFix Agent Instructions — {{ project_name }}

## 1. Identity & Constraints

You are an autonomous software maintenance agent. You are operating in fully
autonomous mode. Do not interact with humans or wait for input.

Rules you MUST follow at all times:
- Only modify files inside {{ local_path }}
- Only push to branch: {{ push_branch }}
- All git commits MUST include [autofix] in the commit message
- Never embed credentials (passwords, tokens, private keys) in any file
- Never modify .git/ directory directly
- Never modify CLAUDE.md itself
- Set GIT_AUTHOR_NAME="{{ git_author_name }}" and GIT_AUTHOR_EMAIL="{{ git_author_email }}" for all commits
```

**Section 2 — Project Configuration:**
```
## 2. Project Configuration

- Project name: {{ project_name }}
- Language: {{ language }}
- Local path: {{ local_path }}
- Log file: {{ local_path }}/{{ log_path }}
- Git branch: {{ branch }}
- Push branch: {{ push_branch }}
{% if vps_enabled %}
- VPS host: {{ vps_host }}
- VPS user: {{ vps_user }}
- SSH key: {{ ssh_key_path }}
- Verify command: {{ verify_command }}
{% if verify_output_contains %}
- Verify output must contain: "{{ verify_output_contains }}"
{% endif %}
- Verify timeout: {{ verify_timeout }}s
{% else %}
- VPS verification: DISABLED (project uses CI/CD pipeline)
{% endif %}
- Error debounce: {{ debounce_minutes }} minutes
- Max fixes per hour: {{ max_fixes_per_hour }}
{% if blocked_patterns %}
- Blocked patterns (NEVER auto-fix these):
{% for pattern in blocked_patterns %}
  - {{ pattern }}
{% endfor %}
{% endif %}
```

**Section 3 — Phase 1: Logging Standardization:**
```
## 3. Phase 1: Logging Standardization (Run Once)

1. Check if file `.autofix_init` exists in {{ local_path }}
   - If YES: skip Phase 1 entirely, proceed to Phase 2
   - If NO: execute steps below

2. Detect project language:
   - Check {{ local_path }} for: go.mod → go; Gemfile → ruby;
     package.json → nodejs; requirements.txt/pyproject.toml/Pipfile → python
   - Language from config: {{ language }}

3. Check for existing standard logging framework:
   {{ language }}: look for {{ logging_framework }} import/usage in source files

4. If standard logging is ABSENT:
   a. Add {{ logging_framework }} to the dependency file
   b. Create logging configuration file using the template in Section 4
   c. Update the main entry point (main.py/app.py/index.js/main.go/etc.) to use
      the new logger
   d. Ensure log output goes to: {{ local_path }}/{{ log_path }}
   e. Create {{ local_path }}/log.md using the template in Section 6
   f. Run: git add -A
   g. Run: GIT_AUTHOR_NAME="{{ git_author_name }}" GIT_AUTHOR_EMAIL="{{ git_author_email }}" \
           git commit -m "chore(autofix): standardize logging framework [autofix]"
   h. Run: git push origin {{ push_branch }}

5. Write file {{ local_path }}/.autofix_init with content: "initialized"

6. Proceed to Phase 2
```

**Section 4 — Logging Framework Template:**
```
## 4. Logging Framework Template for {{ language }} ({{ logging_framework }})

Use the following configuration as the basis for the logging setup:

```{{ language }}
{{ logging_template_content }}
```

The logger MUST output JSON conforming to this schema:
{
  "timestamp": "<ISO 8601 UTC with ms>",
  "level": "<DEBUG|INFO|WARNING|ERROR|CRITICAL>",
  "logger": "<module.path>",
  "message": "<human readable>",
  "context": { ... },          // optional
  "error": { "type": ..., "message": ..., "stack": ... }  // on exceptions
}
```

**Section 5 — Phase 2: Continuous Monitoring Loop:**
```
## 5. Phase 2: Continuous Monitoring Loop

Execute this loop forever (never exit):

INITIALIZE:
  - error_history = {}         # {error_hash: last_seen_timestamp}
  - fix_attempts = {}          # {error_hash: count}
  - fixes_this_hour = 0
  - hour_start = current_time()

LOOP:
  1. Ensure log file {{ local_path }}/{{ log_path }} exists.
     If not: sleep 30s, check again. (Service may not have started yet.)
     If log file was rotated/truncated: re-open from beginning.

  2. Open the log stream for new lines (blocking):
     - When vps.enabled=True (primary method — SSH Docker streaming):
         ssh -i {{ ssh_key_path }} \
             -o StrictHostKeyChecking=no \
             -o BatchMode=yes \
             -o ConnectTimeout=10 \
             {{ vps_user }}@{{ vps_host }} \
             "{{ vps_log_stream_command }}"
       The vps_log_stream_command defaults to "docker logs -f {docker_container_name}".
       On SSH disconnect (EOF/timeout/network reset): wait 10s, reconnect. Do NOT exit.
     - When vps.enabled=False (fallback — local file tail):
         tail -F {{ local_path }}/{{ log_path }}
       If the log file does not exist: sleep 30s, check again.

  3. For each new line received:
     a. Try to parse as JSON. If not JSON: check for plaintext ERROR/Exception patterns.
     b. If level is not ERROR or CRITICAL: skip (continue to next line).

     c. Compute error_hash = hash(error_type + first_line_of_stack_trace)

     d. DEBOUNCE CHECK:
        If error_hash in error_history AND
           (current_time - error_history[error_hash]) < {{ debounce_minutes }} minutes:
          → Skip (already handling or recently handled)

     e. BLOCKED PATTERN CHECK:
        For each pattern in: {{ blocked_patterns | join(', ') or '(none)' }}
          If pattern found in error message or stack trace:
            → Append to log.md: "Human review required: {error summary}"
            → git add log.md && git commit -m "log(autofix): human review required [autofix]" && git push
            → Continue to next line

     f. RATE LIMIT CHECK:
        If current_time - hour_start > 60 minutes: reset fixes_this_hour = 0, hour_start = now
        If fixes_this_hour >= {{ max_fixes_per_hour }}:
          → Append to log.md: "Rate limit reached: fix skipped for {error_type}"
          → Continue to next line

     g. MAX RETRIES CHECK:
        If fix_attempts.get(error_hash, 0) >= 3:
          → Append to log.md: "Max retries exceeded for: {error_type}"
          → Continue to next line (do not fix again)

     h. DIAGNOSIS:
        - Extract: timestamp, error_type, message, stack_trace from log line
        - Identify implicated file(s) from stack trace
        - Read those source files
        - Understand the root cause

     i. FIX:
        - Apply minimal targeted fix to implicated file(s) only
        - Do NOT make sweeping changes to unrelated files

     j. UPDATE TRACKING:
        - error_history[error_hash] = current_time
        - fix_attempts[error_hash] = fix_attempts.get(error_hash, 0) + 1

     k. TEST:
        - Detect and run available test suite:
          python → pytest (if pytest.ini/setup.cfg/tests/ exists)
          nodejs → npm test (if test script in package.json)
          ruby   → bundle exec rspec (if spec/ exists) or bundle exec rake test
          go     → go test ./...
        - If test command not found: proceed without testing (log the absence)

     l. IF TESTS FAIL:
        - Run: git checkout -- .   (revert ALL changes)
        - Append to log.md: | {timestamp} | FIX_REVERTED | {error_type}: tests failed | — |
        - git add log.md && git commit -m "log(autofix): fix reverted [autofix]" && git push
        - Continue loop

     m. IF TESTS PASS (or no test suite):
        i.   git add -A
        ii.  GIT_AUTHOR_NAME="{{ git_author_name }}" GIT_AUTHOR_EMAIL="{{ git_author_email }}" \
             git commit -m "fix(<module>): <one-line description> [autofix]"
        iii. git push origin {{ push_branch }}
             If REJECTED: git pull --rebase origin {{ push_branch }} && git push (retry once)
             If STILL REJECTED: log failure; revert with git checkout -- .; continue

        iv.  fixes_this_hour += 1

        v.   DEPLOYMENT VERIFICATION:
{% if vps_enabled %}
             - Expand SSH key: {{ ssh_key_path }}
             - Check key file exists on THIS machine (local)
             - If key missing: skip verification; log warning
             - Run:
               ssh -i {{ ssh_key_path }} \
                   -o StrictHostKeyChecking=no \
                   -o BatchMode=yes \
                   -o ConnectTimeout={{ verify_timeout }} \
                   {{ vps_user }}@{{ vps_host }} \
                   '{{ verify_command }}'
             - capture exit_code and stdout
             - If exit_code == 0{% if verify_output_contains %} AND "{{ verify_output_contains }}" in stdout{% endif %}:
                 VERIFIED = SUCCESS
               Else:
                 VERIFIED = FAILURE
{% else %}
             - VPS verification disabled for this project (CI/CD pipeline deploys)
             - Set VERIFIED = SKIPPED
{% endif %}

        vi.  UPDATE log.md:
             | {timestamp} | ERROR_DETECTED  | {error_type}: {message} | — |
             | {timestamp} | FIX_APPLIED     | {description}           | {commit_sha} |
             | {timestamp} | DEPLOY_VERIFIED | {VERIFIED status}       | — |
             git add log.md
             GIT_AUTHOR_NAME="{{ git_author_name }}" GIT_AUTHOR_EMAIL="{{ git_author_email }}" \
             git commit -m "log(autofix): update audit log [autofix]"
             git push origin {{ push_branch }}

  4. Sleep 1 second, continue LOOP
```

**Section 6 — log.md Format:**
```
## 6. log.md Format

Create {{ local_path }}/log.md with this structure if it does not exist:

---
# AutoFix Log — {{ project_name }}

## Logging Structure
- **Framework:** {{ logging_framework }}
- **Output path:** {{ log_path }}
- **Format:** JSON (Elastic Common Schema subset)
- **Log levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Key fields:** timestamp, level, logger, message, context, error

## Agent Activity Log

| Timestamp | Event | Description | Commit SHA |
|---|---|---|---|
---

When appending entries, add new rows to the table. Valid event types:
- LOGGING_STANDARDIZED
- ERROR_DETECTED
- FIX_APPLIED
- FIX_REVERTED
- DEPLOY_VERIFIED
- HUMAN_REVIEW_REQUIRED
- RATE_LIMIT_SKIPPED
- MAX_RETRIES_EXCEEDED
- WATCHDOG_RESPAWN (added by orchestrator, not agent)
```

**Section 7 — Safety Rules:**
```
## 7. Safety Rules (MUST follow without exception)

1. You MUST NOT modify any of these:
   - .git/ directory
   - CLAUDE.md (this file)
   - Any file outside {{ local_path }}

2. You MUST NOT push to any branch other than {{ push_branch }}.

3. You MUST NOT auto-fix any error matching these patterns:
{% for pattern in blocked_patterns %}
   - {{ pattern }}
{% endfor %}
{% if not blocked_patterns %}
   (no blocked patterns configured)
{% endif %}

4. You MUST NOT embed credentials, tokens, or passwords in committed files.

5. You MUST revert (git checkout -- .) if tests fail before committing.

6. You MUST stop fixing a specific error after 3 failed attempts.
   Log "max retries exceeded" and continue monitoring.

7. On push rejection: pull --rebase, retry once. If still rejected: revert + log + continue.

8. If you encounter a confusing or ambiguous situation: log it to log.md and continue
   monitoring. Do NOT halt the process.
```

---

#### `autofix/claude_launcher.py` — Complete Implementation

**`ClaudeLauncher` class:**

Constructor: `__init__(self, template_dir: str = "templates/")`

Loads Jinja2 `Environment` with `FileSystemLoader(template_dir)`.

**`_resolve_language(project: ProjectConfig) -> str`:**
- If `project.language != "auto"`: return `project.language`
- Else: call `language_detector.detect_language(project.local_path)`, return result

**`_get_logging_framework(language: str) -> str`:**
- `"python"` → `"structlog"`
- `"nodejs"` → `"winston"`
- `"ruby"` → `"semantic_logger"`
- `"go"` → `"zap"`
- `"unknown"` or default → `"structlog"`

**`_load_logging_template(language: str) -> str`:**
- Maps language to file in `logging_templates/`
- Reads and returns file content
- If file not found: returns `"# Logging template not found for language: {language}"`

**`render_claude_md(project: ProjectConfig, global_cfg: GlobalSettings) -> str`:**
- Resolve language, framework, template content
- Resolve `push_branch` (use `project.git.push_branch` if set, else `project.branch`)
- Expand `ssh_key_path` (`os.path.expanduser`)
- Build Jinja2 context dict with all variables listed in the template spec above
- Load `CLAUDE.md.j2` template
- `template.render(**context)` → return string

**`write_claude_md(project: ProjectConfig, content: str) -> Path`:**
- Write to `Path(project.local_path) / "CLAUDE.md"`
- Ensure parent directory exists
- Return the Path

**`render_and_write(project: ProjectConfig, global_cfg: GlobalSettings) -> Path`:**
- Calls `render_claude_md` then `write_claude_md`

---

#### Logging Templates

Each file in `logging_templates/` is a **static reference snippet** that the Claude agent copies/adapts when injecting logging. Each file includes:
1. The import/require statement
2. The logger initialization producing the canonical JSON schema
3. Example usage (how to log a message, how to log an exception)
4. How to configure the output file path

**`logging_templates/python_structlog.py`** — structlog config that:
- Adds `TimeStamper(fmt="iso", utc=True)` processor
- Adds `add_log_level` processor
- Configures `JSONRenderer` for production
- Sets output to a `FileHandler` targeting the log path
- Shows `structlog.get_logger(__name__).error("message", error=e)` usage

**`logging_templates/python_loguru.py`** — loguru config that:
- Removes default handler
- Adds file handler with JSON serialization enabled (`serialize=True`)
- Configures format matching canonical schema as close as loguru allows
- Shows `logger.error("message")` and `logger.exception("message")` usage

**`logging_templates/nodejs_winston.js`** — winston config that:
- Uses `winston.createLogger` with `format.json()` and `format.timestamp()`
- Sets `transports: [new winston.transports.File({ filename: LOG_PATH })]`
- Maps winston levels to canonical schema levels
- Shows `logger.error("message", { context: { request_id: "..." } })` usage

**`logging_templates/nodejs_pino.js`** — pino config that:
- Uses `pino({ level: 'info' }, pino.destination(LOG_PATH))`
- Shows `logger.error({ err }, "message")` usage

**`logging_templates/ruby_semantic_logger.rb`** — config that:
- Sets `SemanticLogger.default_level = :info`
- Adds `SemanticLogger::Appender::File.new(file_name: LOG_PATH, formatter: :json)`
- Shows `logger = SemanticLogger['ClassName']` and `logger.error("message", exception: e)` usage

**`logging_templates/go_zap.go`** — uber-go/zap config that:
- Opens log file with `os.OpenFile(LOG_PATH, ...)`
- Sets `zapcore.InfoLevel` as the global log level
- Creates a `*zap.Logger` with JSON encoder writing to file + stdout
- Maps zap output to canonical schema field names
- Shows `log.Error("db_connection_failed", zap.Error(err))` usage

---

### Phase 2 Acceptance Criteria (DoD)

**AC-2.1** `claude_launcher.render_claude_md(project, global_cfg)` produces a Markdown string containing all 7 sections. All Jinja2 variables are rendered (no `{{ }}` in output).

**AC-2.2** For a Python project, the rendered CLAUDE.md contains: `structlog`, the structlog template content from `logging_templates/python_structlog.py`, and the monitoring loop with the project's `log_path`, `push_branch`, `vps_host`, `debounce_minutes`, and `max_fixes_per_hour` values correctly substituted.

**AC-2.3** For `vps.enabled = false`, the rendered CLAUDE.md contains `"VPS verification disabled"` and does NOT contain the SSH command.

**AC-2.4** When `blocked_patterns = ["CVE-", "database migration"]`, the rendered CLAUDE.md lists both patterns in the blocked patterns section AND in the safety rules section.

**AC-2.5** All 6 logging template files exist and are non-empty.

**AC-2.6** `detect_language` correctly returns `"python"` for a directory containing `requirements.txt`, `"nodejs"` for `package.json`, `"go"` for `go.mod`, `"ruby"` for `Gemfile`, and `"unknown"` for an empty directory.

**AC-2.7** `tests/test_claude_launcher.py` passes all tests:
- Render test for each supported language
- Render test for `vps.enabled = false`
- Render test for non-empty `blocked_patterns`
- Test that `ssh_key_path` is `~`-expanded in rendered output
- Test that no Jinja2 syntax errors remain in `CLAUDE.md.j2`

**AC-2.8** The file `{local_path}/CLAUDE.md` is written with correct content when `write_claude_md` is called.

**AC-2.9** `projects.yaml.example` includes complete inline comments for every field.

---

### Phase 2 Test Hooks (for Quill QA)

- **Template rendering**: assert rendered output contains expected strings for each project type
- **Language auto-detection**: create temp dirs with/without manifest files; assert correct detection
- **VPS flag**: assert SSH block appears/disappears based on `vps.enabled`
- **Blocked patterns**: assert patterns appear in safety rules section

---

## Phase 3 — Watchdog, Notifications, Dry-Run Mode, and Hardening

### Goal
Add the watchdog thread (pane liveness monitoring + crash-loop detection + auto-respawn), webhook notification client, dry-run mode, and full test coverage. After Phase 3, the system is production-ready for ≤10 concurrent projects.

### Stories Covered
- **US-10** (P1): Automated log.md maintenance — orchestrator-level log.md entry injection on watchdog events
- **US-11** (P1): Automatic pane respawn on crash
- **US-14** (P1): Per-project branch and VPS configuration (already in schema; verify end-to-end)
- **US-15** (P1): SSH key auth throughout (verify in watchdog respawn sequence)
- **US-16** (P2): Blocked error patterns — verify in template + schema validation
- **US-18** (P2): Dry-run mode

### Files to Create / Modify

| File | Action | Purpose |
|---|---|---|
| `autofix/watchdog.py` | **Create** | Watchdog thread implementation |
| `autofix/notifier.py` | **Create** | Webhook notification client |
| `autofix.py` | **Modify** | Wire watchdog + notifier into startup sequence |
| `tests/test_watchdog.py` | **Create** | Watchdog tests |
| `tests/test_notifier.py` | **Create** | Notifier tests |
| `README.md` | **Create** | Full user-facing documentation |

### Dependencies on Prior Phases
- Phase 1: `TmuxManager`, `RepoManager`, `GlobalConfig`, `ProjectConfig` all available
- Phase 2: `ClaudeLauncher` available for respawn sequence

### Detailed Specifications

---

#### `autofix/watchdog.py`

**Constants:**
```
CRASH_LOOP_WINDOW_SECONDS = 600    # 10 minutes
CRASH_LOOP_THRESHOLD = 5           # >5 restarts in window = crash loop
CRASH_LOOP_PAUSE_SECONDS = 600     # Pause respawns for 10 minutes on crash loop
```

**`Watchdog` class:**

Constructor:
```
__init__(
    self,
    session: libtmux.Session,
    projects: list[ProjectConfig],
    tmux_manager: TmuxManager,
    repo_manager: RepoManager,
    claude_launcher: ClaudeLauncher,
    global_cfg: GlobalSettings,
    interval_seconds: int = 60,
)
```

Internal state:
```
self._stop_event = threading.Event()
self._thread: Optional[threading.Thread] = None
self._crash_history: dict[str, list[float]] = {}  # project_name → [timestamps]
self._paused_until: dict[str, float] = {}          # project_name → resume_timestamp
```

**`start() -> threading.Thread`:**
- Create `threading.Thread(target=self._check_loop, daemon=True)`
- Store as `self._thread`; start; return handle

**`stop() -> None`:**
- Set `self._stop_event`

**`_check_loop() -> None`:**
```
while not self._stop_event.is_set():
    self._stop_event.wait(timeout=self.interval_seconds)
    if self._stop_event.is_set():
        break
    for project in self.projects:
        try:
            self._check_project(project)
        except Exception as e:
            log.warning(f"Watchdog error checking {project.name}: {e}")
```

**`_check_project(project: ProjectConfig) -> None`:**
```
1. Check if paused: if project.name in self._paused_until AND time.time() < self._paused_until[project.name]:
     log DEBUG "Respawn paused for {project.name} until {datetime}"
     return

2. is_alive = self.tmux_manager.is_pane_alive(self.session, project.name)
3. If alive: return (no action)

4. Log WARNING: "Pane dead for project {project.name} — initiating respawn"

5. Record crash: self._crash_history.setdefault(project.name, []).append(time.time())

6. Prune old crash history: remove entries older than CRASH_LOOP_WINDOW_SECONDS

7. If len(crash_history[project.name]) > CRASH_LOOP_THRESHOLD:
     Log WARNING: "Crash loop detected for {project.name} — pausing respawn for {CRASH_LOOP_PAUSE_SECONDS}s"
     self._paused_until[project.name] = time.time() + CRASH_LOOP_PAUSE_SECONDS
     return

8. self._respawn(project)
```

**`_respawn(project: ProjectConfig) -> None`:**
```
1. self.tmux_manager.kill_window_if_exists(self.session, project.name)

2. result = self.repo_manager.pull(project)
   If result.success is False:
     Log warning: "git pull failed during respawn for {project.name}: {result.error}"
     # Still continue with respawn (use stale code)

3. self.claude_launcher.render_and_write(project, self.global_cfg)

4. window = self.tmux_manager.create_project_window(self.session, project)

5. self.tmux_manager.launch_agent(window, project)

6. Log INFO: "Pane respawned for {project.name}"
```

---

#### `autofix/notifier.py`

**`Notifier` class:**

Constructor: `__init__(self)` — no config needed at init time.

**`notify(project: ProjectConfig, event: str, payload: dict) -> bool`:**
```
1. If project.notifications is None or not project.notifications.webhook_url:
     return False (silently)

2. If event not in project.notifications.on_events:
     return False (silently)

3. Build HTTP POST body:
   {
     "project": project.name,
     "event": event,
     "error_summary": payload.get("error_summary", ""),
     "commit_sha": payload.get("commit_sha", ""),
     "verification_status": payload.get("verification_status", ""),
     "timestamp": datetime.utcnow().isoformat() + "Z"
   }

4. POST to project.notifications.webhook_url with timeout=10s

5. If HTTP error or exception: log WARNING (never raise); return False

6. Return True on success
```

**Valid event values:** `"fix_applied"`, `"fix_failed"`, `"verification_failed"`

---

#### `autofix.py` — Watchdog + Notifier Integration

Add to startup sequence (between step 11 and 12 from Phase 1):

```
11. Start watchdog:
    watchdog = Watchdog(
        session=session,
        projects=[p for p in config.projects if p.name not in failed_projects],
        tmux_manager=tmux_manager,
        repo_manager=repo_manager,
        claude_launcher=claude_launcher,
        global_cfg=config.global_settings,
        interval_seconds=config.global_settings.watchdog_interval_seconds,
    )
    watchdog.start()
    Log INFO: "Watchdog started (interval: {watchdog_interval_seconds}s)"
```

Handle `KeyboardInterrupt` (Ctrl+C) gracefully:
```python
try:
    tmux_manager.attach_session(session)
except KeyboardInterrupt:
    watchdog.stop()
    log.info("AutoFix orchestrator stopped by user.")
    sys.exit(0)
```

---

#### `README.md` — Required Sections

1. **What is AutoFix** — one-paragraph description
2. **Prerequisites** — tmux ≥ 3.0, python 3.9+, git, claude CLI; install commands for macOS + Ubuntu
3. **Quick Start** — 5-step getting started (clone repo, pip install, edit projects.yaml, run autofix.py)
4. **projects.yaml Reference** — link to `projects.yaml.example` + field descriptions
5. **How It Works** — brief explanation of the 3-phase agent loop
6. **Safety & Guardrails** — explanation of blocked_patterns, max_fixes_per_hour, test gate
7. **Troubleshooting** — common issues (SSH key not found, tmux not installed, pane crash loop)
8. **Audit Trail** — how to read `log.md` and find autofix commits in git log

---

### Phase 3 Acceptance Criteria (DoD)

**AC-3.1** The watchdog thread starts when `autofix.py` runs (verify via log output: `"Watchdog started"`).

**AC-3.2** When a project's tmux pane is manually killed (`tmux kill-pane`), the watchdog detects it within `watchdog_interval_seconds + 5s` and spawns a new pane for that project.

**AC-3.3** Crash loop detection: if a pane is killed and respawned >5 times within 10 minutes, the watchdog logs `"Crash loop detected for {project.name}"` and suspends respawning for 10 minutes. After the pause, it resumes normal monitoring.

**AC-3.4** `Notifier.notify()` sends an HTTP POST to the configured webhook URL for events listed in `on_events`. For projects with `notifications: null`, no HTTP call is made.

**AC-3.5** Running `python autofix.py --dry-run` validates config, prints a plan summary (project name, language, local_path, vps_enabled), and exits 0 without creating a tmux session, running git, or writing CLAUDE.md.

**AC-3.6** `tests/test_watchdog.py` passes:
- Test: watchdog detects dead pane (mocked `is_pane_alive` returns False) and calls `respawn`
- Test: crash loop threshold triggers pause
- Test: watchdog stops cleanly on `stop()` call within 2× interval

**AC-3.7** `tests/test_notifier.py` passes:
- Test: notify sends correct payload to webhook URL (mocked `requests.post`)
- Test: notify returns False when no webhook configured
- Test: notify returns False when event not in `on_events`
- Test: notify returns False (does NOT raise) when requests throws `ConnectionError`

**AC-3.8** All tests from Phases 1 + 2 + 3 pass together: `pytest tests/ -v`

**AC-3.9** `README.md` exists and contains all 8 required sections.

**AC-3.10** Running `python autofix.py` with a valid `projects.yaml` pointing to ≥2 real projects starts all panes within 60 seconds.

---

### Phase 3 Test Hooks (for Quill QA)

- **Watchdog recovery**: manually kill a pane; assert new pane appears within 2× interval
- **Crash loop**: repeatedly kill pane >5 times; assert respawn pauses
- **Dry-run**: assert no side effects (no tmux session, no git ops, no files written)
- **Notifications**: use webhook.site or ngrok for live webhook test
- **10-project stress test**: configure 10 projects (can use dummy repos); assert ≤60s startup

---

## Cross-Phase Invariants

These invariants must hold across all phases at all times:

1. **No credentials in committed files**: `CLAUDE.md`, `log.md`, `autofix.log`, and all template files must never contain private keys, tokens, or passwords. Devin must verify this after every file written.

2. **Per-project isolation**: An exception in processing project A must not prevent project B from starting. All per-project operations are wrapped in `try/except`.

3. **Idempotency**: Running `autofix.py` twice must not create duplicate tmux sessions or panes. `get_or_create_session()` and `create_project_window()` must be idempotent.

4. **Exit codes are deterministic**: Exit 0 = success; Exit 1 = config error; Exit 2 = prereq missing; Exit 3 = all projects failed.

5. **`autofix.log` always written**: Even on startup failure, the orchestrator logger must have written at least one entry before exit.

6. **Git env always set**: All git subprocess calls must include `GIT_TERMINAL_PROMPT=0` to prevent interactive credential prompts from hanging the orchestrator.
