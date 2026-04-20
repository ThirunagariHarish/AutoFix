# PRD: AutoFix — Autonomous Multi-Project Log Monitoring & Auto-Fix System

**Version:** 1.0  
**Status:** Draft — Ready for Architecture Review  
**Author:** Nova (PM)  
**Last Updated:** 2025-01-01  
**Audience:** Atlas (Architect), Devin (Implementation Engineer)

---

## 1. Problem

### 1.1 Problem Statement

Software teams running multiple Git-backed services on VPS infrastructure spend disproportionate time on reactive maintenance: detecting log errors, diagnosing root causes, applying fixes, deploying, and verifying. This is largely mechanical work that blocks higher-value engineering.

Three compounding problems exist today:

1. **Inconsistent logging**: Different projects use different logging libraries, formats, and verbosity levels. This makes cross-project error correlation impossible and slows diagnosis.
2. **No automated remediation loop**: Errors are detected by humans (or basic alerting tools) long after they occur. Fixes require manual: `ssh → diagnose → edit → commit → push → verify` cycles.
3. **Tooling fragmentation**: Each project has different deploy scripts, log locations, and SSH access patterns. There is no unified operator.

### 1.2 Why Now

The emergence of autonomous coding agents (Claude Code CLI with `--dangerously-skip-permissions`) makes it practical for the first time to have a software agent that can: read logs, understand code context, write a fix, commit it, push it, and verify the result — all without human intervention in a tight loop.

### 1.3 Prior Art & Competitive Landscape

| Tool | Approach | Gap |
|---|---|---|
| **Datadog Watchdog** | ML anomaly detection + alert routing | No auto-fix; requires human response; expensive |
| **Shoreline.io** | Resource-oriented scripting (Op DSL) for incident response | Requires proprietary agents installed per-host; no code-writing ability |
| **PagerDuty AIOps** | Alert correlation + on-call routing | Purely notification-based; no remediation |
| **Ansible AWX** | Playbook-based remediation | Requires pre-authored playbooks; cannot author novel fixes |
| **GitHub Copilot Autofix** | Code scanning + PR suggestions | PR-based only; no live log monitoring; no deployment verification |
| **AutoFix (this project)** | LLM agent per project, monitors live logs, authors + deploys fixes autonomously | Novel approach; no direct equivalent |

**Sources:**
- Datadog Watchdog: https://www.datadoghq.com/blog/datadog-watchdog/
- Shoreline.io architecture: https://shoreline.io/
- Ansible AWX: https://github.com/ansible/awx
- GitHub Copilot Autofix: https://github.blog/2023-11-08-github-copilot-autofix/

---

## 2. Target Users & Jobs-to-Be-Done

### 2.1 Primary Persona — The Solo/Small-Team Backend Engineer

**Name:** "Dev-Ops Dana"  
**Context:** Runs 3–10 personal or small-team projects on one or more VPS instances. Uses Git (GitHub/GitLab/Gitea) for version control. Does not have a dedicated DevOps/SRE person.  
**Pain:** Wakes up to 3am error emails. Spends 2–4 hours/week manually fixing recurring errors across projects.  
**Goal:** Set it and forget it. Have a system that monitors every project around the clock and fixes itself.  
**Technical comfort:** High — comfortable with YAML config files, tmux, SSH keys, Python scripts.  
**Machine:** MacBook Pro or Linux desktop running tmux as a long-lived terminal environment.

### 2.2 Secondary Persona — The Platform/Infra Engineer at a Startup

**Name:** "Infra Ivan"  
**Context:** Maintains 10–30 microservices across staging and production VPS clusters. Has some monitoring (Datadog/Grafana) but no auto-remediation.  
**Pain:** Alert fatigue; team spends 30% of sprint capacity on incident response.  
**Goal:** Autonomous first-responder that handles known error patterns so humans only see novel issues.  
**Technical comfort:** Very high — writes Python, knows paramiko/fabric, manages tmux sessions.

### 2.3 Jobs-to-Be-Done

| Job | Trigger | Desired Outcome |
|---|---|---|
| **Bootstrap logging** | New project onboarded; no standard logging | All projects emit structured JSON logs to predictable paths |
| **Detect errors early** | Service log contains ERROR/CRITICAL events | Alert captured and diagnosed within seconds |
| **Auto-fix known errors** | Error is diagnosable from code + log context | Fix committed, pushed, deployed, verified — no human needed |
| **Audit trail** | "What did AutoFix do last night?" | Git commits + `log.md` file per project showing all actions |
| **Parallel monitoring** | Multiple projects active simultaneously | Each project gets its own isolated agent session |

---

## 3. Goals & Non-Goals

### 3.1 Goals (In Scope)

