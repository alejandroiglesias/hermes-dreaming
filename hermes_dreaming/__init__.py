from __future__ import annotations

"""
hermes-dreaming plugin entry point.

Hermes calls register(ctx) once at startup to wire all tools, commands,
CLI subcommands, and hooks.
"""

import json
import logging
import threading
import time
import urllib.request
from pathlib import Path

from .paths import ensure_dirs, DREAMING_DIR
from . import state as _state

logger = logging.getLogger(__name__)

_UPDATE_CACHE_TTL = 6 * 3600  # 6 hours, same cadence as Hermes itself
_UPDATE_CACHE_FILE = DREAMING_DIR / ".update_check"
_RELEASES_URL = (
    "https://api.github.com/repos/alejandroiglesias/hermes-dreaming/releases/latest"
)


def _current_version() -> str:
    import yaml
    plugin_yaml = Path(__file__).parent.parent / "plugin.yaml"
    return yaml.safe_load(plugin_yaml.read_text())["version"]


def _read_update_cache() -> str | None:
    """Return the cached latest version if the cache is still fresh, else None."""
    if not _UPDATE_CACHE_FILE.exists():
        return None
    try:
        cached = json.loads(_UPDATE_CACHE_FILE.read_text())
    except Exception:
        logger.warning("hermes-dreaming: malformed update cache at %s", _UPDATE_CACHE_FILE, exc_info=True)
        return None
    if time.time() - cached.get("ts", 0) >= _UPDATE_CACHE_TTL:
        return None
    return cached.get("latest")


def _fetch_and_cache_latest() -> str | None:
    """Hit the GitHub releases API and write the cache. Returns latest version or None."""
    try:
        with urllib.request.urlopen(  # nosec B310 - safe: HTTPS to GitHub API with timeout
            _RELEASES_URL, timeout=5,
        ) as resp:
            tag = json.loads(resp.read())["tag_name"]
    except Exception:
        logger.warning("hermes-dreaming: update fetch failed", exc_info=True)
        return None
    latest = tag.lstrip("v")
    try:
        _UPDATE_CACHE_FILE.write_text(json.dumps({"ts": time.time(), "latest": latest}))
    except Exception:
        logger.warning("hermes-dreaming: failed to write update cache", exc_info=True)
    return latest


def _notify_if_update_available(latest: str | None) -> None:
    """Print to stdout — the only sink that's visible at plugin-load time.

    ctx.inject_message is unusable here: plugins load before the CLI sets its
    _cli_ref (see hermes_cli/plugins.py — discover_plugins() runs at module
    import in model_tools.py, which executes before HermesCLI.__init__).
    """
    if not latest:
        return
    current = _current_version()
    if latest != current:
        msg = (
            f"[hermes-dreaming] Update available: {current} → {latest}. "
            f"Run: hermes plugins update hermes-dreaming"
        )
        logger.warning(msg)
        print(msg, flush=True)


def _check_for_update() -> None:
    """Notify from cache immediately; refresh cache in background."""
    try:
        cached = _read_update_cache()
    except Exception:
        logger.warning("hermes-dreaming: update cache read failed", exc_info=True)
        cached = None

    try:
        _notify_if_update_available(cached)
    except Exception:
        logger.warning("hermes-dreaming: update notify failed", exc_info=True)

    def _refresh():
        try:
            latest = _fetch_and_cache_latest()
            if latest and not cached:
                _notify_if_update_available(latest)
        except Exception:
            logger.warning("hermes-dreaming: background update check failed", exc_info=True)

    threading.Thread(target=_refresh, daemon=True).start()

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

    # --- Update check: fires from cache synchronously, refreshes cache in background ---
    _check_for_update()
