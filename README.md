# AutoFix

> **Autonomous multi-project log monitoring and auto-fix system powered by Claude Code CLI.**

AutoFix is a single-command Python orchestrator that watches your production services around the clock. It reads a `projects.yaml` config, clones or pulls each listed Git repository, and opens **one tmux pane per project** — each running an autonomous [Claude Code CLI](https://github.com/anthropics/claude-code) agent (`claude --dangerously-skip-permissions`). The agents continuously tail live Docker logs from your VPS via SSH, detect ERROR/CRITICAL events, apply code fixes, run tests, commit, push, redeploy, and loop — all without human intervention.

A built-in **watchdog thread** monitors every tmux pane from the orchestrator side. If a pane dies (Claude crashes, SSH drops, signal received), the watchdog respawns it automatically within two polling intervals. Crash-loop protection prevents infinite restart storms: if a project crashes three or more times within ten minutes the watchdog backs off and logs a clear alert.

---

## Table of Contents

1. [What is AutoFix?](#1-what-is-autofix)
2. [How it works](#2-how-it-works)
3. [Requirements](#3-requirements)
4. [Deploy AutoFix on a Dedicated VPS](#4-deploy-autofix-on-a-dedicated-vps)
5. [Local Installation](#5-local-installation)
6. [Configuration](#6-configuration)
7. [Running](#7-running)
8. [First-time project setup](#8-first-time-project-setup)
9. [Logging templates](#9-logging-templates)
10. [Watchdog](#10-watchdog)
11. [Safety guardrails](#11-safety-guardrails)
12. [Audit Trail](#12-audit-trail)
13. [Project structure](#13-project-structure)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. What is AutoFix?

AutoFix is a **developer-workstation tool** that turns your local machine into a 24/7 monitoring station for multiple remote services. After a one-time `python autofix.py` invocation, AutoFix opens a tmux session with one window per project and launches a Claude Code agent in each window. Each agent is given a rich `CLAUDE.md` instruction file tailored to the project's language, repository layout, VPS credentials, and monitoring thresholds. The agent then enters a continuous loop: stream live Docker container logs → detect errors → diagnose the root cause → write a fix → run the project's test suite → commit with an `[autofix]` tag → push → SSH into the VPS and verify the deployment is healthy → repeat.

AutoFix is intentionally **infrastructure-free** — it requires no cloud accounts, no databases, no background services, and no root access. The only runtime dependencies are Python 3.9+, tmux, git, and the Claude CLI. All state is stored in plain files (`CLAUDE.md`, `log.md`, `logs/app.log`) inside each project directory. Every automated fix is fully traceable: the commit message, the `log.md` audit trail, and the orchestrator JSON log (`logs/autofix.log`) all record exactly what was changed and why.

---

## 2. How it works

1. **Start** — `python autofix.py` reads `projects.yaml`, validates the config, and checks prerequisites (tmux, git, claude CLI).
2. **Clone / pull** — For each project, AutoFix runs `git clone` (first run) or `git pull` (subsequent runs) to ensure the local working copy is up to date.
3. **Write `CLAUDE.md`** — AutoFix renders a project-specific instruction file using Jinja2 and writes it to `<local_path>/CLAUDE.md`. The file tells the Claude agent everything it needs: language, VPS credentials, log stream command, monitoring thresholds, blocked patterns, and full step-by-step instructions.
4. **Open tmux pane** — A dedicated tmux window named after the project is created inside the `autofix` session. The Claude agent is launched inside it with `claude --dangerously-skip-permissions`.
5. **Agent: logging setup** — On first run (no `log.md` / `.autofix_init` marker), the agent injects the project's structured JSON logging framework (structlog / Winston / Semantic Logger / Zap), creates `log.md`, commits, pushes, and redeploys.
6. **Monitor `docker logs -f` via SSH** — The agent opens an SSH connection to the VPS and streams container logs in real time using the configured `log_stream_command` (default: `docker logs -f <container_name>`).
7. **Detect ERROR / CRITICAL** — The agent parses each log line for `ERROR` or `CRITICAL` level entries, subject to the `blocked_patterns` and `error_debounce_minutes` safeguards.
8. **Fix** — The agent edits source files to address the root cause. It respects `blocked_patterns` (never touches migrations, CVE disclosures, etc.) and the `max_fixes_per_hour` rate limit.
9. **Test** — The agent runs the project's test suite (`pytest`, `npm test`, `go test ./...`, etc.) before committing. No fix is committed if tests fail.
10. **Commit → push** — A commit tagged `[autofix]` is created with `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` from `global_settings`, then pushed to `push_branch`.
11. **SSH verify** — The agent SSHes into the VPS, runs `verify_command`, and checks that the output contains `verify_output_contains`. If verification fails the fix is logged as failed.
12. **Loop** — The agent returns to step 6 and keeps monitoring.

---

## 3. Requirements

| Requirement | Version |
|---|---|
| Python | 3.9 or later |
| tmux | 3.0 or later |
| git | any recent version |
| Claude CLI (`claude`) | latest — install from [claude.ai/code](https://claude.ai/code) |
| SSH access to VPS | key-based auth only (no password prompts) |
| Docker (on VPS) | any version that supports `docker logs -f` |

Python package dependencies (installed via `pip`):

```
pyyaml
pydantic>=2.0
jinja2
libtmux>=0.28
```

---

## 4. Deploy AutoFix on a Dedicated VPS

This section is for the most common production scenario: you have **one or more VPS machines running your Docker projects**, and you want to spin up a **separate "monitoring VPS"** that runs AutoFix 24/7, SSHes into each project VPS, and monitors everything from a single place.

```
┌─────────────────────────────────────────────────────────┐
│              Your laptop / any machine                  │
│  ssh ubuntu@<monitoring-vps>                            │
│  tmux attach -t autofix                                 │
└────────────────────┬────────────────────────────────────┘
                     │  SSH
                     ▼
┌─────────────────────────────────────────────────────────┐
│          Monitoring VPS  (AutoFix lives here)           │
│                                                         │
│  tmux session "autofix"                                 │
│  ├─ window: project-api     → claude agent              │
│  ├─ window: project-worker  → claude agent              │
│  └─ window: project-site    → claude agent              │
│                                                         │
│  Each agent SSHes out to the project VPS(es) ──────────►│
└─────────────────────────────────────────────────────────┘
                     │  SSH (docker logs -f)
         ┌───────────┴───────────┐
         ▼                       ▼
┌──────────────────┐   ┌──────────────────┐
│  Project VPS 1   │   │  Project VPS 2   │
│  Docker containers│   │  Docker containers│
└──────────────────┘   └──────────────────┘
```

### Step 1 — Provision the monitoring VPS

Any small VPS works (1 vCPU, 1 GB RAM is enough for 5 projects). Recommended OS: **Ubuntu 22.04 LTS**.

```bash
# SSH into your new monitoring VPS
ssh ubuntu@<monitoring-vps-ip>
```

### Step 2 — Install system dependencies

```bash
sudo apt update && sudo apt upgrade -y

# tmux (required — must be >= 3.0)
sudo apt install -y tmux git curl wget unzip build-essential

# Python 3.11 (Ubuntu 22.04 ships 3.10; upgrade for best compatibility)
sudo apt install -y python3.11 python3.11-venv python3-pip
python3.11 --version   # confirm

# Make python3 / pip point to 3.11
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
```

Verify tmux version:

```bash
tmux -V   # must show 3.0 or later
```

### Step 3 — Install Node.js and the Claude CLI

The Claude Code CLI is distributed as an npm package. Install Node.js first:

```bash
# Install Node.js LTS via NodeSource
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # v20.x or later

# Install Claude Code CLI globally
sudo npm install -g @anthropic-ai/claude-code
claude --version   # confirm
```

### Step 4 — Authenticate Claude

Claude CLI requires a one-time login. On the monitoring VPS run:

```bash
claude login
```

Follow the browser link printed in the terminal. If the VPS has no browser, copy the URL to your laptop, authenticate, and paste the resulting token back. Once authenticated the credential is stored in `~/.config/claude/` and persists across reboots.

> **Tip:** You can also set `ANTHROPIC_API_KEY` as an environment variable in `/etc/environment` or `~/.bashrc` if you prefer API key auth over device login.

### Step 5 — Set up SSH keys for your project VPSes

AutoFix SSHes from the monitoring VPS to each project VPS. Use **key-based auth** — no passwords.

```bash
# Generate a dedicated key for AutoFix (on the monitoring VPS)
ssh-keygen -t ed25519 -C "autofix-agent" -f ~/.ssh/autofix_id_ed25519 -N ""

# Copy the public key to EACH project VPS
# Replace <user> and <project-vps-ip> for each VPS
ssh-copy-id -i ~/.ssh/autofix_id_ed25519.pub <user>@<project-vps-1-ip>
ssh-copy-id -i ~/.ssh/autofix_id_ed25519.pub <user>@<project-vps-2-ip>
# ... repeat for every project VPS

# Test the connection
ssh -i ~/.ssh/autofix_id_ed25519 <user>@<project-vps-1-ip> "docker ps"
```

You should see a container list with no password prompt. If it fails, check [SSH troubleshooting](#ssh-key-rejected--permission-denied-publickey).

### Step 6 — Set up SSH keys for GitHub / GitLab

AutoFix also needs to `git clone` and `git push` to your project repositories. Add a **deploy key** (or use the same `autofix_id_ed25519` key if you prefer a single key):

```bash
# Print the public key
cat ~/.ssh/autofix_id_ed25519.pub
```

Then on GitHub: **Repository → Settings → Deploy Keys → Add deploy key**. Tick **"Allow write access"** so the agent can push fixes.

For multiple repos you can add the same key to each repo, or use a GitHub personal access token (PAT) stored in `~/.netrc`:

```bash
# ~/.netrc  (chmod 600)
machine github.com
  login <your-github-username>
  password <your-github-pat>
```

### Step 7 — Clone AutoFix onto the monitoring VPS

```bash
# Clone AutoFix
git clone https://github.com/ThirunagariHarish/AutoFix.git ~/AutoFix
cd ~/AutoFix

# Create a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Verify
python autofix.py --version
```

### Step 8 — Configure your projects

```bash
cp projects.yaml.example projects.yaml
nano projects.yaml   # or vim / your editor of choice
```

Fill in one entry per project. Here is a minimal real-world example for two projects on two different VPSes:

```yaml
schema_version: "1.0"

global:
  tmux_session_name: "autofix"
  watchdog_interval_seconds: 60
  claude_command: "claude --dangerously-skip-permissions"
  git_author_name: "AutoFix Agent"
  git_author_email: "autofix@yourdomain.com"
  log_dir: "/home/ubuntu/AutoFix/logs"

projects:
  - name: "api-service"
    repo_url: "git@github.com:yourorg/api-service.git"
    local_path: "/home/ubuntu/autofix-workspace/api-service"
    branch: "main"
    language: "python"
    log_path: "logs/app.log"
    vps:
      enabled: true
      host: "203.0.113.10"                     # Project VPS 1 IP
      user: "ubuntu"
      ssh_key_path: "~/.ssh/autofix_id_ed25519"
      docker_container_name: "api-service"
      docker_compose_path: "/opt/api-service"
      log_stream_command: "docker logs -f api-service"
      verify_command: "docker ps --filter name=api-service --format '{{.Status}}'"
      verify_output_contains: "Up"
    monitoring:
      error_debounce_minutes: 5
      max_fixes_per_hour: 3
      blocked_patterns:
        - "CVE-"
        - "database migration"
        - "credentials"

  - name: "worker-service"
    repo_url: "git@github.com:yourorg/worker-service.git"
    local_path: "/home/ubuntu/autofix-workspace/worker-service"
    branch: "main"
    language: "nodejs"
    log_path: "logs/app.log"
    vps:
      enabled: true
      host: "203.0.113.20"                     # Project VPS 2 IP
      user: "deploy"
      ssh_key_path: "~/.ssh/autofix_id_ed25519"
      docker_container_name: "worker"
      docker_compose_path: "/srv/worker"
      log_stream_command: "docker logs -f worker"
      verify_command: "docker ps --filter name=worker --format '{{.Status}}'"
      verify_output_contains: "Up"
    monitoring:
      error_debounce_minutes: 10
      max_fixes_per_hour: 2
```

> **`projects.yaml` is git-ignored** — it contains SSH key paths and VPS IPs. Never commit it.

### Step 9 — Dry run (validate everything)

```bash
cd ~/AutoFix
source .venv/bin/activate
python autofix.py --dry-run
```

A successful dry run prints each project's resolved config, confirms all prerequisites pass, and exits without touching tmux or git. Fix any validation errors before proceeding.

### Step 10 — Start AutoFix

```bash
# Start monitoring (opens tmux session and attaches)
python autofix.py

# Or start headless (no attach) — useful if launching via SSH from your laptop
python autofix.py --no-attach
```

Once running you will see one tmux window per project. Each window shows the Claude agent working in real time.

### Step 11 — Reconnect from your laptop anytime

AutoFix runs entirely inside a persistent tmux session. You can disconnect and reconnect freely:

```bash
# From your laptop — SSH into the monitoring VPS
ssh ubuntu@<monitoring-vps-ip>

# Re-attach to the AutoFix session
tmux attach -t autofix

# Switch between project windows
# Ctrl+B, then window number (0, 1, 2…) or project name
tmux select-window -t autofix:api-service
tmux select-window -t autofix:worker-service

# Detach without stopping AutoFix
# Ctrl+B, then D
```

### Step 12 — Keep AutoFix running after SSH disconnect / reboot (systemd)

To ensure AutoFix survives SSH disconnections and VPS reboots, install it as a **systemd service**:

```bash
# Create the service file
sudo tee /etc/systemd/system/autofix.service > /dev/null << 'EOF'
[Unit]
Description=AutoFix Autonomous Monitoring Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/AutoFix
Environment=PATH=/home/ubuntu/AutoFix/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStartPre=/bin/bash -c 'tmux has-session -t autofix 2>/dev/null && tmux kill-session -t autofix; true'
ExecStart=/home/ubuntu/AutoFix/.venv/bin/python autofix.py --no-attach
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable autofix
sudo systemctl start autofix

# Check status
sudo systemctl status autofix

# Follow live orchestrator logs
sudo journalctl -u autofix -f
```

> **Note:** The `--no-attach` flag is mandatory when running under systemd (no TTY to attach to). The tmux session is still created and accessible via `tmux attach -t autofix` from any SSH session.

### Step 13 — View orchestrator logs

```bash
# JSON orchestrator log (all events)
tail -f ~/AutoFix/logs/autofix.log | python3 -m json.tool

# Or pretty-print with jq
tail -f ~/AutoFix/logs/autofix.log | jq .

# systemd journal (when running as a service)
sudo journalctl -u autofix -n 100 --no-pager
```

### Quick-reference cheat sheet

| Task | Command |
|---|---|
| Start monitoring | `python autofix.py` |
| Start headless | `python autofix.py --no-attach` |
| Dry run | `python autofix.py --dry-run` |
| Attach to session | `tmux attach -t autofix` |
| Switch to a project | `tmux select-window -t autofix:<name>` |
| Detach (keep running) | `Ctrl+B D` |
| Stop AutoFix | `Ctrl+C` in the session, or `sudo systemctl stop autofix` |
| Restart after config change | `sudo systemctl restart autofix` |
| Tail orchestrator log | `tail -f ~/AutoFix/logs/autofix.log \| jq .` |
| Check service status | `sudo systemctl status autofix` |

---

## 5. Local Installation

```bash
# 1. Clone AutoFix
git clone https://github.com/ThirunagariHarish/AutoFix.git
cd AutoFix

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Copy and edit the example config
cp projects.yaml.example projects.yaml

# 4. Edit projects.yaml with your repos and VPS details
#    (see Configuration section below)
$EDITOR projects.yaml
```

Verify the setup with a dry run:

```bash
python autofix.py --dry-run
```

---

## 6. Configuration

All configuration lives in `projects.yaml` (never committed — add it to `.gitignore`).

### Global settings

```yaml
schema_version: "1.0"

global:
  tmux_session_name: "autofix"          # Name of the tmux session
  watchdog_interval_seconds: 60         # How often the watchdog polls pane health
  claude_command: "claude --dangerously-skip-permissions"
  git_author_name: "AutoFix Agent"      # Git commit author name
  git_author_email: "autofix@local"     # Git commit author email
  log_dir: "./logs"                     # Orchestrator log directory
```

### Project fields

```yaml
projects:
  - name: "my-python-api"              # Unique alphanumeric/dash/underscore ID
    repo_url: "git@github.com:org/my-python-api.git"
    local_path: "/home/user/projects/my-python-api"  # Absolute path
    branch: "main"
    language: "python"                 # python | nodejs | ruby | go | auto
    log_path: "logs/app.log"           # Relative to local_path
```

### VPS settings

```yaml
    vps:
      enabled: true
      host: "192.168.1.100"            # IP or hostname
      user: "deploy"                   # SSH user
      ssh_key_path: "~/.ssh/id_rsa"   # Private key for SSH and git

      # docker_container_name — the Docker container running your app on the VPS.
      # Used as the default argument to "docker logs -f" when log_stream_command
      # is not set explicitly.
      docker_container_name: "my-python-api-app"

      # docker_compose_path — absolute path on the VPS to the directory containing
      # docker-compose.yml. The agent CDs here and runs "docker-compose up -d"
      # after pushing a fix.
      docker_compose_path: "/opt/my-python-api"

      # log_stream_command — the exact command run via SSH to stream live logs.
      # Defaults to "docker logs -f <docker_container_name>" when not set.
      # Override for non-Docker setups, e.g. "journalctl -u my-service -f -o json"
      log_stream_command: "docker logs -f my-python-api-app"

      # verify_command — run via SSH after each pushed fix to confirm health.
      verify_command: "docker ps --filter name=my-python-api-app --format '{{.Status}}'"

      # verify_output_contains — substring that must appear in verify_command output.
      verify_output_contains: "Up"

      verify_timeout_seconds: 30
```

### Monitoring settings

```yaml
    monitoring:
      # Minimum minutes between triggering two fixes for the same root error.
      error_debounce_minutes: 5

      # Hard cap on automated fixes per hour (1–20).
      # The agent tracks this internally and pauses when the limit is reached.
      max_fixes_per_hour: 3

      # blocked_patterns — substrings that, if found in an error message,
      # prevent AutoFix from applying any automated fix. Use this to protect
      # sensitive code paths that require human review.
      blocked_patterns:
        - "CVE-"              # Security advisories
        - "SQL injection"     # Security errors
        - "database migration" # Schema changes need manual review
        - "credentials"       # Never auto-fix credential-related errors
```

### Notification settings (optional)

```yaml
    notifications:
      webhook_url: "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
      # Events that trigger a POST to webhook_url.
      # Valid values: fix_applied, fix_failed, verification_failed,
      #               crash_loop_detected, pane_respawned
      on_events:
        - "fix_applied"
        - "fix_failed"
        - "verification_failed"
        - "crash_loop_detected"
        - "pane_respawned"
```

Webhook payload format:

```json
{
  "project": "my-python-api",
  "event": "fix_applied",
  "detail": "Fixed NullPointerError in auth handler",
  "timestamp": "2025-01-15T09:23:01+00:00",
  "source": "autofix"
}
```

### Git settings (optional)

```yaml
    git:
      push_branch: "main"        # Branch to push fixes to (defaults to branch)
      pull_before_fix: true      # Pull latest before attempting a fix
      commit_sign: false         # GPG-sign commits
```

---

## 7. Running

```bash
# Start monitoring all projects (attaches to tmux session)
python autofix.py

# Dry run — validate config and show plan; no git/tmux operations
python autofix.py --dry-run

# Custom config file location
python autofix.py --config /path/to/projects.yaml

# Start without attaching to tmux (headless / server mode)
# Watchdog runs in the background; press Ctrl+C to stop cleanly
python autofix.py --no-attach

# Adjust orchestrator log verbosity
python autofix.py --log-level DEBUG
```

To re-attach to a running session after detaching:

```bash
tmux attach -t autofix
```

To view a specific project's agent:

```bash
tmux select-window -t autofix:<project-name>
```

---

## 8. First-time project setup

When AutoFix launches an agent for a project that has **no `log.md` file** and **no `.autofix_init` marker** in the repository root, the agent enters **initialisation mode**:

1. **Detects** whether the project already uses structured JSON logging (structlog, Winston, Semantic Logger, or Zap depending on the language).
2. **Injects** the appropriate logging framework if absent, using the snippet from `logging_templates/`.
3. **Creates** `log.md` in the project root to serve as an ongoing audit trail.
4. **Commits** both changes with message `[autofix] Init: inject structured logging + create log.md`.
5. **Pushes** to the configured branch.
6. **Redeploys** on the VPS via `docker-compose up -d` (if `docker_compose_path` is set).
7. **Creates** the `.autofix_init` marker so subsequent restarts skip initialisation.

After initialisation the agent transitions directly into the monitoring loop.

---

## 9. Logging templates

AutoFix ships ready-to-use logging setup snippets for six frameworks. The agent reads the appropriate snippet from `logging_templates/` and injects it into the project when initialisation is needed.

| Language | Framework | Template file |
|---|---|---|
| Python | [structlog](https://www.structlog.org/) | `logging_templates/python_structlog.py` |
| Node.js | [Winston](https://github.com/winstonjs/winston) | `logging_templates/nodejs_winston.js` |
| Ruby | [Semantic Logger](https://logger.rocketjob.io/) | `logging_templates/ruby_semantic_logger.rb` |
| Go | [Zap](https://github.com/uber-go/zap) | `logging_templates/go_zap.go` |

All templates produce **structured JSON output** so errors are machine-parseable by the agent. You can customise any template to match your project's exact needs — the agent will use whatever is on disk at startup.

---

## 10. Watchdog

The watchdog is a background daemon thread (`threading.Thread(daemon=True)`) that starts automatically after all agents are launched. It polls every `watchdog_interval_seconds` (default: 60 s).

**Per-poll cycle:**

1. For each project, call `TmuxManager.is_pane_alive()`.
2. If the pane is alive → no action.
3. If the pane is dead:
   - Re-render `CLAUDE.md` to pick up any config changes.
   - Kill the dead tmux window.
   - Create a fresh window and re-launch the Claude agent.
   - Log `[watchdog] '<name>' respawned successfully.`

**Crash-loop detection:**

The watchdog tracks a rolling list of crash timestamps (last 10 minutes) per project. If a project crashes **five or more times within 10 minutes** the watchdog:

- Marks the project as `crash-looping`.
- Logs `[watchdog] ERROR: '<name>' crash-looping (>= 5 crashes in 10 min). NOT respawning.`
- Stops attempting restarts for that project.

This prevents infinite-restart loops when a project has a fundamental startup failure (bad environment variable, missing secret, broken dependency). To clear the crash-loop state, restart AutoFix (`Ctrl+C` then `python autofix.py`).

**Recovery time SLA:** Dead pane detected and respawned within `2 × watchdog_interval_seconds` (≤ 120 s at default settings).

**Shutdown:** Press `Ctrl+C`. AutoFix prints `[autofix] Shutting down watchdog...`, signals the watchdog thread to stop, waits up to 5 seconds for it to exit cleanly, and prints `[autofix] Goodbye.`

---

## 11. Safety guardrails

AutoFix is designed to be **conservative by default**. Multiple layers prevent runaway or harmful automation:

| Guardrail | Mechanism |
|---|---|
| **Blocked patterns** | `monitoring.blocked_patterns` — substrings that freeze the fix loop for human review |
| **Rate limit** | `monitoring.max_fixes_per_hour` — hard cap (1–20) on automated commits per project per hour |
| **Debounce** | `monitoring.error_debounce_minutes` — minimum gap between two fixes for the same error class |
| **Tests must pass** | Agent runs the project's test suite before every commit; failing tests abort the fix |
| **No secrets** | Agents are instructed never to commit `.env`, `secrets.*`, private keys, or credentials |
| **No migrations** | `database migration` is a default blocked pattern; schema changes require human sign-off |
| **No CVEs** | `CVE-` is a default blocked pattern; security advisories require human review |
| **Crash-loop stop** | Watchdog halts restarts after 5 crashes in 10 minutes |
| **Audit trail** | Every fix commits with `[autofix]` tag + appends entry to `log.md` |

---

## 12. Audit Trail

Every action AutoFix takes is traceable. All automated commits include `[autofix]` in the message:

```bash
# View all AutoFix commits across a project
git log --grep='\[autofix\]' --oneline

# View only fix commits
git log --grep='^fix(' --oneline

# View only logging-setup commits
git log --grep='\[autofix\]' --all --oneline
```

Each project also maintains a `log.md` file at its root, updated by the Claude agent after every fix cycle. It contains:
- The structured log format and field schema
- How to stream/tail logs (SSH command for Docker projects)
- Common error patterns and their typical causes
- A record of fixes applied with timestamps, error summaries, and commit SHAs

To inspect the audit log for a project:
```bash
cat ~/autofix-workspace/<project-name>/log.md
```

---

## 13. Project structure

```
AutoFix/
├── autofix.py                    # Orchestrator entry point (CLI)
├── projects.yaml.example         # Fully-annotated example config
├── requirements.txt              # Python dependencies
├── README.md                     # This file
│
├── autofix/                      # Core Python package
│   ├── __init__.py
│   ├── colors.py                 # ANSI terminal colour constants
│   ├── logger.py                 # JSON file logger (autofix.log)
│   ├── prereq_checker.py         # tmux / git / claude CLI checks
│   ├── config/
│   │   ├── __init__.py
│   │   ├── schema.py             # Pydantic v2 models (GlobalSettings, ProjectConfig, …)
│   │   └── loader.py             # YAML load + validate → AutoFixConfig
│   ├── repo_manager.py           # git clone / git pull
│   ├── tmux_manager.py           # libtmux session / window / pane lifecycle
│   ├── language_detector.py      # Manifest-based language detection (go.mod, etc.)
│   ├── claude_launcher.py        # Render CLAUDE.md.j2 + write to disk
│   ├── watchdog.py               # Background thread: dead-pane detection + respawn
│   └── notifier.py               # Webhook HTTP POST notifications
│
├── templates/
│   └── CLAUDE.md.j2              # Jinja2 template for per-project agent instructions
│
├── logging_templates/            # Ready-to-inject logging snippets
│   ├── python_structlog.py
│   ├── nodejs_winston.js
│   ├── ruby_semantic_logger.rb
│   └── go_zap.go
│
├── logs/                         # Orchestrator JSON log output (gitignored)
│   └── autofix.log
│
├── docs/
│   ├── architecture/
│   │   ├── architecture.md       # System architecture (Atlas)
│   │   └── tech-plan.md          # Phased implementation plan (Atlas)
│   └── product/autofix/
│       └── PRD.md                # Product requirements document (Nova)
│
└── tests/
    ├── conftest.py               # Shared pytest fixtures
    ├── test_config.py            # Config schema + loader tests
    ├── test_repo_manager.py      # Git operation tests
    ├── test_tmux_manager.py      # TmuxManager unit tests
    ├── test_language_detector.py # Language detection tests
    ├── test_claude_launcher.py   # CLAUDE.md rendering tests
    ├── test_watchdog.py          # Watchdog thread + crash-loop tests
    ├── test_notifier.py          # Notifier webhook tests
    └── fixtures/                 # YAML test fixtures
```

---

## 14. Troubleshooting

### `tmux: command not found`

Install tmux:

```bash
# macOS
brew install tmux

# Ubuntu / Debian
sudo apt install tmux
```

Verify the version is ≥ 3.0: `tmux -V`

---

### `SSH key rejected` / `Permission denied (publickey)`

1. Verify the key path in `projects.yaml` (`vps.ssh_key_path`) resolves to an existing file.
2. Ensure the public key is in `~/.ssh/authorized_keys` on the VPS.
3. Test manually: `ssh -i /path/to/key user@host "docker ps"`
4. Check key permissions: `chmod 600 ~/.ssh/id_rsa`

---

### `claude: command not found`

Install the Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
# or follow https://claude.ai/code for the latest instructions
```

Verify: `claude --version`

---

### `Project not appearing in tmux session`

1. Check the orchestrator log for errors: `cat logs/autofix.log`
2. Run with verbose logging: `python autofix.py --log-level DEBUG`
3. Verify the project's `local_path` is an absolute path (not relative).
4. Confirm git operations succeeded: `git -C <local_path> status`

---

### `Config validation failed`

Run `python autofix.py --dry-run` to see exactly which fields are invalid. Common causes:

- `local_path` is relative (must start with `/`).
- `ssh_key_path` file does not exist.
- `language` is not one of `python`, `nodejs`, `ruby`, `go`, `auto`.
- `max_fixes_per_hour` is outside the range 1–20.
- Duplicate project names.

---

### Watchdog not respawning a crashed pane

1. Check the watchdog polling interval: `global.watchdog_interval_seconds` (default 60 s).
2. Look for the crash-loop message in stdout: `[watchdog] ERROR: '<name>' crash-looping (>= 5 crashes)`.
3. A crash-loop triggers a **10-minute timed pause** (not a permanent ban) — AutoFix will automatically resume after the pause window. To clear immediately, restart AutoFix (`Ctrl+C` then `python autofix.py`).
4. Check that `libtmux >= 0.28` is installed (`pip show libtmux`) — older versions do not expose the `pane.dead` property used by the watchdog.

