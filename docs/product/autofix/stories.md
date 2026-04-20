# User Stories & Acceptance Criteria — AutoFix

**Version:** 1.0  
**Status:** Draft  
**Linked PRD:** `docs/product/autofix/PRD.md`

---

## P0 Stories — Must Ship in v1

---

### US-01 — Single-Command Startup

**Story:**  
As Dana, I want to run one command to start monitoring all my projects, so that I don't have to manually set up each project.

**Priority:** P0  
**Dependencies:** US-02, US-03, US-04

**Acceptance Criteria:**

```
Given a valid projects.yaml in the current directory
When the user runs `python autofix.py`
Then the orchestrator reads and validates projects.yaml
  AND clones or pulls each project repo
  AND creates a tmux session named per global.tmux_session_name
  AND creates one pane per project
  AND launches a Claude agent in each pane
  AND attaches the terminal to the tmux session
  AND completes all setup within 60 seconds for ≤10 projects
```

```
Given projects.yaml does not exist
When the user runs `python autofix.py`
Then the orchestrator prints: "ERROR: projects.yaml not found at ./projects.yaml"
  AND exits with code 1
  AND does NOT create any tmux session
```

```
Given tmux is not installed on the host machine
When the user runs `python autofix.py`
Then the orchestrator prints: "ERROR: tmux not found. Install with: brew install tmux (macOS) or apt install tmux (Ubuntu)"
  AND exits with code 1
```

```
Given claude CLI is not installed
When the user runs `python autofix.py`
Then the orchestrator prints: "ERROR: claude CLI not found."
  AND exits with code 1
```

---

### US-02 — Config-Driven Project Definition

**Story:**  
As Dana, I want to define all project configs in a single `projects.yaml` file, so that adding a new project is a one-line change.

**Priority:** P0  
**Dependencies:** None

**Acceptance Criteria:**

```
Given a projects.yaml with all required fields present and valid
When the orchestrator parses the config
Then all fields are read without error
  AND default values are applied for all optional fields not specified
  AND a Pydantic model is populated for each project
```

```
Given a projects.yaml with a missing required field (e.g., repo_url)
When the orchestrator validates the config
Then validation fails with an error message identifying: the project name AND the missing field
  AND exits with code 1
  AND no projects are started
```

```
Given a projects.yaml with two projects sharing the same `name` value
When the orchestrator validates the config
Then validation fails with: "Duplicate project name: {name}"
  AND exits with code 1
```

```
Given a projects.yaml with schema_version not present
When the orchestrator validates the config
Then validation fails with: "schema_version is required"
  AND exits with code 1
```

```
Given a projects.yaml with language set to an unsupported value (e.g., "cobol")
When the orchestrator validates the config
Then validation fails with: "Invalid language 'cobol'. Must be one of: python, nodejs, ruby, go, auto"
```

---

### US-03 — Automatic Repo Clone/Pull

**Story:**  
As Dana, I want each project to be cloned automatically if not already local, so that I don't need to manually clone repos.

**Priority:** P0  
**Dependencies:** US-02

**Acceptance Criteria:**

```
Given a project with local_path that does not exist on disk
When the orchestrator starts
Then it runs: git clone {repo_url} {local_path}
  AND the clone completes successfully
  AND the correct branch is checked out
```

```
Given a project with local_path that already exists and is a valid git repo
When the orchestrator starts
Then it runs: git pull origin {branch}
  AND the pull completes successfully
  AND no clone is attempted
```

```
Given a git clone fails (e.g., network error, auth failure)
When the orchestrator encounters the error
Then it logs: "WARN: Failed to clone {name}: {error_message}"
  AND continues processing all other projects
  AND marks this project's pane with the error state
  AND does NOT exit the orchestrator
```

```
Given a project's local_path exists but is not a git repo
When the orchestrator processes this project
Then it logs: "WARN: {local_path} is not a git repository"
  AND skips the pull
  AND proceeds to pane creation (agent will detect and handle)
```

