# Data Models & Schemas — AutoFix

**Version:** 1.0  
**Author:** Atlas (Architect)  
**Date:** 2025-01-01  
**Architecture:** `docs/architecture/architecture.md`

---

## 1. `projects.yaml` — Full Annotated Schema

This is the complete reference schema. Every field is documented with type, requirement, default, and valid values. This file is the sole configuration interface for AutoFix operators.

```yaml
# ============================================================
# AutoFix Configuration File
# Save as: projects.yaml (in the directory where you run autofix.py)
# ============================================================

# REQUIRED. Schema version for forward compatibility.
# Current supported version: "1.0"
# Warn (but do not fail) on unrecognized versions.
schema_version: "1.0"

# ============================================================
# GLOBAL SETTINGS
# All fields are optional; defaults shown below.
# ============================================================
global:
  # Name of the tmux session AutoFix creates/reuses.
  # Default: "autofix"
  # Type: string
  tmux_session_name: "autofix"

  # How often (in seconds) the watchdog checks each pane's liveness.
  # If a pane is found dead, it is respawned within this interval.
  # Default: 60
  # Type: integer > 0
  watchdog_interval_seconds: 60

  # The exact command sent to each tmux pane to start the Claude agent.
  # Default: "claude --dangerously-skip-permissions"
  # Type: string
  # Note: Change only if Claude CLI binary is at a non-standard path.
  claude_command: "claude --dangerously-skip-permissions"

  # Git author name used for all commits made by the AutoFix agent.
  # This distinguishes AutoFix commits from human commits in git log.
  # Default: "AutoFix Agent"
  # Type: string
  git_author_name: "AutoFix Agent"

  # Git author email used for all commits made by the AutoFix agent.
  # Default: "autofix@local"
  # Type: string
  git_author_email: "autofix@local"

  # Directory where orchestrator logs (autofix.log) are written.
  # Relative to the directory where autofix.py is run.
  # Default: "./logs"
  # Type: string
  log_dir: "./logs"

# ============================================================
# PROJECTS
# List of projects to monitor. Maximum 10 in v1.
# Each entry requires: name, repo_url, local_path, vps block.
# ============================================================
projects:

  # ─────────────────────────────────────────
  # Project Entry Example 1: Python API
  # ─────────────────────────────────────────
  - # REQUIRED. Unique identifier for this project.
    # Used as the tmux window name.
    # Must match pattern: [a-zA-Z0-9_-]+
    # Must be unique across all projects in this file.
    name: "my-python-api"

    # REQUIRED. Git remote URL for the project repository.
    # SSH format strongly recommended (avoids credential prompts).
    # HTTPS format works if credential helper is configured.
    # Examples:
    #   git@github.com:user/repo.git
    #   https://github.com/user/repo.git
    repo_url: "git@github.com:user/my-python-api.git"

    # REQUIRED. Absolute path on the local machine where the repo
    # is (or will be) cloned. Must start with /.
    # AutoFix will run: git clone <repo_url> <local_path> on first run.
    local_path: "/home/user/projects/my-python-api"

    # OPTIONAL. Git branch to monitor and push fixes to.
    # Default: "main"
    # Type: string
    branch: "main"

    # OPTIONAL. Programming language of the project.
    # AutoFix uses this to determine which logging framework to inject.
    # Default: "auto" (AutoFix detects from manifest files)
    # Valid values: python | nodejs | ruby | go | auto
    language: "python"

    # OPTIONAL. Path to the application log file, relative to local_path.
    # The Claude agent will tail this file for ERROR/CRITICAL events.
    # Default: "logs/app.log"
    # Type: string (relative path)
    log_path: "logs/app.log"

    # ── VPS Configuration ────────────────────
    # The VPS where this project is deployed.
    # Required unless vps.enabled is set to false.
    vps:
      # OPTIONAL. Enable/disable VPS verification step.
      # Set to false for projects that deploy via CI/CD pipeline
      # (e.g., GitHub Actions auto-deploys on push).
      # Default: true
      # Type: bool
      enabled: true

      # REQUIRED (when enabled: true). VPS IP address or hostname.
      # Type: string
      host: "192.168.1.100"

      # REQUIRED (when enabled: true). SSH username on the VPS.
      # Type: string
      user: "deploy"

      # REQUIRED (when enabled: true). Path to SSH private key file.
      # ~ is expanded. File must exist on the local machine.
      # NEVER put the private key content here — only the path.
      # Type: string (absolute or ~ path)
      ssh_key_path: "~/.ssh/id_rsa"

      # REQUIRED (when enabled: true). Shell command to run on VPS
      # after a fix is pushed to verify the deployment is healthy.
      # This command runs as <vps_user> via SSH.
      # Examples:
      #   "systemctl status my-python-api"
      #   "docker ps | grep my-python-api"
      #   "curl -sf http://localhost:8000/health"
      #   "pm2 status my-python-api"
      # Type: string
      verify_command: "systemctl status my-python-api"

      # OPTIONAL. If set, the verification also checks that this exact
      # substring appears in the stdout of verify_command.
      # If null or omitted: only the exit code (0) is checked.
      # Example: "active (running)"
      # Type: string | null
      verify_output_contains: "active (running)"

      # OPTIONAL. Timeout in seconds for the SSH verify_command.
      # Default: 30
      # Type: integer > 0
      verify_timeout_seconds: 30

    # ── Git Configuration ────────────────────
    git:
      # OPTIONAL. Branch to push auto-fix commits to.
      # Default: same as the top-level `branch` field.
      # Override this to push fixes to a different branch
      # (e.g., branch: main, push_branch: autofix/fixes).
      # Type: string | null
      push_branch: "main"

      # OPTIONAL. If true, the agent runs `git pull --rebase` before
      # applying a fix to ensure it's working on the latest code.
      # Default: true
      # Type: bool
      pull_before_fix: true

      # OPTIONAL. If true, git commits are GPG-signed.
      # Requires GPG to be configured on the local machine.
      # Default: false
      # Type: bool
      commit_sign: false

    # ── Monitoring Configuration ─────────────
    monitoring:
      # OPTIONAL. Minimum gap (in minutes) between fix attempts for
      # the same error. Prevents duplicate fixes on recurring errors.
      # Default: 5
      # Type: integer >= 1
      error_debounce_minutes: 5

      # OPTIONAL. Maximum number of auto-fixes the agent may apply
      # in any rolling 60-minute window. Prevents runaway fix loops.
      # Default: 3
      # Valid range: 1 to 20 (inclusive)
      # Type: integer
      max_fixes_per_hour: 3

      # OPTIONAL. List of regex/substring patterns. If any pattern
      # matches an error message or stack trace, the agent will NOT
      # attempt to auto-fix it and will instead log:
      # "Human review required: <error summary>"
      # Default: [] (empty — all errors are eligible for auto-fix)
      # Type: list[string]
      # Recommended minimums (always include these):
      blocked_patterns:
        - "CVE-"                    # Security vulnerabilities
        - "SQL injection"           # Security
        - "database migration"      # Schema changes
        - "ALTER TABLE"             # Schema changes
        - "DROP TABLE"              # Destructive DB ops
        - "SECRET"                  # Secret/key references
        - "PASSWORD"                # Password-related
        - "AUTH"                    # Authentication errors

    # ── Notifications Configuration ──────────
    # All fields optional. Set to null to disable notifications.
    notifications:
      # Webhook URL to POST event notifications to.
      # Supports Slack, Discord, or any HTTP endpoint.
      # Slack: "https://hooks.slack.com/services/T.../B.../..."
      # Discord: "https://discord.com/api/webhooks/..."
      # Default: null (no notifications)
      # Type: string | null
      webhook_url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"

      # List of event types that trigger a notification.
      # Valid values:
      #   fix_applied         — agent committed and pushed a fix
      #   fix_failed          — fix was reverted because tests failed
      #   verification_failed — SSH verify_command failed after push
      # Default: []
      # Type: list[string]
      on_events:
        - "fix_applied"
        - "fix_failed"
        - "verification_failed"

  # ─────────────────────────────────────────
  # Project Entry Example 2: Node.js Frontend
  # (Minimal — showing only required fields + defaults)
  # ─────────────────────────────────────────
  - name: "my-nodejs-app"
    repo_url: "git@github.com:user/my-nodejs-app.git"
    local_path: "/home/user/projects/my-nodejs-app"
    language: "nodejs"
    log_path: "logs/app.log"

    vps:
      host: "192.168.1.101"
      user: "deploy"
      ssh_key_path: "~/.ssh/id_rsa"
      verify_command: "pm2 status my-nodejs-app"
      verify_output_contains: "online"

    # All other fields use their defaults:
    # branch: "main", git: {pull_before_fix: true, commit_sign: false}
    # monitoring: {error_debounce_minutes: 5, max_fixes_per_hour: 3, blocked_patterns: []}
    # notifications: null

  # ─────────────────────────────────────────
  # Project Entry Example 3: CI/CD Pipeline (no VPS verify)
  # ─────────────────────────────────────────
  - name: "my-ci-cd-service"
    repo_url: "git@github.com:user/my-ci-cd-service.git"
    local_path: "/home/user/projects/my-ci-cd-service"
    language: "go"

    vps:
      enabled: false               # GitHub Actions deploys; skip SSH verify
      host: ""                     # Required field but unused when enabled: false
      user: ""
      ssh_key_path: "~/.ssh/id_rsa"
      verify_command: ""
```

