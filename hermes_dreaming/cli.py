from __future__ import annotations

"""
CLI wiring for `hermes dreaming <subcommand>`.

Provides argparse setup (register_cli) and dispatch (handle_cli).
"""

import argparse


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Add dreaming subcommands to the hermes dreaming argparse parser."""
    subs = parser.add_subparsers(dest="dreaming_command", metavar="<command>")

    subs.add_parser("run",     help="Run a full dreaming cycle")
    subs.add_parser("review",  help="Dry-run: propose ops without applying them")
    subs.add_parser("status",  help="Show last run, candidate counts, memory usage")
    subs.add_parser("compact", help="Merge duplicates and remove obsolete entries")

    install_p = subs.add_parser("install-cron", help="Register the nightly dreaming cron job")
    install_p.add_argument(
        "--schedule",
        default="0 3 * * *",
        help="Cron expression (default: '0 3 * * *')",
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
        print(handle())

    elif sub == "review":
        from .commands.review import handle
        print(handle())

    elif sub == "compact":
        from .commands.compact import handle
        print(handle())

    elif sub == "install-cron":
        from .commands.install_cron import handle
        schedule = getattr(args, "schedule", "0 3 * * *")
        print(handle(schedule=schedule))

    else:
        print(f"Unknown subcommand '{sub}'. Run: hermes dreaming --help")