---

### US-04 — Per-Project tmux Pane

**Story:**  
As Dana, I want each project to open in its own tmux pane, so that I can visually inspect any project's agent activity at a glance.

**Priority:** P0  
**Dependencies:** US-01, US-03

**Acceptance Criteria:**

```
Given N valid projects in projects.yaml
When the orchestrator starts
Then exactly N panes are created in the tmux session
  AND each pane is named after the project's `name` field
  AND each pane has cd'd to the project's local_path
  AND each pane is running the Claude agent
```

```
Given the tmux session "autofix" already exists from a previous run
When the orchestrator starts again
Then it detects the existing session
  AND does NOT create a duplicate session
  AND attaches to the existing session
```

```
Given a project pane is created
When a user switches to that pane in tmux
Then they can see the Claude agent's live output
  AND the current working directory is the project's local_path
```

---

### US-05 — Logging Standardization Enforcement

**Story:**  
As Dana, I want each Claude agent to check and enforce standardized logging, so that all projects emit logs in a consistent, parseable format.

**Priority:** P0  
**Dependencies:** US-04

**Acceptance Criteria:**

```
Given a Python project that does NOT use structlog or loguru
When the Claude agent starts (Phase 1)
Then it detects the absence of standard logging
  AND installs structlog (or configured equivalent) via pip/requirements.txt
  AND creates a logging_config.py with JSON formatter targeting the configured log_path
  AND updates the project's main entry point to use the new logger
  AND commits with: "chore(autofix): standardize logging framework [autofix]"
  AND pushes to the configured branch
  AND creates log.md documenting the logging structure
```

```
Given a Node.js project that does NOT use winston or pino
When the Claude agent starts (Phase 1)
Then it detects the absence of standard logging
  AND installs pino (or configured equivalent) via npm
  AND creates a logger.js config outputting JSON to the configured log_path
  AND updates the project's main entry point
  AND commits and pushes
  AND creates log.md
```

```
Given a project that ALREADY uses a standard logging framework
When the Claude agent starts (Phase 1)
Then it detects the existing framework
  AND skips installation
  AND creates/updates log.md documenting the existing setup
  AND writes .autofix_init marker file
  AND proceeds directly to Phase 2 monitoring
```

```
Given the logging standardization commit is pushed
When the VPS auto-deploys (e.g., via webhook or CD pipeline)
Then the project's logs at log_path begin emitting JSON structured logs
  AND all log lines contain: timestamp, level, logger, message
```

---

### US-06 — Continuous Log Monitoring

**Story:**  
As Dana, I want each agent to continuously monitor logs for errors, so that errors are caught immediately without me watching.

**Priority:** P0  
**Dependencies:** US-05

**Acceptance Criteria:**

```
Given the agent is in Phase 2 (monitoring loop)
When a new ERROR or CRITICAL line is appended to the log file
Then the agent detects it within 5 seconds
  AND extracts: timestamp, level, logger, message, stack trace (if present)
```

```
Given the same error appears twice within the debounce window (default: 5 minutes)
When the agent detects the second occurrence
Then it does NOT trigger a second fix attempt
  AND logs: "Duplicate error suppressed (debounce: {minutes}m)"
```

```
Given an INFO or WARNING log line appears
When the agent reads it
Then it does NOT trigger a fix attempt
  AND continues monitoring
```

```
Given the log file does not exist yet
When the agent starts Phase 2
Then it polls for the file every 30 seconds
  AND when the file appears, begins tailing it
  AND does NOT crash or exit
```

```
Given the log file is rotated (renamed and new file created)
When the agent detects the rotation
Then it re-opens the new log file from the beginning
  AND continues monitoring without interruption
```

---

### US-07 — Auto-Fix: Detect → Fix → Commit → Push

**Story:**  
As Dana, I want each agent to automatically apply a fix, commit it, and push it when an error is detected, so that my projects self-heal.