---

## 2. `projects.yaml` Field Reference Table

| Field Path | Type | Required | Default | Validation Rules |
|---|---|---|---|---|
| `schema_version` | `string` | **Yes** | — | Must be present; warn on unknown versions |
| `global.tmux_session_name` | `string` | No | `"autofix"` | Non-empty string |
| `global.watchdog_interval_seconds` | `int` | No | `60` | > 0 |
| `global.claude_command` | `string` | No | `"claude --dangerously-skip-permissions"` | Non-empty |
| `global.git_author_name` | `string` | No | `"AutoFix Agent"` | Non-empty |
| `global.git_author_email` | `string` | No | `"autofix@local"` | Non-empty |
| `global.log_dir` | `string` | No | `"./logs"` | Valid path |
| `projects[].name` | `string` | **Yes** | — | Unique; matches `[a-zA-Z0-9_-]+` |
| `projects[].repo_url` | `string` | **Yes** | — | Non-empty |
| `projects[].local_path` | `string` | **Yes** | — | Absolute path (starts with `/`) |
| `projects[].branch` | `string` | No | `"main"` | Non-empty |
| `projects[].language` | `string` | No | `"auto"` | One of: `python`, `nodejs`, `ruby`, `go`, `auto` |
| `projects[].log_path` | `string` | No | `"logs/app.log"` | Non-empty relative path |
| `projects[].vps.enabled` | `bool` | No | `true` | — |
| `projects[].vps.host` | `string` | **Yes*** | — | *Required when `vps.enabled: true` |
| `projects[].vps.user` | `string` | **Yes*** | — | *Required when `vps.enabled: true` |
| `projects[].vps.ssh_key_path` | `string` | **Yes** | — | `~` expanded; file must exist on local machine |
| `projects[].vps.verify_command` | `string` | **Yes*** | — | *Required when `vps.enabled: true` |
| `projects[].vps.verify_output_contains` | `string\|null` | No | `null` | Optional substring check |
| `projects[].vps.verify_timeout_seconds` | `int` | No | `30` | > 0 |
| `projects[].git.push_branch` | `string\|null` | No | `null` (= `branch`) | Non-empty if set |
| `projects[].git.pull_before_fix` | `bool` | No | `true` | — |
| `projects[].git.commit_sign` | `bool` | No | `false` | — |
| `projects[].monitoring.error_debounce_minutes` | `int` | No | `5` | ≥ 1 |
| `projects[].monitoring.max_fixes_per_hour` | `int` | No | `3` | 1 ≤ x ≤ 20 |
| `projects[].monitoring.blocked_patterns` | `list[string]` | No | `[]` | Strings (regex or substring) |
| `projects[].notifications.webhook_url` | `string\|null` | No | `null` | Valid HTTP(S) URL if set |
| `projects[].notifications.on_events` | `list[string]` | No | `[]` | Values from: `fix_applied`, `fix_failed`, `verification_failed` |
| `projects` (list length) | — | — | — | 1 ≤ length ≤ 10 |
| `projects[].name` (uniqueness) | — | — | — | All names must be distinct |

