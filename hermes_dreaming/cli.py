from __future__ import annotations

"""
CLI wiring for `hermes dreaming <subcommand>`.

Provides argparse setup (register_cli) and dispatch (handle_cli).
"""

import argparse


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Add dreaming subcommands to the hermes dreaming argparse parser."""
    subs = parser.add_subparsers(dest="dreaming_command", metavar="<command>")

    run_p = subs.add_parser("run", help="Run a full dreaming cycle")
    run_p.add_argument(
        "--instructions",
        default="",
        help="Free-text focus for this run (overrides dreaming.instructions in config).",
    )

    review_p = subs.add_parser("review", help="Dry-run: propose ops without applying them")
    review_p.add_argument(
        "--instructions",
        default="",
        help="Free-text focus for this run (overrides dreaming.instructions in config).",
    )

    subs.add_parser("status",  help="Show last run, candidate counts, memory usage")
    subs.add_parser("compact", help="Merge duplicates and remove obsolete entries")

    install_p = subs.add_parser("install-cron", help="Register the nightly dreaming cron job")
    install_p.add_argument(
        "--schedule",
        default=None,
        help="Cron expression (default value from config: '0 3 * * *')",
    )


def handle_cli(args: argparse.Namespace) -> None:
    """Dispatch hermes dreaming <subcommand> to the matching handler."""
    sub = getattr(args, "dreaming_command", None)

    if sub is None or sub == "help":
        from .commands.status import handle
        print(handle())
        return

    if sub == "status":
        from .commands.status import handle
        print(handle())

    elif sub == "run":
        from .commands.run import handle
        instructions = getattr(args, "instructions", "") or ""
        print(handle(instructions))

    elif sub == "review":
        from .commands.review import handle
        instructions = getattr(args, "instructions", "") or ""
        print(handle(instructions))

    elif sub == "compact":
        from .commands.compact import handle
        print(handle())

    elif sub == "install-cron":
        from .commands.install_cron import handle
        schedule = getattr(args, "schedule", None)
        print(handle(schedule=schedule))

    else:
        print(f"Unknown subcommand '{sub}'. Run: hermes dreaming --help")