| # | Goal |
|---|---|
| G1 | Single-command startup that brings up all project monitors |
| G2 | Config-driven: add/remove projects by editing `projects.yaml` only |
| G3 | Auto-clone repos on first run; auto-pull on subsequent runs |
| G4 | Spawn one isolated tmux pane per project; no cross-project interference |
| G5 | Each pane runs a fully autonomous Claude Code agent session |
| G6 | Agent enforces standardized logging in every project it monitors |
| G7 | Agent continuously monitors logs and acts on detected errors |
| G8 | Full fix-commit-push-SSH-verify cycle is automated per error event |
| G9 | Every action by an agent is recorded in the project's `log.md` |
| G10 | System is portable: runs on macOS and Linux with minimal deps |
| G11 | Graceful handling of agent crashes — pane restarts automatically |

### 3.2 Non-Goals (Explicitly Out of Scope)

| # | Non-Goal | Rationale |
|---|---|---|
| NG1 | Web UI or dashboard | Pure script-based tool; tmux is the interface |
| NG2 | Cloud provider SDKs (AWS ECS, GCP Cloud Run, etc.) | VPS-only; no managed container platforms |
| NG3 | Database schema migrations as auto-fixes | Too high risk; requires human review |
| NG4 | Security vulnerability patches | Requires human approval; out of autonomous scope |
| NG5 | Multi-user RBAC / permissions system | Single-operator tool |
| NG6 | Windows support | tmux not natively available on Windows |
| NG7 | Log streaming to external SaaS (Datadog, Splunk) | Out of scope for v1 |
| NG8 | AI model selection / model switching | Claude Code CLI only; no model configuration UI |
| NG9 | Auto-rollback on failed deployments | v2 roadmap item |
| NG10 | Parallel fix attempts (only one fix per error at a time) | Reduces risk of conflicting commits |

---

## 4. Success Metrics

| Metric | Target (v1) | Measurement Method |
|---|---|---|
| **Time-to-first-fix** (error detected → fix pushed) | < 10 minutes for known error patterns | Timestamps in `log.md` |
| **Logging standardization rate** | 100% of onboarded projects have standard logging within first run | Presence of `log.md` + logging framework import in codebase |
| **Agent uptime** | ≥ 99% of time each tmux pane is alive (auto-restart on crash) | Pane watchdog check every 60s |
| **False-fix rate** (fix pushed but broke the build / tests fail) | < 5% of auto-fixes | CI status check post-push OR deploy verification failure |
| **Zero human interventions** for P2/P3 errors | > 80% resolved autonomously | Git commit log authored by AutoFix agent |
| **Cold start time** (run script → all panes monitoring) | < 60 seconds for ≤ 10 projects | Wall clock measurement |
| **Config schema compliance** | 100% of `projects.yaml` configs validated at startup; bad configs rejected with clear error | Validation output at launch |

---

## 5. User Stories

*(Linked to full acceptance criteria in `stories.md`)*

| ID | Story | Priority |
|---|---|---|
| US-01 | As Dana, I want to run one command to start monitoring all my projects, so that I don't have to manually set up each project. | P0 |
| US-02 | As Dana, I want to define all project configs in a single `projects.yaml` file, so that adding a new project is a one-line change. | P0 |
| US-03 | As Dana, I want each project to be cloned automatically if not already local, so that I don't need to manually clone repos. | P0 |
| US-04 | As Dana, I want each project to open in its own tmux pane, so that I can visually inspect any project's agent activity at a glance. | P0 |
| US-05 | As Dana, I want each Claude agent to check and enforce standardized logging, so that all projects emit logs in a consistent, parseable format. | P0 |
| US-06 | As Dana, I want each agent to continuously monitor logs for errors, so that errors are caught immediately without me watching. | P0 |
| US-07 | As Dana, I want each agent to automatically apply a fix, commit it, and push it when an error is detected, so that my projects self-heal. | P0 |
| US-08 | As Dana, I want the agent to SSH into the VPS after a push to verify the deployment succeeded, so that I know the fix is actually live. | P0 |
| US-09 | As Dana, I want each agent to return to monitoring after a fix cycle, so that monitoring is continuous and uninterrupted. | P0 |
| US-10 | As Dana, I want every agent action logged to a `log.md` in the project root, so that I can audit what changed and when. | P1 |
| US-11 | As Ivan, I want the system to restart a crashed agent pane automatically, so that a single project failure doesn't kill monitoring. | P1 |
| US-12 | As Ivan, I want config validation to fail fast with a clear error message at startup, so that misconfigured projects don't silently fail. | P1 |
| US-13 | As Dana, I want each project's CLAUDE.md to contain precise instructions for the autonomous agent, so that agent behavior is deterministic and auditable. | P1 |
| US-14 | As Ivan, I want to configure per-project branch names and VPS SSH targets, so that staging and production projects can coexist in the same config. | P1 |
| US-15 | As Dana, I want the system to handle SSH key authentication to both Git remotes and VPS, so that no passwords are needed in the loop. | P1 |
| US-16 | As Ivan, I want to be able to mark certain error patterns as "human-review-only" in the config, so that sensitive fixes are never auto-committed. | P2 |
| US-17 | As Dana, I want the agent to create a `log.md` documenting the logging structure when it first standardizes logging in a project, so that I understand what was changed. | P1 |
| US-18 | As Ivan, I want a dry-run mode that shows what would happen without making changes, so that I can safely test the system against existing projects. | P2 |

---

## 6. Functional Requirements