---

## 3. Pydantic v2 Model Hierarchy

```
AutoFixConfig
├── schema_version: str
├── global_settings: GlobalSettings        (YAML key: "global")
│   ├── tmux_session_name: str
│   ├── watchdog_interval_seconds: int
│   ├── claude_command: str
│   ├── git_author_name: str
│   ├── git_author_email: str
│   └── log_dir: str
└── projects: list[ProjectConfig]
    └── ProjectConfig
        ├── name: str
        ├── repo_url: str
        ├── local_path: str
        ├── branch: str
        ├── language: str
        ├── log_path: str
        ├── vps: VPSConfig
        │   ├── enabled: bool
        │   ├── host: str
        │   ├── user: str
        │   ├── ssh_key_path: str
        │   ├── verify_command: str
        │   ├── verify_output_contains: Optional[str]
        │   └── verify_timeout_seconds: int
        ├── git: GitConfig
        │   ├── push_branch: Optional[str]
        │   ├── pull_before_fix: bool
        │   └── commit_sign: bool
        ├── monitoring: MonitoringConfig
        │   ├── error_debounce_minutes: int
        │   ├── max_fixes_per_hour: int
        │   └── blocked_patterns: list[str]
        └── notifications: Optional[NotificationsConfig]
            ├── webhook_url: Optional[str]
            └── on_events: list[str]
```

