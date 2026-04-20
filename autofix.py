#!/usr/bin/env python3
"""AutoFix — Autonomous multi-project log monitoring and auto-fix system.

Usage:
    python autofix.py [--config PATH] [--dry-run] [--no-attach] [--log-level LEVEL]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autofix.version import __version__
from autofix.logger import setup_logger
from autofix.config.schema import GlobalSettings
from autofix.prereq_checker import check_prerequisites
from autofix.config.loader import (
    load_config,
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)
from autofix.repo_manager import RepoManager
from autofix.tmux_manager import TmuxManager
from autofix.claude_launcher import ClaudeLauncher
from autofix.watchdog import Watchdog
from autofix.notifier import Notifier
from autofix.colors import GREEN, YELLOW, RED, CYAN, BOLD, RESET


def _print_success(msg: str) -> None:
    print(f"{GREEN}✓ {msg}{RESET}", flush=True)


def _print_warn(msg: str) -> None:
    print(f"{YELLOW}⚠ {msg}{RESET}", flush=True)


def _print_error(msg: str) -> None:
    print(f"{RED}✗ ERROR: {msg}{RESET}", file=sys.stderr, flush=True)


def _print_info(msg: str) -> None:
    print(f"{CYAN}→ {msg}{RESET}", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autofix",
        description="AutoFix — Autonomous multi-project log monitoring and auto-fix system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        default="./projects.yaml",
        metavar="PATH",
        help="Path to projects.yaml config file (default: ./projects.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and print plan; do not run git or tmux operations.",
    )
    parser.add_argument(
        "--no-attach",
        action="store_true",
        help="Start tmux session but do not attach to it.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level for the orchestrator (default: INFO)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"AutoFix %(prog)s {__version__}",
    )
    return parser


# ---------------------------------------------------------------------------
# Dry-run summary
# ---------------------------------------------------------------------------

def _dry_run_render_claude_mds(config) -> None:  # noqa: ANN001
    """Render CLAUDE.md for every project and confirm the template is valid.

    In dry-run mode we do NOT write to disk (local_path may not exist).
    We render in-memory and report the rendered size so the operator can
    confirm all project-specific values were substituted.
    """
    gs = config.global_settings
    launcher = ClaudeLauncher()

    print(f"\n{BOLD}{CYAN}  CLAUDE.md Rendering Preview{RESET}")
    print(f"{CYAN}  {'─'*50}{RESET}")
    all_ok = True
    for p in config.projects:
        try:
            content = launcher.generate_claude_md(p, gs)
            size = len(content)
            print(
                f"  {GREEN}✓{RESET} [{GREEN}{p.name}{RESET}] "
                f"CLAUDE.md rendered — {size:,} chars "
                f"(would write to {p.local_path}/CLAUDE.md)"
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"  {RED}✗{RESET} [{RED}{p.name}{RESET}] "
                f"CLAUDE.md render FAILED: {exc}",
                file=sys.stderr,
            )
            all_ok = False

    if all_ok:
        print(
            f"\n{GREEN}  ✓ All {len(config.projects)} project(s) rendered "
            f"CLAUDE.md successfully.{RESET}\n"
        )
    else:
        print(
            f"\n{RED}  ✗ One or more CLAUDE.md renders failed.{RESET}\n",
            file=sys.stderr,
        )


def _print_dry_run_summary(config) -> None:  # noqa: ANN001
    """Print a human-readable summary of a validated AutoFixConfig."""
    gs = config.global_settings
    print(f"\n{BOLD}{CYAN}{'='*60}")
    print("  AutoFix — Dry Run Summary")
    print(f"{'='*60}{RESET}")
    print(f"  schema_version : {config.schema_version}")
    print(f"  tmux_session   : {gs.tmux_session_name}")
    print(f"  watchdog       : every {gs.watchdog_interval_seconds}s")
    print(f"  claude_command : {gs.claude_command}")
    print(f"  git_author     : {gs.git_author_name} <{gs.git_author_email}>")
    print(f"  log_dir        : {gs.log_dir}")
    print(f"\n  Projects ({len(config.projects)}):")
    for p in config.projects:
        vps_status = "enabled" if p.vps.enabled else "disabled"
        print(f"\n    [{GREEN}{p.name}{RESET}]")
        print(f"      repo_url   : {p.repo_url}")
        print(f"      local_path : {p.local_path}")
        print(f"      branch     : {p.branch}")
        print(f"      language   : {p.language}")
        print(f"      log_path   : {p.log_path}")
        print(f"      vps        : {vps_status} ({p.vps.host})")
        print(f"      max_fixes  : {p.monitoring.max_fixes_per_hour}/hr")
    print(f"\n{CYAN}{'='*60}{RESET}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # 1. Initialize logger early so all subsequent modules can use it
    # We don't have log_dir yet; use default until config loads
    logger = setup_logger(args.log_level, "./logs")

    # 2. Prerequisite checks
    check_prerequisites()

    # 3. Load + validate config
    try:
        config = load_config(args.config)
    except ConfigFileNotFoundError as exc:
        _print_error(str(exc))
        sys.exit(1)
    except ConfigParseError as exc:
        _print_error(str(exc))
        sys.exit(1)
    except ConfigValidationError as exc:
        _print_error("Config validation failed:")
        for err in exc.errors:
            print(f"  {RED}• {err}{RESET}", file=sys.stderr)
        sys.exit(1)

    _print_success(f"Config loaded: {len(config.projects)} project(s) defined.")
    logger.info("Config loaded from %s (%d projects)", args.config, len(config.projects))

    # 4. Dry-run: print summary, render CLAUDE.md for each project, then exit
    if args.dry_run:
        _print_dry_run_summary(config)
        _dry_run_render_claude_mds(config)
        sys.exit(0)

    # 5. Initialize managers
    gs = config.global_settings
    repo_manager = RepoManager(gs.git_author_name, gs.git_author_email)
    tmux_manager = TmuxManager(
        session_name=gs.tmux_session_name,
        claude_command=gs.claude_command,
        git_author_name=gs.git_author_name,
        git_author_email=gs.git_author_email,
    )
    claude_launcher = ClaudeLauncher()

    # 6. Clone / pull each project
    failed_projects: list[str] = []
    healthy_projects = []

    for project in config.projects:
        _print_info(f"Processing project: {project.name}")

        result = repo_manager.clone_or_pull(project)
        if not result.success:
            _print_warn(
                f"Git {result.action} failed for '{project.name}': {result.error}"
            )
            failed_projects.append(project.name)
            logger.error(
                "Git %s failed for project '%s': %s",
                result.action, project.name, result.error,
            )
            continue

        _print_success(f"[{project.name}] Git {result.action} succeeded.")

        # B2: If clone_fresh redirected to a new path, update project to reflect it
        if result.new_local_path:
            project = project.model_copy(update={"local_path": result.new_local_path})
            _print_info(f"[{project.name}] Updated local_path to {result.new_local_path}")

        # 7. Write CLAUDE.md (stub in Phase 1)
        try:
            claude_md_path = claude_launcher.render_and_write(project, gs)
            _print_success(f"CLAUDE.md written to {claude_md_path}")
            logger.info("CLAUDE.md written to %s", claude_md_path)
        except Exception as exc:
            _print_warn(f"Failed to write CLAUDE.md for '{project.name}': {exc}")
            logger.warning("CLAUDE.md write failed for '%s': %s", project.name, exc)
            # Don't fail the project over CLAUDE.md — agent can still be launched

        healthy_projects.append(project)

    # 8. If all projects failed, exit
    if config.projects and not healthy_projects:
        _print_error("All projects failed git operations. Exiting.")
        logger.error("All projects failed; exiting with code 3")
        sys.exit(3)

    if failed_projects:
        _print_warn(
            f"Skipping {len(failed_projects)} failed project(s): "
            f"{', '.join(failed_projects)}"
        )

    # 9. Create tmux session
    session = tmux_manager.get_or_create_session()

    # 10. Launch agents for each healthy project
    for project in healthy_projects:
        window = tmux_manager.create_project_window(session, project)
        tmux_manager.launch_agent(window, project)
        _print_success(f"Agent launched for '{project.name}'.")
        logger.info("Agent launched for project '%s'", project.name)

    # 11. Instantiate Notifier and Watchdog (Phase 3)
    notifier = Notifier(healthy_projects)

    watchdog = Watchdog(
        tmux_manager=tmux_manager,
        claude_launcher=claude_launcher,
        repo_manager=repo_manager,
        projects=healthy_projects,
        global_settings=gs,
        notifier=notifier,
    )
    watchdog.start()
    _print_success(
        f"Watchdog started (interval: {gs.watchdog_interval_seconds}s)."
    )
    logger.info("Watchdog started with interval=%ds", gs.watchdog_interval_seconds)

    # 12. Attach or run headless
    session_name = gs.tmux_session_name
    if not args.no_attach:
        _print_info(f"Attaching to tmux session '{session_name}'…")
        try:
            tmux_manager.attach_session(session)
        except KeyboardInterrupt:
            pass
        finally:
            print("\n[autofix] Shutting down watchdog...", flush=True)
            watchdog.stop()
            watchdog.join(timeout=5)
            print("[autofix] Goodbye.", flush=True)
    else:
        print(
            f"\n{GREEN}{BOLD}✓ AutoFix is running.{RESET}\n"
            f"  tmux session : {BOLD}{session_name}{RESET}\n"
            f"  Attach with  : {CYAN}tmux attach -t {session_name}{RESET}\n"
        )
        logger.info(
            "AutoFix started with --no-attach. "
            "tmux session: %s. Attach: tmux attach -t %s",
            session_name, session_name,
        )
        try:
            watchdog.join()
        except KeyboardInterrupt:
            print("\n[autofix] Shutting down watchdog...", flush=True)
            watchdog.stop()
            watchdog.join(timeout=5)
            print("[autofix] Goodbye.", flush=True)


if __name__ == "__main__":
    main()