**Priority:** P0  
**Dependencies:** US-06

**Acceptance Criteria:**

```
Given an ERROR is detected with a readable stack trace
When the agent initiates a fix cycle
Then it reads the implicated source file(s) from the stack trace
  AND diagnoses the root cause
  AND modifies ONLY the files directly implicated in the error
  AND does NOT modify unrelated files
```

```
Given a fix has been applied
When tests are available (pytest / npm test / go test)
Then the agent runs the test suite
  AND if tests PASS: proceeds to commit
  AND if tests FAIL: runs git checkout -- . to revert all changes
    AND logs: "Fix reverted — test suite failed" to log.md
    AND continues monitoring
```

```
Given tests pass (or no test suite exists)
When the agent commits the fix
Then the commit message format is: "fix(<scope>): <brief description> [autofix]"
  AND git author is set to global.git_author_name and global.git_author_email
  AND the commit is pushed to push_branch
```

```
Given a push is rejected (remote has new commits)
When the agent encounters the rejection
Then it runs: git pull --rebase origin {push_branch}
  AND retries the push once
  AND if the second push also fails: logs the failure and skips this fix cycle
```

```
Given max_fixes_per_hour is set to 3
When the agent has already auto-fixed 3 times in the current hour
Then the agent logs: "Rate limit reached: max_fixes_per_hour=3"
  AND pauses fix attempts until the next hour
  AND continues monitoring (logging errors but not fixing)
```

---

### US-08 — VPS Deployment Verification via SSH

**Story:**  
As Dana, I want the agent to SSH into the VPS after a push to verify the deployment succeeded, so that I know the fix is actually live.

**Priority:** P0  
**Dependencies:** US-07

**Acceptance Criteria:**

```
Given a fix was successfully committed and pushed
When the agent initiates verification
Then it opens an SSH connection to vps.host as vps.user using vps.ssh_key_path
  AND executes verify_command on the remote host
  AND waits up to verify_timeout_seconds for a response
```

```
Given the verify_command exits with code 0
AND verify_output_contains is configured
AND the command output contains the configured substring
When the agent checks the result
Then it logs: "DEPLOY_VERIFIED: {project_name} — {verify_command} succeeded" to log.md
  AND appends commit SHA and timestamp to the log entry
```

```
Given the verify_command exits with non-zero code
When the agent checks the result
Then it logs: "DEPLOY_FAILED: {project_name} — {verify_command} returned exit code {code}" to log.md
  AND sends a webhook notification if configured
  AND does NOT attempt rollback (v1)
  AND returns to the monitoring loop
```

```
Given the SSH connection times out after verify_timeout_seconds
When the agent encounters the timeout
Then it logs: "VPS_TIMEOUT: SSH to {vps_host} timed out after {timeout}s"
  AND does NOT retry
  AND returns to the monitoring loop
```

```
Given vps.ssh_key_path does not exist on the local machine
When the agent attempts verification
Then it logs: "SSH_KEY_MISSING: {ssh_key_path} not found — skipping verification"
  AND returns to the monitoring loop without crashing
```

---

### US-09 — Continuous Loop After Fix

**Story:**  
As Dana, I want each agent to return to monitoring after a fix cycle, so that monitoring is continuous and uninterrupted.

**Priority:** P0  
**Dependencies:** US-07, US-08

**Acceptance Criteria:**

```
Given a fix cycle has completed (success, failure, or skip)
When the cycle ends
Then the agent immediately resumes tailing the log file
  AND monitors for new errors
  AND does NOT require restart or human intervention
```

```
Given 24 hours have passed with no errors
When the monitoring loop is running
Then the agent is still alive and tailing logs
  AND has not crashed or exited
  AND the tmux pane is still active
```

---

## P1 Stories — Required for Production Readiness

---

### US-10 — Automated log.md Maintenance