---

## 4. `log.md` — Per-Project Audit Log Structure

Each monitored project gets a `log.md` file created by the Claude agent at the project root (`{local_path}/log.md`) during Phase 1 (logging standardization).

### 4.1 Full Template

```markdown
# AutoFix Log — {project_name}

## Logging Structure
- **Framework:** {logging_framework} {version}
- **Output path:** {log_path}
- **Format:** JSON (Elastic Common Schema subset)
- **Log levels in use:** DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Key fields:** timestamp, level, logger, message, context, error
- **Standardized by AutoFix:** {ISO_8601_timestamp}

## Agent Activity Log

| Timestamp | Event | Description | Commit SHA |
|---|---|---|---|
| 2025-01-01T10:00:00Z | LOGGING_STANDARDIZED | Injected structlog; updated main.py | abc1234 |
| 2025-01-01T11:30:00Z | ERROR_DETECTED | ValueError in api/routes.py:42 | — |
| 2025-01-01T11:31:00Z | FIX_APPLIED | Added null check before int() cast | def5678 |
| 2025-01-01T11:32:00Z | DEPLOY_VERIFIED | systemctl status: active (running) | — |
```

### 4.2 Event Type Reference

| Event Type | Trigger | Description Field Contents | Commit SHA |
|---|---|---|---|
| `LOGGING_STANDARDIZED` | Phase 1 completes | `"Injected {framework} vX.Y.Z; updated {entry_point}"` | Commit SHA of standardization commit |
| `ERROR_DETECTED` | ERROR/CRITICAL log line found | `"{ErrorType} in {file}:{line}: {message}"` | `—` |
| `FIX_APPLIED` | Fix committed + pushed | `"{one-line fix description}"` | Fix commit SHA |
| `FIX_REVERTED` | Tests failed after fix | `"{ErrorType}: tests failed — fix reverted"` | `—` |
| `DEPLOY_VERIFIED` | SSH verify returns success | `"{verify_command} output: {substring_matched}"` | `—` |
| `DEPLOY_FAILED` | SSH verify returns failure | `"Exit code {n} or output mismatch. Output: {stdout[:200]}"` | `—` |
| `HUMAN_REVIEW_REQUIRED` | Error matches blocked_pattern | `"Matched pattern '{pattern}': {error_summary}"` | `—` |
| `RATE_LIMIT_SKIPPED` | max_fixes_per_hour reached | `"Fix skipped: {fixes_this_hour}/{max} fixes used this hour"` | `—` |
| `MAX_RETRIES_EXCEEDED` | 3 failed fix attempts for same error | `"Max retries (3) exceeded for: {error_hash}"` | `—` |
| `VPS_VERIFY_SKIPPED` | vps.enabled = false | `"VPS verification disabled for this project"` | `—` |
| `SSH_KEY_MISSING` | SSH key file not found at runtime | `"Key not found: {ssh_key_path} — verification skipped"` | `—` |
| `WATCHDOG_RESPAWN` | Orchestrator watchdog respawned pane | `"Pane respawned after death detection"` | `—` |
| `PUSH_REJECTED` | git push rejected by remote | `"Push rejected — tried rebase+retry; status: {result}"` | `—` |

