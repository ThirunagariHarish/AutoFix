# Changelog

All notable changes to AutoFix are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] — Initial Release

### Added
- Single-command launch (`python autofix.py`) with `--config`, `--dry-run`, `--no-attach`, `--version` flags
- Config-driven via `projects.yaml` — supports up to 10 projects
- Pydantic v2 schema validation with user-friendly error messages
- Auto `git clone` on first run, `git pull` on subsequent runs (SSH-key aware)
- One tmux pane per project via libtmux
- Autonomous Claude Code agent per pane (`claude --dangerously-skip-permissions`)
- CLAUDE.md auto-generated per project from Jinja2 template with all project-specific values
- Logging standardisation: auto-injects structlog (Python), winston (Node.js), pino (Node.js alt), loguru (Python alt), semantic_logger (Ruby), zap (Go) if not present
- `log.md` created per project documenting log format, SSH streaming commands, and error patterns
- `.autofix_init` sentinel prevents re-running logging setup on subsequent launches
- Docker log streaming via SSH (`docker logs -f <container>` on VPS)
- Continuous error monitoring: detects `error`/`critical`/`fatal` log levels + exception tracebacks
- Automated fix cycle: diagnose → fix → test → commit → push → SSH verify → loop
- Debounce: skips same error pattern seen within last N minutes
- Rate limit: max N fixes per hour (configurable per project)
- Blocked patterns: never auto-fixes security CVEs, SQL injection, database migrations
- Deployment verification via configurable SSH command + expected output string
- Watchdog thread: polls pane liveness every N seconds, respawns dead panes
- Crash-loop detection: suspends respawning after >5 crashes in 10 minutes (auto-resumes after 10 min)
- Git pull before each respawn to pick up latest code
- Notifier: fire-and-forget webhook (Slack/Discord/custom) for `fix_applied`, `fix_failed`, `verification_failed`, `crash_loop_detected`, `pane_respawned`
- Prerequisite checker: validates tmux ≥ 3.0, git, claude CLI present at startup (exit code 2 if missing)
- Structured JSON logging to `logs/autofix.log` (rotating, 50 MB, 7 backups)
- Dry-run mode: validates config and renders CLAUDE.md without touching git or tmux
- 173 unit tests across all modules