**Story:**  
As Dana, I want every agent action logged to a `log.md` in the project root, so that I can audit what changed and when.

**Priority:** P1  
**Dependencies:** US-05, US-07, US-08

**Acceptance Criteria:**

```
Given the agent performs any of: logging standardization, error detection, fix attempt, verification
When the action completes
Then a new row is appended to the log.md activity table
  AND includes: ISO 8601 timestamp, event type, description, commit SHA (if applicable)
  AND is committed and pushed to the repo
```

```
Given log.md does not exist
When the agent first runs Phase 1
Then it creates log.md with the header structure (logging framework documentation + empty activity table)
```

```
Given log.md exists with prior entries
When the agent appends a new entry
Then prior entries are NOT modified
  AND the new entry appears at the bottom of the table
```

---

### US-11 — Automatic Pane Respawn on Crash

**Story:**  
As Ivan, I want the system to restart a crashed agent pane automatically, so that a single project failure doesn't kill monitoring.

**Priority:** P1  
**Dependencies:** US-04

**Acceptance Criteria:**

```
Given a Claude agent pane has died (exited with any code)
When the watchdog fires (within watchdog_interval_seconds)
Then it detects the dead pane
  AND logs: "PANE_DEAD: {project_name} — respawning"
  AND creates a new pane with the same name
  AND runs git pull
  AND re-launches claude --dangerously-skip-permissions
  AND the new pane begins the Phase 1 check (with .autofix_init marker skipping logging setup)
```

```
Given a pane has been respawned 3 times in the last 10 minutes
When the watchdog detects it is dead again
Then it logs: "PANE_CRASH_LOOP: {project_name} — not respawning (crash loop detected)"
  AND does NOT respawn again until 30 minutes have elapsed
  AND sends a webhook notification if configured
```

---

### US-12 — Config Validation with Actionable Errors

**Story:**  
As Ivan, I want config validation to fail fast with a clear error message at startup, so that misconfigured projects don't silently fail.

**Priority:** P1  
**Dependencies:** US-02

**Acceptance Criteria:**

```
Given any required field is missing
When validation runs
Then the error message includes: field path, project name, and human-readable description of what's expected
  Example: "projects[1].vps.host: Required field missing. Expected: IP address or hostname string."
```

```
Given ssh_key_path points to a file that doesn't exist
When validation runs
Then the error message includes: "ssh_key_path '{path}' does not exist on this machine"
```

```
Given monitoring.max_fixes_per_hour is set to 0 or > 20
When validation runs
Then the error message includes: "max_fixes_per_hour must be between 1 and 20"
```

---

### US-13 — CLAUDE.md Per-Project Instruction File

**Story:**  
As Dana, I want each project's CLAUDE.md to contain precise instructions for the autonomous agent, so that agent behavior is deterministic and auditable.

**Priority:** P1  
**Dependencies:** US-02, US-04

**Acceptance Criteria:**

```
Given the orchestrator has read a valid project config
When it generates CLAUDE.md for that project
Then CLAUDE.md is written to {local_path}/CLAUDE.md
  AND contains all five required sections (Identity, Phase 1, Phase 2 loop, Escalation rules, Project values)
  AND all {placeholder} values are replaced with actual config values
  AND no placeholder tokens remain in the output file
```

```
Given CLAUDE.md is placed in the project root
When claude --dangerously-skip-permissions is launched in that directory
Then Claude reads CLAUDE.md automatically (Claude Code behavior)
  AND executes Phase 1 before Phase 2
```

```
Given CLAUDE.md contains vps.ssh_key_path as a reference
When the file is read
Then the key path is a filesystem reference (e.g., "~/.ssh/id_rsa")
  AND NOT the contents of the key itself
```

---

### US-14 — Per-Project Branch and VPS Configuration

**Story:**  
As Ivan, I want to configure per-project branch names and VPS SSH targets, so that staging and production projects can coexist in the same config.