### 4.3 log.md Maintenance Rules

- The file is created by the Claude agent during Phase 1 if it doesn't exist.
- Each new entry is appended as a new row to the table.
- The header and Logging Structure section are written once and never modified.
- After each append, the agent runs:
  ```
  git add log.md
  git commit -m "log(autofix): update audit log [autofix]"
  git push origin {push_branch}
  ```
- The orchestrator may also append `WATCHDOG_RESPAWN` entries by writing directly to the file (Phase 3 enhancement, not v1 scope).

---

## 5. `CLAUDE.md` — Generated Agent Instruction File

`CLAUDE.md` is generated by the orchestrator's `ClaudeLauncher` and written to `{local_path}/CLAUDE.md` before the Claude agent is spawned.

### 5.1 Generation

- **Template:** `templates/CLAUDE.md.j2` (Jinja2)
- **Written by:** `autofix/claude_launcher.py` → `render_and_write()`
- **Written at:** Orchestrator startup, before `launch_agent()`
- **Re-written on:** Every orchestrator startup (ensures config changes are reflected)
- **Committed by:** Claude agent during Phase 1

### 5.2 Security Constraints

The following values are **never** rendered into `CLAUDE.md`:
- SSH private key file contents (only the file *path* is embedded)
- Git credentials or tokens
- Webhook URLs (these are not needed by the agent — only the orchestrator notifies)
- Any value from environment variables that might contain secrets

### 5.3 File Stability

Because the orchestrator re-writes `CLAUDE.md` on every startup:
- If the operator changes `projects.yaml` (e.g., updates `max_fixes_per_hour`), the new `CLAUDE.md` is written and the agent picks up the new config on next restart/respawn.
- If a team member modifies `CLAUDE.md` directly in the repo, the orchestrator will overwrite it on next run. Document this behavior in `README.md`.

---

## 6. `.autofix_init` — Phase 1 Completion Marker

A zero-byte (or single-line) marker file written by the Claude agent to `{local_path}/.autofix_init` when Phase 1 (logging standardization) completes.

### Purpose
- Prevents the agent from re-running logging standardization on restart/respawn.
- The watchdog-respawned agent checks for this file and skips Phase 1 if found.

### Content
```
initialized
```

### Lifecycle
- **Written by:** Claude agent, at end of Phase 1
- **Read by:** Claude agent at every startup (before Phase 1 check)
- **Committed to Git:** Yes — agent includes it in the Phase 1 commit
- **Deleted by:** Never (manual deletion by operator resets Phase 1)

