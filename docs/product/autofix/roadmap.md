# Roadmap — AutoFix

**Version:** 1.0  
**Status:** Draft  
**Linked PRD:** `docs/product/autofix/PRD.md`

---

## Overview

AutoFix ships in three phases. Phase 1 delivers a working end-to-end system for a single project (proof-of-concept validation). Phase 2 hardens it for multi-project production use. Phase 3 adds reliability features and extensibility.

---

## Phase 1 — Core Loop (MVP) 

**Theme:** One project, fully working, end-to-end.  
**Goal:** Prove the core loop: config → clone → tmux pane → Claude agent → log monitoring → fix → push → verify.  
**Definition of Done:** A single Python project is onboarded, logging is standardized, one error is auto-fixed, committed, pushed, and verified via SSH — all triggered by one command.

| Story | Title | Priority |
|---|---|---|
| US-02 | Config-Driven Project Definition | P0 |
| US-12 | Config Validation with Actionable Errors | P1 |
| US-03 | Automatic Repo Clone/Pull | P0 |
| US-01 | Single-Command Startup | P0 |
| US-04 | Per-Project tmux Pane | P0 |
| US-13 | CLAUDE.md Per-Project Instruction File | P1 |
| US-05 | Logging Standardization Enforcement | P0 |
| US-17 | log.md Created at Logging Standardization | P1 |
| US-06 | Continuous Log Monitoring | P0 |
| US-07 | Auto-Fix: Detect → Fix → Commit → Push | P0 |
| US-08 | VPS Deployment Verification via SSH | P0 |
| US-09 | Continuous Loop After Fix | P0 |

**Deliverables:**
- `autofix.py` — working orchestrator
- `projects.yaml` — validated schema + example
- `config/schema.py` — Pydantic models
- `tmux_manager.py` — pane lifecycle
- `repo_manager.py` — clone/pull
- `claude_launcher.py` — CLAUDE.md generation
- `CLAUDE.md.j2` — agent instruction template (Python project variant)
- `logging_templates/python.py` — structlog injection config
- End-to-end test: one Python project auto-fixed

---

## Phase 2 — Multi-Project Production Hardening

**Theme:** Multiple projects, reliability, auditability.  
**Goal:** Run 5+ projects in parallel without failure, with full audit trail and auto-recovery.  
**Definition of Done:** 5 mixed-language projects monitored in parallel; pane crash triggers auto-respawn; log.md maintained; all configs validated; SSH key auth works throughout.

| Story | Title | Priority |
|---|---|---|
| US-10 | Automated log.md Maintenance | P1 |
| US-11 | Automatic Pane Respawn on Crash | P1 |
| US-14 | Per-Project Branch and VPS Configuration | P1 |
| US-15 | SSH Key Auth Throughout | P1 |

**Additional work (not story-linked):**
- Node.js logging template (`logging_templates/nodejs.js`)
- Ruby logging template (`logging_templates/ruby.rb`)
- Go logging template (`logging_templates/go.go`)
- Language auto-detection logic (`language_detector.py`)
- Watchdog loop implementation with crash-loop detection
- Orchestrator-level `autofix.log` structured output
- Webhook notification client (US-09 prerequisite)
- Integration tests: multi-project startup, pane respawn

---

## Phase 3 — Extensibility & Operator Experience

**Theme:** Reliability controls, escalation paths, and safe operating modes.  
**Goal:** Operators trust the system enough to leave it running on production services overnight.  
**Definition of Done:** Blocked patterns prevent sensitive fixes; dry-run mode verified; rate limiting confirmed; full test coverage on orchestrator.

| Story | Title | Priority |
|---|---|---|
| US-16 | Blocked Error Patterns (Human-Review-Only) | P2 |
| US-18 | Dry-Run Mode | P2 |

**Additional work:**
- Auto-rollback on failed deployment verification (v2 feature, scoped here)
- `schema_version` upgrade path (migration warnings)
- Comprehensive unit test suite for orchestrator
- Documentation: `README.md`, `CONTRIBUTING.md`, example `projects.yaml`
- Performance test: 10 projects, 60s startup validation

---

## Future Roadmap (Post-v1, Not Scoped)

| Idea | Rationale |
|---|---|
| **Auto-rollback** | If verification fails, revert the pushed commit and redeploy | 
| **Slack/Discord rich notifications** | Richer fix summaries with diffs and links |
| **GitHub Actions CD awareness** | Skip SSH verify if project uses CI/CD pipeline |
| **Multi-VPS / load balanced verification** | Verify across multiple nodes |
| **Dashboard (read-only tmux pane)** | Aggregate status across all projects in one pane |
| **Error pattern library** | Pre-built fix playbooks for common errors (DB connection, missing env vars) |
| **Plugin system for logging frameworks** | Community-contributed language templates |
| **Git tag management** | Auto-tag fix commits with semantic version increments |

---

## Key Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Claude agent exits unexpectedly due to context length | Medium | High | Watchdog respawn; CLAUDE.md keeps instructions concise |
| Push conflicts on shared repos (team + autofix) | Medium | Medium | pull --rebase strategy; blocked_patterns for merge-sensitive files |
| VPS SSH key rotation breaks verification | Low | Medium | Clear error messages; operator-visible pane output |
| False-positive fixes break working code | Low | High | Test-before-commit gate (FR-7.4); max_fixes_per_hour rate limit |
| Claude API / CLI behavioral changes | Medium | High | Pin claude CLI version; test on upgrade |
| tmux version incompatibilities across macOS/Linux | Low | Medium | Specify minimum tmux version (≥3.0); test on both platforms |