### FR-1: Orchestrator Entry Point

**FR-1.1** The system SHALL provide a single executable entry point (e.g., `autofix.py` or `autofix.sh`) that accepts zero required arguments.  
**FR-1.2** The orchestrator SHALL read `projects.yaml` from a configurable path (default: `./projects.yaml` in the script's working directory).  
**FR-1.3** The orchestrator SHALL validate `projects.yaml` against the defined schema at startup before taking any action. Any schema violation SHALL terminate startup with a human-readable error message identifying the offending field.  
**FR-1.4** The orchestrator SHALL create a named tmux session (default name: `autofix`) if one does not already exist.  
**FR-1.5** On re-run, the orchestrator SHALL detect the existing tmux session and attach to it rather than creating duplicate sessions.

### FR-2: Repository Management

**FR-2.1** For each project in config, the orchestrator SHALL check whether the `local_path` directory exists.  
**FR-2.2** If `local_path` does not exist, the orchestrator SHALL execute `git clone <repo_url> <local_path>`.  
**FR-2.3** If `local_path` exists, the orchestrator SHALL execute `git pull` on the configured branch.  
**FR-2.4** Git operations SHALL be authenticated via SSH keys configured on the host machine; no credential prompts are permitted.  
**FR-2.5** Clone/pull failures SHALL be logged to orchestrator output and the project's pane SHALL display the error; other projects SHALL continue unaffected.

### FR-3: tmux Pane Management

**FR-3.1** The orchestrator SHALL create one tmux window/pane per project named after the project's `name` field.  
**FR-3.2** Each pane SHALL `cd` to the project's `local_path` before launching the Claude agent.  
**FR-3.3** Each pane SHALL launch: `claude --dangerously-skip-permissions` with the CLAUDE.md in the project root providing agent instructions.  
**FR-3.4** The orchestrator SHALL implement a watchdog process that checks each pane's liveness every configurable interval (default: 60 seconds).  
**FR-3.5** If a pane is detected as dead/exited, the watchdog SHALL re-spawn it automatically, respecting the same startup sequence (git pull → cd → claude).  
**FR-3.6** Pane names SHALL be stable across restarts (same project → same pane name).

### FR-4: CLAUDE.md Instruction File

**FR-4.1** The orchestrator SHALL generate a `CLAUDE.md` file in each project's `local_path` before launching the Claude agent.  
**FR-4.2** `CLAUDE.md` SHALL contain the full autonomous agent instruction set (see Section 9 for template).  
**FR-4.3** `CLAUDE.md` SHALL be populated with project-specific values from `projects.yaml` (project name, VPS SSH host, branch, log paths, etc.).  
**FR-4.4** `CLAUDE.md` SHALL be committed to the repository by the agent as part of the initial logging standardization step.  
**FR-4.5** `CLAUDE.md` SHALL NOT contain sensitive credentials (SSH private key paths are referenced, not embedded).

### FR-5: Logging Standardization

**FR-5.1** The Claude agent SHALL detect the project's primary language by inspecting file extensions and build manifests (`package.json`, `requirements.txt`, `Gemfile`, `go.mod`, etc.).  
**FR-5.2** The agent SHALL check whether a standardized logging framework is already configured:  
  - Python: `structlog` or `loguru` imported and configured  
  - Node.js: `winston` or `pino` imported and configured  
  - Ruby: `semantic_logger` configured  
  - Go: `zap` (uber-go/zap) configured  
**FR-5.3** If no standard logging is detected, the agent SHALL inject the appropriate logging framework:  
  - Add dependency to `requirements.txt` / `package.json` / `Gemfile` / `go.mod`  
  - Create or update a logging config file (e.g., `logging_config.py`, `logger.js`)  
  - Update the project's main entry point to use the new logger  
**FR-5.4** All injected loggers SHALL output structured JSON logs conforming to the canonical schema defined in Section 10.  
**FR-5.5** Log output path SHALL be configurable via `projects.yaml` (default: `./logs/app.log`).  
**FR-5.6** After standardization, the agent SHALL create or update `log.md` at the project root (see Section 11 for template).  
**FR-5.7** The agent SHALL commit standardization changes with message: `chore(autofix): standardize logging framework [automated]`.  
**FR-5.8** The agent SHALL push the commit to the configured branch.

### FR-6: Continuous Log Monitoring

**FR-6.1** The agent SHALL continuously tail the configured log file path (e.g., `tail -f logs/app.log` or equivalent).  
**FR-6.2** The agent SHALL parse log lines for ERROR and CRITICAL level events.  
**FR-6.3** The agent SHALL apply configurable debounce logic: identical errors within a configurable window (default: 5 minutes) SHALL NOT trigger duplicate fix attempts.  
**FR-6.4** The agent SHALL maintain an in-session error history to avoid redundant fixes within a single monitoring session.  
**FR-6.5** Error detection SHALL cover: exception stack traces, HTTP 5xx patterns, database connection failures, import errors, out-of-memory signals.

### FR-7: Auto-Fix Cycle

**FR-7.1** On error detection, the agent SHALL read the relevant source file(s) identified in the stack trace.  
**FR-7.2** The agent SHALL diagnose the root cause by correlating the error message, stack trace, and source code.  
**FR-7.3** The agent SHALL apply a targeted code fix — only modifying files directly implicated in the error.  
**FR-7.4** The agent SHALL run available tests (`pytest`, `npm test`, `go test`, etc.) before committing. If tests fail, the agent SHALL revert the fix and log the failure.  
**FR-7.5** If tests pass (or no tests exist), the agent SHALL commit with message: `fix(<scope>): <brief description> [autofix]`.  
**FR-7.6** The agent SHALL push the commit to the configured branch.  
**FR-7.7** Push failures (e.g., rejected due to remote changes) SHALL trigger a `git pull --rebase` and retry once.  
**FR-7.8** After a successful push, the agent SHALL proceed to deployment verification (FR-8).  
**FR-7.9** Errors listed in `blocked_patterns` in `projects.yaml` SHALL NOT be auto-fixed; they SHALL be logged to `log.md` as "Human review required" and monitoring SHALL continue.

### FR-8: Deployment Verification

**FR-8.1** After a successful push, the agent SHALL SSH to the configured `vps_host` using the configured `vps_user` and `ssh_key_path`.  
**FR-8.2** The agent SHALL execute the configured `verify_command` on the VPS (e.g., `systemctl status myapp`, `docker ps | grep myapp`, `curl -s localhost:3000/health`).  
**FR-8.3** A verification is considered successful if `verify_command` exits with code 0 and optionally matches a configured `verify_output_contains` string.  
**FR-8.4** If verification fails, the agent SHALL log the failure details to `log.md` and send a notification if configured (see FR-9).  
**FR-8.5** Verification timeout SHALL be configurable (default: 30 seconds).  
**FR-8.6** After verification (success or failure), the agent SHALL return to the monitoring loop (FR-6).

### FR-9: Notifications (Optional / P2)

**FR-9.1** The system SHALL support optional webhook-based notifications (e.g., Slack, Discord) for: fix applied, fix failed, verification failed.  
**FR-9.2** Webhook URL SHALL be configurable per-project in `projects.yaml`.  
**FR-9.3** Notification payload SHALL include: project name, error summary, fix commit SHA, verification status.

### FR-10: log.md Maintenance

**FR-10.1** The agent SHALL create `log.md` in the project root on first run if it does not exist.  
**FR-10.2** The agent SHALL append a timestamped entry to `log.md` for every: logging standardization event, error detection, fix attempt (success or failure), verification result.  
**FR-10.3** `log.md` entries SHALL include: ISO 8601 timestamp, event type, description, commit SHA (if applicable), operator (always "AutoFix Agent").  
**FR-10.4** `log.md` SHALL be committed and pushed after each update.

---

## 7. Non-Functional Requirements

### NFR-1: Portability
- **NFR-1.1** The system SHALL run on macOS 12+ and Ubuntu 20.04+ with no OS-specific dependencies beyond tmux, Python 3.9+, and git.
- **NFR-1.2** All Python dependencies SHALL be declared in a `requirements.txt` with pinned versions.
- **NFR-1.3** The system SHALL NOT require root/sudo access.

### NFR-2: Reliability
- **NFR-2.1** A single project failure (clone error, agent crash, SSH timeout) SHALL NOT affect other project monitors.
- **NFR-2.2** The watchdog SHALL recover a crashed pane within 2× the watchdog interval (default: 120 seconds max recovery time).
- **NFR-2.3** All orchestrator-level errors SHALL be written to a central `autofix.log` file.

### NFR-3: Security
- **NFR-3.1** `projects.yaml` SHALL NOT contain plaintext SSH passwords. Only key-path references are permitted.
- **NFR-3.2** `CLAUDE.md` SHALL NOT contain private keys, tokens, or passwords.
- **NFR-3.3** The system SHALL NOT auto-fix errors categorized as security vulnerabilities (pattern matching on CVE, OWASP, injection keywords).
- **NFR-3.4** All Git commits made by the agent SHALL be signed with a configurable Git identity (name + email) to distinguish from human commits.
- **NFR-3.5** SSH connections to VPS SHALL use key-based auth only; password auth SHALL NOT be attempted.

### NFR-4: Auditability
- **NFR-4.1** Every automated fix SHALL be traceable to a Git commit with the `[autofix]` tag in the message.
- **NFR-4.2** `log.md` per project SHALL provide a human-readable audit trail of all agent actions.
- **NFR-4.3** The orchestrator SHALL emit structured log lines (timestamped) to stdout and `autofix.log`.

### NFR-5: Extensibility
- **NFR-5.1** Adding support for a new programming language's logging framework SHALL require only: adding a detection rule and a logging config template — no core orchestrator changes.
- **NFR-5.2** Config schema versioning SHALL be supported via a `schema_version` field in `projects.yaml`.

### NFR-6: Performance
- **NFR-6.1** Startup time (script invocation → all panes running) SHALL be ≤ 60 seconds for ≤ 10 projects on a standard developer machine.
- **NFR-6.2** Log tailing latency (line written → agent reads it) SHALL be ≤ 5 seconds.
- **NFR-6.3** The orchestrator watchdog loop SHALL consume < 1% CPU on idle.

---

## 8. Config File Schema — `projects.yaml`

### 8.1 Top-Level Structure

```yaml
schema_version: "1.0"

global:
  tmux_session_name: "autofix"         # Name of the tmux session
  watchdog_interval_seconds: 60        # How often to check pane liveness
  claude_command: "claude --dangerously-skip-permissions"  # Claude CLI invocation
  git_author_name: "AutoFix Agent"
  git_author_email: "autofix@local"
  log_dir: "./logs"                    # Orchestrator log output directory

projects:
  - name: "my-api"                     # Unique project identifier (used as tmux pane name)
    repo_url: "git@github.com:user/my-api.git"
    local_path: "/home/user/projects/my-api"
    branch: "main"
    language: "python"                 # python | nodejs | ruby | go | auto (auto-detect)
    log_path: "logs/app.log"           # Relative to local_path; path agent tails
    
    vps:
      host: "192.168.1.100"
      user: "deploy"
      ssh_key_path: "~/.ssh/id_rsa"
      verify_command: "systemctl status my-api"
      verify_output_contains: "active (running)"  # Optional; substring match
      verify_timeout_seconds: 30

    git:
      push_branch: "main"
      pull_before_fix: true            # git pull --rebase before applying fix
      commit_sign: false               # GPG sign commits (requires GPG setup)

    monitoring:
      error_debounce_minutes: 5        # Min gap between fix attempts for same error
      max_fixes_per_hour: 3            # Rate limit on auto-fixes
      blocked_patterns:                # Errors matching these will NOT be auto-fixed
        - "CVE-"
        - "SQL injection"
        - "database migration"

    notifications:                     # Optional
      webhook_url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
      on_events:
        - "fix_applied"
        - "fix_failed"
        - "verification_failed"

  - name: "my-frontend"
    repo_url: "git@github.com:user/my-frontend.git"
    local_path: "/home/user/projects/my-frontend"
    branch: "main"
    language: "nodejs"
    log_path: "logs/app.log"
    
    vps:
      host: "192.168.1.101"
      user: "deploy"
      ssh_key_path: "~/.ssh/id_rsa"
      verify_command: "pm2 status my-frontend"
      verify_output_contains: "online"
      verify_timeout_seconds: 30

    git:
      push_branch: "main"
      pull_before_fix: true

    monitoring:
      error_debounce_minutes: 5
      max_fixes_per_hour: 2
      blocked_patterns: []

    notifications: null
```

### 8.2 Schema Field Reference

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `schema_version` | string | Yes | — | Schema version for future compatibility |
| `global.tmux_session_name` | string | No | `"autofix"` | tmux session name |
| `global.watchdog_interval_seconds` | int | No | `60` | Pane liveness check interval |
| `global.claude_command` | string | No | `"claude --dangerously-skip-permissions"` | Claude CLI invocation string |
| `global.git_author_name` | string | No | `"AutoFix Agent"` | Git commit author name |
| `global.git_author_email` | string | No | `"autofix@local"` | Git commit author email |
| `projects[].name` | string | Yes | — | Unique project ID; used as tmux pane name |
| `projects[].repo_url` | string | Yes | — | Git remote URL (SSH format preferred) |
| `projects[].local_path` | string | Yes | — | Absolute local filesystem path |
| `projects[].branch` | string | No | `"main"` | Branch to monitor and push fixes to |
| `projects[].language` | string | No | `"auto"` | `python`, `nodejs`, `ruby`, `go`, `auto` |
| `projects[].log_path` | string | No | `"logs/app.log"` | Log file path relative to `local_path` |
| `projects[].vps.host` | string | Yes | — | VPS IP or hostname |
| `projects[].vps.user` | string | Yes | — | SSH username on VPS |
| `projects[].vps.ssh_key_path` | string | Yes | — | Path to SSH private key |
| `projects[].vps.verify_command` | string | Yes | — | Command run on VPS post-push |
| `projects[].vps.verify_output_contains` | string | No | `null` | Optional substring to match in verify output |
| `projects[].vps.verify_timeout_seconds` | int | No | `30` | SSH command timeout |
| `projects[].git.push_branch` | string | No | Same as `branch` | Branch to push fixes to |
| `projects[].git.pull_before_fix` | bool | No | `true` | Pull before applying fix |
| `projects[].monitoring.error_debounce_minutes` | int | No | `5` | Min minutes between fix attempts for same error |
| `projects[].monitoring.max_fixes_per_hour` | int | No | `3` | Rate limit on auto-fixes |
| `projects[].monitoring.blocked_patterns` | list[str] | No | `[]` | Regex/substring patterns that block auto-fix |
| `projects[].notifications.webhook_url` | string | No | `null` | Webhook for event notifications |
| `projects[].notifications.on_events` | list[str] | No | `[]` | Events that trigger notification |

### 8.3 Validation Rules

1. `projects[].name` MUST be unique across all projects.
2. `projects[].local_path` MUST be an absolute path.
3. `projects[].language` MUST be one of: `python`, `nodejs`, `ruby`, `go`, `auto`.
4. `projects[].vps.ssh_key_path` MUST be resolvable (path exists on filesystem).
5. `projects[].monitoring.max_fixes_per_hour` MUST be ≥ 1 and ≤ 20.
6. `schema_version` MUST be present; warn on unknown versions.

---

## 9. Component Breakdown

| Component | Responsibility | Technology |
|---|---|---|
| **`autofix.py`** (Orchestrator) | Parse config, validate schema, clone/pull repos, create tmux session/panes, launch agents, run watchdog | Python 3.9+ |
| **`config/schema.py`** | YAML schema validation, Pydantic models for all config fields | Pydantic v2 + PyYAML |
| **`tmux_manager.py`** | tmux session/window/pane lifecycle management, watchdog loop | libtmux (Python tmux wrapper) |
| **`repo_manager.py`** | `git clone`, `git pull`, error handling for Git operations | subprocess + gitpython |
| **`claude_launcher.py`** | Construct CLAUDE.md from template + project config, send to pane | Jinja2 templates |
| **`CLAUDE.md.j2`** (Template) | Jinja2 template for autonomous agent instructions | Jinja2 |
| **`logging_templates/`** | Language-specific logging config snippets for injection | Python dicts / plain files |
| **`projects.yaml`** | User-edited config file | YAML |
| **`autofix.log`** | Orchestrator-level event log | Plain text / structured JSON |

---

## 10. Canonical Log Schema

All injected logging frameworks SHALL produce JSON log lines conforming to:

```json
{
  "timestamp": "2025-01-01T12:00:00.000Z",
  "level": "INFO",
  "logger": "myapp.module.submodule",
  "message": "Human-readable log message",
  "context": {
    "request_id": "abc-123",
    "user_id": "u-456"
  },
  "error": {
    "type": "ValueError",
    "message": "invalid literal for int()",
    "stack": "Traceback (most recent call last):\n  File ..."
  }
}
```

**Required fields:** `timestamp`, `level`, `logger`, `message`  
**Optional fields:** `context`, `error`  
**Level values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`  
**Timestamp format:** ISO 8601 with milliseconds, UTC (`Z`)

This schema is aligned with the Elastic Common Schema (ECS) subset. Source: https://www.elastic.co/guide/en/ecs/current/

---

## 11. CLAUDE.md Agent Instruction Template (Specification)

The generated `CLAUDE.md` placed in each project root SHALL instruct the Claude agent to execute the following stateful loop. This section defines what the template MUST contain — not the exact template text (which Atlas/Devin will implement).

### Required Sections in `CLAUDE.md`:

**Section 1 — Identity & Constraints**
- Agent is operating in fully autonomous mode
- Agent MUST NOT interact with humans or wait for input
- Agent MUST NOT modify files outside the project root
- Agent MUST NOT push to any branch other than `{push_branch}`
- All commits MUST include `[autofix]` in message

**Section 2 — Phase 1: Logging Standardization (Run Once)**
1. Detect project language (inspect `{language}` config or auto-detect)
2. Check for existing standard logging framework
3. If absent: inject logging framework (see FR-5), install deps, configure output path to `{log_path}`
4. Create/update `log.md` with logging structure documentation
5. Commit + push: `chore(autofix): standardize logging framework [autofix]`
6. Mark Phase 1 complete (write `.autofix_init` marker file)

**Section 3 — Phase 2: Continuous Monitoring Loop**
```
LOOP forever:
  1. Tail {log_path} for new lines
  2. FOR each line:
     IF level == ERROR or CRITICAL:
       a. Extract: timestamp, error type, message, stack trace
       b. Check debounce: if same error seen within {debounce_minutes} minutes → SKIP
       c. Read implicated source files from stack trace
       d. Diagnose root cause
       e. Apply minimal targeted fix
       f. Run tests (if available)
       g. IF tests pass OR no tests:
            i.  git add -A
            ii. git commit -m "fix(<scope>): <description> [autofix]"
            iii. git push origin {push_branch}
            iv.  SSH to {vps_host} as {vps_user} using {ssh_key_path}
            v.   Run: {verify_command}
            vi.  IF verify succeeds: log SUCCESS to log.md
            vii. IF verify fails: log FAILURE to log.md
          ELSE (tests fail):
            git checkout -- .   # revert fix
            log REVERT to log.md
       h. Append entry to log.md, commit + push log.md
  3. Sleep 1 second, continue loop
END LOOP
```

**Section 4 — Error Escalation Rules**
- If error matches any `blocked_pattern`: log "Human review required" → continue loop
- If fix attempt count for same error exceeds 3: stop attempting, log "Max retries exceeded"
- If push is rejected: `git pull --rebase`, retry push once

**Section 5 — Project-Specific Values** (injected from config)
- `{project_name}`, `{branch}`, `{push_branch}`, `{log_path}`
- `{vps_host}`, `{vps_user}`, `{ssh_key_path}`, `{verify_command}`, `{verify_output_contains}`
- `{debounce_minutes}`, `{max_fixes_per_hour}`, `{blocked_patterns}`

---

## 12. log.md Per-Project Template (Specification)

The agent SHALL create a `log.md` with:

```markdown
# AutoFix Log — {project_name}

## Logging Structure
- **Framework:** {logging_framework} ({version})
- **Output path:** {log_path}
- **Format:** JSON (Elastic Common Schema subset)
- **Log levels in use:** DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Key fields:** timestamp, level, logger, message, context, error

## Agent Activity Log

| Timestamp | Event | Description | Commit SHA |
|---|---|---|---|
| 2025-01-01T10:00:00Z | LOGGING_STANDARDIZED | Injected structlog; updated main.py | abc1234 |
| 2025-01-01T11:30:00Z | ERROR_DETECTED | ValueError in api/routes.py:42 | — |
| 2025-01-01T11:31:00Z | FIX_APPLIED | Added null check before int() cast | def5678 |
| 2025-01-01T11:32:00Z | DEPLOY_VERIFIED | systemctl status: active (running) | — |
```

---

## 13. User Flows

### Flow A — Cold Start (First Run)

```
User runs: python autofix.py

  ├── [Orchestrator] Validate projects.yaml schema
  │     └── FAIL: Print error, exit 1
  │     └── PASS: Continue
  │
  ├── [Orchestrator] For each project (parallel):
  │     ├── Check local_path exists
  │     │     ├── NO  → git clone repo_url local_path
  │     │     └── YES → git pull origin branch
  │     │
  │     └── Generate CLAUDE.md from template + project config
  │
  ├── [tmux_manager] Create tmux session "autofix"
  │
  ├── [tmux_manager] For each project:
  │     ├── Create named pane: {project.name}
  │     ├── cd {local_path}
  │     └── Send: claude --dangerously-skip-permissions
  │
  ├── [Orchestrator] Start watchdog loop (every 60s)
  │     └── Check each pane alive → respawn if dead
  │
  └── [Orchestrator] Attach to tmux session (user sees all panes)
```

### Flow B — Agent Startup (Per Pane, Phase 1)

```
Claude agent starts in project pane

  ├── Read CLAUDE.md for instructions
  ├── Detect project language
  ├── Check logging framework
  │     ├── PRESENT: Skip to Phase 2
  │     └── ABSENT:
  │           ├── Install logging framework
  │           ├── Configure JSON output to log_path
  │           ├── Create log.md
  │           ├── git add, commit, push
  │           └── Write .autofix_init marker
  │
  └── Proceed to Phase 2 (monitoring loop)
```

### Flow C — Error Detected → Fix → Verify Cycle

```
Agent tailing logs/app.log detects:
  ERROR | 2025-01-01T11:30:00Z | api.routes | NoneType has no attribute 'id'

  ├── Check debounce table → not seen recently → proceed
  ├── Extract stack trace → implicated file: api/routes.py:42
  ├── Read api/routes.py
  ├── Diagnose: user object may be None before .id access
  ├── Apply fix: add `if user is None: return 404`
  ├── Run: pytest (if exists)
  │     ├── FAIL → git checkout -- api/routes.py → log REVERT → continue loop
  │     └── PASS →
  │           ├── git add api/routes.py
  │           ├── git commit -m "fix(api): guard None user before .id access [autofix]"
  │           ├── git push origin main
  │           │     └── REJECTED → git pull --rebase → retry push
  │           ├── SSH deploy@192.168.1.100
  │           ├── Run: systemctl status my-api
  │           │     ├── active (running) → log SUCCESS
  │           │     └── failed → log FAILURE, notify webhook
  │           ├── Append to log.md, git commit log.md, push
  │           └── Return to tailing logs/app.log
```

### Flow D — Watchdog Recovery

```
Watchdog fires (every 60s)

  ├── For each project pane:
  │     ├── tmux list-panes → check #{pane_dead}
  │     │     ├── ALIVE → do nothing
  │     │     └── DEAD →
  │     │           ├── Log: "Pane {name} dead, respawning"
  │     │           ├── Kill pane
  │     │           ├── Create new pane with same name
  │     │           ├── git pull origin branch
  │     │           └── Launch claude --dangerously-skip-permissions
  │
  └── Sleep {watchdog_interval_seconds}
```

---

## 14. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|---|---|
| `projects.yaml` missing | Orchestrator exits with: `ERROR: projects.yaml not found at ./projects.yaml` |
| `projects.yaml` invalid YAML syntax | Orchestrator exits with YAML parse error and line number |
| `projects.yaml` fails schema validation | Orchestrator prints each failing field, exits 1 |
| Git clone fails (no network / auth issue) | Project pane shows error; other projects unaffected; watchdog retries on next cycle |
| `local_path` is not a valid git repo | Agent logs error; attempts `git clone` to fresh path `{local_path}_fresh` |
| Claude agent exits immediately (bad CLAUDE.md) | Watchdog detects dead pane, respawns |
| Log file does not exist yet | Agent waits/polls for log file to appear; continues polling every 30s |
| Log file rotated/truncated | Agent re-opens log file from start; continues from new position |
| Test suite fails after fix | Agent reverts fix with `git checkout -- .`; logs "Fix reverted — tests failed"; continues monitoring |
| Push rejected (remote ahead) | Agent runs `git pull --rebase`, retries push once; if still rejected, logs and skips |
| SSH to VPS times out | Agent logs "VPS verification timed out after {timeout}s"; continues monitoring |
| VPS verify_command exits non-zero | Agent logs "Deployment verification FAILED"; triggers webhook notification if configured |
| Error matches `blocked_pattern` | Agent appends "Human review required" to `log.md`; does NOT fix; continues monitoring |
| `max_fixes_per_hour` reached | Agent pauses fix attempts for remainder of hour; continues monitoring and logging |
| Same error triggers > 3 fix attempts | Agent marks error as "max retries exceeded" in `log.md`; stops fixing that specific error |
| tmux not installed | Orchestrator exits with: `ERROR: tmux not found. Install with: brew install tmux` |
| claude CLI not found | Orchestrator exits with: `ERROR: claude CLI not found. Install from Anthropic` |
| Project name collision in config | Schema validation rejects config: "Duplicate project name: {name}" |
| VPS credentials not accessible (SSH key missing) | Agent logs SSH key error; skips verification step; continues fix/push cycle |

---

## 15. Constraints (From Project Vision)

The following constraints were specified by the project owner and are non-negotiable for v1:

| Constraint | Detail |
|---|---|
| **No UI** | Pure script-based. No web server, no dashboard, no TUI framework. |
| **tmux required** | Terminal multiplexing is the only supported multi-project interface. |
| **Claude CLI only** | `claude --dangerously-skip-permissions` is the only agent mechanism. No API calls. |
| **Git-based only** | All source management is via Git. No SVN, Mercurial, or direct file sync. |
| **SSH key auth only** | No password prompts anywhere in the system. |
| **VPS-only deployment** | No cloud provider SDKs. SSH to VPS is the deployment interface. |
| **Python orchestrator preferred** | Python 3.9+ preferred for orchestrator; Bash acceptable for simple glue. |
| **YAML config** | `projects.yaml` only. No TOML, JSON, INI, or env-only configs. |

---

## 16. Open Questions

*All constraints specified by project owner have been captured. The following remain open for architect review:*

| # | Question | Impact | Owner |
|---|---|---|---|
| OQ-1 | Should `CLAUDE.md` be committed to the Git repo or kept as an ephemeral file regenerated on each run? If committed, it becomes part of the project's history and may conflict with team members. | FR-4.4 | Atlas to decide |
| OQ-2 | How should the system handle projects that deploy via CD pipeline (e.g., GitHub Actions auto-deploys on push) rather than requiring SSH verification? The `vps` block would be irrelevant for such projects. | FR-8 schema | Atlas to decide |
| OQ-3 | For the watchdog, should it use `libtmux` (Python tmux binding) or raw `subprocess tmux` calls? libtmux adds a dependency but is more robust. | tmux_manager design | Atlas to decide |
| OQ-4 | Should `log.md` be committed per-event (every fix) or batched (e.g., every 5 minutes)? Per-event creates many small commits; batching risks data loss on crash. | FR-10 | Atlas to decide |
| OQ-5 | For Python projects: `structlog` vs `loguru` as the injected standard? `loguru` has simpler API but `structlog` is more configurable. | logging_templates design | Atlas to decide |
| OQ-6 | Is there a maximum number of projects supported in v1? tmux pane limits and Claude session limits are practical constraints. | Scalability | Atlas/Devin to assess |

---

## 17. Research & Sources

| Claim | Source |
|---|---|
| Datadog Watchdog provides ML anomaly detection with remediation suggestions | https://www.datadoghq.com/blog/datadog-watchdog/ |
| Shoreline.io uses resource-oriented scripting (Op DSL) for incident response | https://shoreline.io/ |
| Ansible AWX enables playbook-based remediation for known error patterns | https://github.com/ansible/awx |
| GitHub Copilot Autofix provides PR-based auto-fix for code scanning alerts | https://github.blog/2023-11-08-github-copilot-autofix/ |
| Elastic Common Schema (ECS) defines the canonical JSON log field set used as AutoFix's log schema | https://www.elastic.co/guide/en/ecs/current/ |
| OpenTelemetry defines cross-language structured logging standards referenced in canonical schema design | https://opentelemetry.io/ |
| libtmux provides a Python API for programmatic tmux session/pane management | https://github.com/tmux-python/libtmux |
| pydantic v2 is the recommended Python config validation library for new projects | https://github.com/pydantic/pydantic |
| structlog provides structured JSON logging for Python with context binding | https://github.com/hynek/structlog |
| pino is the recommended Node.js structured logging library (JSONL output by default) | https://github.com/pinojs/pino |
| fabric wraps paramiko for high-level Python SSH deployment verification | https://github.com/fabric/fabric |

---

*PRD complete. Ready for architectural review by Atlas.*  
*Companion documents: `stories.md` (full acceptance criteria), `roadmap.md` (phased milestones)*