---

## 7. `autofix.log` — Orchestrator Event Log

Written to `{global.log_dir}/autofix.log` by the orchestrator (`autofix/logger.py`).

### Format
One JSON object per line (JSON Lines format):

```json
{"ts": "2025-01-01T10:00:00.000Z", "level": "INFO", "component": "orchestrator", "event": "startup_begin", "detail": "Reading config from ./projects.yaml"}
{"ts": "2025-01-01T10:00:00.100Z", "level": "INFO", "component": "config_loader", "event": "config_loaded", "detail": "Loaded 3 projects", "project": null}
{"ts": "2025-01-01T10:00:00.200Z", "level": "INFO", "component": "repo_manager", "event": "project_clone_ok", "project": "my-python-api", "detail": "Cloned to /home/user/projects/my-python-api"}
{"ts": "2025-01-01T10:00:01.500Z", "level": "INFO", "component": "tmux_manager", "event": "agent_launched", "project": "my-python-api", "detail": "Pane started in window my-python-api"}
{"ts": "2025-01-01T10:00:01.600Z", "level": "INFO", "component": "watchdog", "event": "watchdog_started", "detail": "Interval: 60s, watching 3 projects"}
{"ts": "2025-01-01T10:01:02.000Z", "level": "WARNING", "component": "watchdog", "event": "pane_dead_detected", "project": "my-python-api", "detail": "Pane for my-python-api not found"}
{"ts": "2025-01-01T10:01:03.500Z", "level": "INFO", "component": "watchdog", "event": "pane_respawned", "project": "my-python-api", "detail": "Pane successfully respawned"}
```

### Field Reference

| Field | Type | Always Present | Description |
|---|---|---|---|
| `ts` | string (ISO 8601 UTC) | Yes | Event timestamp |
| `level` | string | Yes | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `component` | string | Yes | Source component: `orchestrator`, `config_loader`, `repo_manager`, `tmux_manager`, `watchdog`, `notifier` |
| `event` | string | Yes | Event type identifier (see below) |
| `project` | string\|null | No | Project name if event is project-scoped; `null` for global events |
| `detail` | string | No | Human-readable description |
| `error` | string\|null | No | Exception message (for WARNING/ERROR events) |

### Event Catalogue

| Event | Level | Component | Description |
|---|---|---|---|
| `startup_begin` | INFO | orchestrator | `python autofix.py` invoked |
| `config_loaded` | INFO | config_loader | `projects.yaml` parsed + validated |
| `config_invalid` | ERROR | config_loader | Validation failure (before exit) |
| `prereq_check_ok` | INFO | orchestrator | All prerequisites satisfied |
| `prereq_missing` | ERROR | orchestrator | tmux/claude/git not found (before exit) |
| `project_clone_ok` | INFO | repo_manager | `git clone` succeeded |
| `project_clone_fail` | WARNING | repo_manager | `git clone` failed; project skipped |
| `project_pull_ok` | INFO | repo_manager | `git pull` succeeded |
| `project_pull_fail` | WARNING | repo_manager | `git pull` failed; project proceeds with stale code |
| `claude_md_written` | INFO | claude_launcher | `CLAUDE.md` written to `local_path` |
| `session_created` | INFO | tmux_manager | New tmux session created |
| `session_exists` | INFO | tmux_manager | Existing session found; reusing |
| `pane_created` | INFO | tmux_manager | Window/pane created for project |
| `agent_launched` | INFO | tmux_manager | Claude command sent to pane |
| `watchdog_started` | INFO | watchdog | Background thread started |
| `pane_dead_detected` | WARNING | watchdog | Dead pane found |
| `pane_respawned` | INFO | watchdog | Pane successfully respawned |
| `crash_loop_detected` | WARNING | watchdog | >5 restarts in 10 min; respawn paused |
| `notification_sent` | INFO | notifier | Webhook POST succeeded |
| `notification_failed` | WARNING | notifier | Webhook POST failed (non-fatal) |
| `dry_run_complete` | INFO | orchestrator | Dry-run finished; no side effects |

