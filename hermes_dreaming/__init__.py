from __future__ import annotations

"""
hermes-dreaming plugin entry point.

Hermes calls register(ctx) once at startup to wire all tools, commands,
CLI subcommands, and hooks.
"""

import logging

from .paths import ensure_dirs
from . import state as _state

logger = logging.getLogger(__name__)

_HELP = """\
/dreaming <subcommand>

Subcommands:
  run           Run a full dreaming cycle (Light → REM → Deep)
  review        Dry-run: propose memory ops without applying them
  status        Show last run, candidate counts, and memory usage
  compact       Merge duplicates and remove obsolete entries (no new adds)
  install-cron  Register the nightly dreaming cron job (idempotent)

Examples:
  /dreaming status
  /dreaming review
  /dreaming run
  /dreaming install-cron
"""


def _handle_slash(raw_args: str) -> str:
    argv = raw_args.strip().split()
    sub = argv[0].lower() if argv else "help"

    if sub in ("help", "-h", "--help"):
        return _HELP

    if sub == "status":
        from .commands.status import handle
        return handle(raw_args[len("status"):].strip())

    if sub == "run":
        from .commands.run import handle
        return handle(raw_args[len("run"):].strip())

    if sub == "review":
        from .commands.review import handle
        return handle(raw_args[len("review"):].strip())

    if sub == "compact":
        from .commands.compact import handle
        return handle(raw_args[len("compact"):].strip())

    if sub == "install-cron":
        from .commands.install_cron import handle
        rest = raw_args[len("install-cron"):].strip()
        schedule = rest if rest else None
        return handle(schedule=schedule)

    return f"Unknown subcommand '{sub}'. Try /dreaming help."


def register(ctx) -> None:
    ensure_dirs()

    # --- Single slash command routed on first arg ---
    ctx.register_command(
        "dreaming",
        handler=_handle_slash,
        description="Hermes memory consolidation (run / review / status / compact / install-cron)",
        args_hint="<run|review|status|compact|install-cron>",
    )

    # --- Single CLI command: hermes dreaming <subcmd> ---
    from .cli import register_cli, handle_cli
    ctx.register_cli_command(
        name="dreaming",
        help="Hermes background memory consolidation",
        setup_fn=register_cli,
        handler_fn=handle_cli,
        description="Curate MEMORY.md and USER.md by promoting, replacing, and removing memories.",
    )

    # --- Agent-callable tools ---
    from .tools import (
        get_state, stage_candidates, record_decisions,
        apply_memory_op, write_dream_report, finalize_run,
    )

    for mod in (get_state, stage_candidates, record_decisions,
                apply_memory_op, write_dream_report, finalize_run):
        ctx.register_tool(
            name=mod.SCHEMA["name"],
            schema=mod.SCHEMA,
            handler=mod.handler,
        )

    # --- Lightweight session pointer hook ---
    def _on_session_end(session_id: str = "", **kwargs):
        if session_id:
            try:
                _state.record_session_pointer(session_id)
            except Exception as exc:
                logger.debug("dreaming: on_session_end pointer failed: %s", exc)

    ctx.register_hook("on_session_end", _on_session_end)