**Priority:** P1  
**Dependencies:** US-02

**Acceptance Criteria:**

```
Given two projects in projects.yaml: one targeting branch "staging", one targeting "main"
When the orchestrator starts
Then the staging project's agent pushes fixes to "staging"
  AND the production project's agent pushes fixes to "main"
  AND no cross-project branch contamination occurs
```

```
Given two projects pointing to different VPS hosts
When each agent completes a fix and runs verification
Then each SSH connection goes to its respective configured host
  AND no project uses another project's VPS connection
```

---

### US-15 — SSH Key Auth Throughout

**Story:**  
As Dana, I want the system to handle SSH key authentication to both Git remotes and VPS, so that no passwords are needed in the loop.

**Priority:** P1  
**Dependencies:** US-03, US-08

**Acceptance Criteria:**

```
Given SSH keys are configured for both Git remote and VPS
When the orchestrator clones a repo and an agent verifies a deployment
Then no password prompt appears
  AND no interactive input is required
  AND operations complete without human intervention
```

```
Given an SSH key doesn't have the correct permissions (not 600)
When an SSH operation fails due to permissions
Then the error message includes: "SSH key permission error: {path} — run chmod 600 {path}"
```

---

### US-17 — log.md Created at Logging Standardization

**Story:**  
As Dana, I want the agent to create a `log.md` documenting the logging structure when it first standardizes logging in a project, so that I understand what was changed.

**Priority:** P1  
**Dependencies:** US-05

**Acceptance Criteria:**

```
Given logging standardization has just been completed
When the agent creates log.md
Then it includes: framework name, version, output path, format (JSON), log levels, key fields
  AND a "Before" and "After" section describing what changed
  AND the first row in the activity table: LOGGING_STANDARDIZED event
```

---

## P2 Stories — Nice-to-Have for v1, Required for v2

---

### US-16 — Blocked Error Patterns (Human-Review-Only)

**Story:**  
As Ivan, I want to be able to mark certain error patterns as "human-review-only" in the config, so that sensitive fixes are never auto-committed.

**Priority:** P2  
**Dependencies:** US-06, US-07

**Acceptance Criteria:**

```
Given an error log line contains a substring matching a blocked_pattern entry
When the agent detects this error
Then it logs: "BLOCKED: Error matches pattern '{pattern}' — human review required" to log.md
  AND does NOT attempt to fix the error
  AND sends a webhook notification if configured
  AND continues monitoring
```

```
Given blocked_patterns: ["CVE-", "SQL injection", "database migration"]
When an error containing "CVE-2024-1234: RCE vulnerability" is detected
Then it is blocked
  AND when an error containing "NullPointerException" (no match) is detected
  Then it proceeds through the normal fix cycle
```

---

### US-18 — Dry-Run Mode

**Story:**  
As Ivan, I want a dry-run mode that shows what would happen without making changes, so that I can safely test the system against existing projects.

**Priority:** P2  
**Dependencies:** US-01

**Acceptance Criteria:**

```
Given the user runs `python autofix.py --dry-run`
When the orchestrator starts
Then it validates config and prints the startup plan:
  - Which repos would be cloned/pulled
  - Which tmux panes would be created
  - What CLAUDE.md would be generated (prints content without writing)
  AND exits without creating any tmux sessions or modifying any files
  AND prints: "DRY RUN complete. No changes made."
```

---

## Dependency Map

```
US-01 ← US-02, US-03, US-04
US-03 ← US-02
US-04 ← US-01, US-03
US-05 ← US-04
US-06 ← US-05
US-07 ← US-06
US-08 ← US-07
US-09 ← US-07, US-08
US-10 ← US-05, US-07, US-08
US-11 ← US-04
US-12 ← US-02
US-13 ← US-02, US-04
US-14 ← US-02
US-15 ← US-03, US-08
US-16 ← US-06, US-07
US-17 ← US-05
US-18 ← US-01
```