---

## 8. Internal State Models (In-Memory, Not Persisted)

These data structures are held in memory by the orchestrator and its components. They are not written to disk. If the orchestrator restarts, they are reset.

### 8.1 `RepoResult` Dataclass

```python
# autofix/repo_manager.py

@dataclass
class RepoResult:
    success: bool            # True if git operation succeeded
    action: str              # "clone" | "pull" | "clone_fresh" | "skip"
    project_name: str        # For logging
    error: Optional[str]     # stderr if failed, None if success
```

### 8.2 Watchdog Crash History (in `Watchdog._crash_history`)

```python
# autofix/watchdog.py

# Maps project name → list of crash timestamps (epoch floats)
# Used to detect crash loops (> CRASH_LOOP_THRESHOLD crashes within CRASH_LOOP_WINDOW_SECONDS)
_crash_history: dict[str, list[float]]

# Maps project name → epoch float (resume time after crash loop pause)
_paused_until: dict[str, float]
```

### 8.3 Notification Event Constants

```python
# autofix/notifier.py

VALID_EVENTS = frozenset({
    "fix_applied",
    "fix_failed",
    "verification_failed",
})
```

---

## 9. Canonical JSON Log Schema (Application-Level)

This is the schema that all AutoFix-injected logging frameworks must produce. The Claude agent configures each project's logging framework to emit this format.

```json
{
  "timestamp": "2025-01-01T12:00:00.000Z",
  "level": "INFO",
  "logger": "myapp.module.submodule",
  "message": "Human-readable log message",
  "context": {
    "request_id": "abc-123",
    "user_id": "u-456",
    "trace_id": "trace-xyz"
  },
  "error": {
    "type": "ValueError",
    "message": "invalid literal for int() with base 10: 'abc'",
    "stack": "Traceback (most recent call last):\n  File \"api/routes.py\", line 42, in handler\n    user_id = int(raw_id)\nValueError: invalid literal for int() with base 10: 'abc'"
  }
}
```

### Field Definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `timestamp` | string | **Yes** | ISO 8601 with milliseconds, UTC (`Z` suffix). Example: `2025-01-01T12:00:00.123Z` |
| `level` | string | **Yes** | One of: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `logger` | string | **Yes** | Logger name. Typically the module path: `myapp.api.routes`. Never empty. |
| `message` | string | **Yes** | Human-readable description. Never null. |
| `context` | object | No | Arbitrary key-value pairs for structured context (request ID, user ID, etc.) |
| `context.request_id` | string | No | Trace/request correlation ID |
| `context.user_id` | string | No | User identifier if applicable |
| `error` | object | No | Present only when level is ERROR or CRITICAL and an exception was caught |
| `error.type` | string | No | Exception class name: `ValueError`, `KeyError`, `TypeError`, etc. |
| `error.message` | string | No | Exception message string |
| `error.stack` | string | No | Full stack trace as a single string with `\n` separators |

### Schema Alignment

This schema is a subset of the [Elastic Common Schema (ECS)](https://www.elastic.co/guide/en/ecs/current/) and [OpenTelemetry Log Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/).

### Framework Configuration Targets

| Language | Framework | Key Config Points |
|---|---|---|
| Python | `structlog` | `TimeStamper(fmt="iso", utc=True)` + `JSONRenderer()` + file handler |
| Python (alt) | `loguru` | `serialize=True` + custom `format` function mapping to canonical fields |
| Node.js | `winston` | `format.combine(format.timestamp(), format.json())` + File transport |
| Node.js (alt) | `pino` | Default JSONL output; configure `timestamp: pino.stdTimeFunctions.isoTime` |
| Ruby | `semantic_logger` | `:json` formatter + File appender |
| Go | `zap` | `zap.NewProduction()` with `zapcore.InfoLevel`; JSON encoder writing to file + stdout |
