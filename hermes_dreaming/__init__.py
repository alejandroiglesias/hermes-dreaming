from __future__ import annotations

"""
hermes-dreaming plugin entry point.

Hermes calls register(ctx) once at startup to wire all tools, commands,
CLI subcommands, and hooks.
"""

import json
import logging
import threading
import urllib.request
from pathlib import Path

from .paths import ensure_dirs
from . import state as _state

logger = logging.getLogger(__name__)


def _check_for_update(ctx) -> None:
    try:
        import yaml
        plugin_yaml = Path(__file__).parent / "plugin.yaml"
        current = yaml.safe_load(plugin_yaml.read_text())["version"]
        with urllib.request.urlopen(  # nosec B310 - safe: HTTPS to GitHub API with timeout
            "https://api.github.com/repos/alejandroiglesias/hermes-dreaming/releases/latest",
            timeout=3,
        ) as resp:
            tag = json.loads(resp.read())["tag_name"]  # e.g. "v0.3.5"
        latest = tag.lstrip("v")
        if latest != current:
            msg = (
                f"[hermes-dreaming] Update available: {current} → {latest}. "
                f"Run: hermes plugins update hermes-dreaming"
            )
            logger.warning(msg)
            ctx.inject_message(msg)
    except Exception:
        pass

_HELP = """\
/dreaming <subcommand> [instructions]

Subcommands:
  run           Run a full dreaming cycle (Light → Deep → REM)
  review        Dry-run: propose memory ops without applying them
  status        Show last run, candidate counts, and memory usage
  compact       Merge duplicates and remove obsolete entries (no new adds)
  install-cron  Register the nightly dreaming cron job (idempotent)

The `run` and `review` subcommands accept optional free-text instructions
that focus the cycle (e.g. "focus on coding-style preferences"). When no
instructions are given, the value of `dreaming.instructions` in
~/.hermes/config.yaml is used.

Examples:
  /dreaming status
  /dreaming review
  /dreaming run
  /dreaming run focus on coding-style preferences
  /dreaming install-cron
"""


def register(ctx) -> None:
    ensure_dirs()

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
            instructions = raw_args[len("run"):].strip()
            prompt = handle(instructions)
            ctx.inject_message(prompt)
            return "Dreaming cycle started (live). Running Light → Deep → REM…"

        if sub == "review":
            from .commands.review import handle
            instructions = raw_args[len("review"):].strip()
            prompt = handle(instructions)
            ctx.inject_message(prompt)
            return "Dreaming cycle started (dry-run). Running Light → Deep → REM…"

        if sub == "compact":
            from .commands.compact import handle
            return handle(raw_args[len("compact"):].strip())

        if sub == "install-cron":
            from .commands.install_cron import handle
            rest = raw_args[len("install-cron"):].strip()
            schedule = rest if rest else None
            return handle(schedule=schedule)

        return f"Unknown subcommand '{sub}'. Try /dreaming help."

    # --- Single slash command routed on first arg ---
    ctx.register_command(
        "dreaming",
        handler=_handle_slash,
        description="Hermes memory consolidation (run / review / status / compact / install-cron)",
        args_hint="<run|review|status|compact|install-cron> [instructions]",
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

    def _json_handler(h):
        def wrapped(params, **kw):
            result = h(params, **kw)
            return json.dumps(result, default=str) if isinstance(result, dict) else result
        return wrapped

    for mod in (get_state, stage_candidates, record_decisions,
                apply_memory_op, write_dream_report, finalize_run):
        ctx.register_tool(
            name=mod.SCHEMA["name"],
            toolset="dreaming",
            schema=mod.SCHEMA,
            handler=_json_handler(mod.handler),
        )

    # --- Lightweight session pointer hook ---
    def _on_session_end(session_id: str = "", **kwargs):
        if session_id:
            try:
                _state.record_session_pointer(session_id)
            except Exception as exc:
                logger.debug("dreaming: on_session_end pointer failed: %s", exc)

    ctx.register_hook("on_session_end", _on_session_end)

    # --- Background update check ---
    threading.Thread(target=_check_for_update, args=(ctx,), daemon=True).start()
