from __future__ import annotations

"""
dreaming_get_state — read-only snapshot of current dreaming state.

Returns a JSON-serialisable dict with:
  - memory_md:   {raw, entries, char_count, char_limit, usage_pct}
  - user_md:     same
  - recent_sessions: list of session digest dicts
  - prior_candidates: unresolved candidates from previous runs
  - last_run_summary: from state.json
"""

from typing import Any

from ..dreams_md import open_run
from ..memory_io import read_both
from ..session_reader import list_recent
from ..sidecar import read_candidates
from ..state import ensure_current_run, read as read_state
from ..config import load as load_config

SCHEMA = {
    "name": "dreaming_get_state",
    "description": (
        "Return the current Dreaming state: contents of MEMORY.md and USER.md "
        "with capacity info, recent session digests, prior staged candidates, "
        "and last run summary. Call this at the start of a Dreaming cycle."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ensure_run": {
                "type": "boolean",
                "description": (
                    "When true (default), bootstrap current_run if missing so downstream "
                    "dreaming_* tool calls are bound to a generated run_id."
                ),
            },
            "dry_run": {
                "type": "boolean",
                "description": (
                    "Used only when ensure_run=true and no current_run exists. "
                    "false for live runs, true for review mode."
                ),
            },
            "instructions": {
                "type": "string",
                "description": (
                    "Optional run focus persisted when ensure_run bootstraps a run."
                ),
            },
        },
        "required": [],
    },
}


def handler(_params: dict[str, Any], **_) -> dict[str, Any]:
    ensure_run = _params.get("ensure_run", True)
    dry_run = bool(_params.get("dry_run", False))
    instructions = (_params.get("instructions", "") or "").strip()

    if ensure_run:
        state_before = read_state()
        if not state_before.get("current_run"):
            ensure_current_run(dry_run=dry_run, instructions=instructions)
            open_run(dry_run=dry_run)

    cfg = load_config()
    files = read_both()
    sessions = list_recent(limit=cfg.recent_sessions_limit)
    candidates = read_candidates()
    state = read_state()

    return {
        "memory_md": {
            "raw": files["memory"].raw,
            "entries": files["memory"].entries,
            "char_count": files["memory"].char_count,
            "char_limit": files["memory"].char_limit,
            "usage_pct": files["memory"].usage_pct,
            "near_capacity": files["memory"].near_capacity,
        },
        "user_md": {
            "raw": files["user"].raw,
            "entries": files["user"].entries,
            "char_count": files["user"].char_count,
            "char_limit": files["user"].char_limit,
            "usage_pct": files["user"].usage_pct,
            "near_capacity": files["user"].near_capacity,
        },
        "recent_sessions": [
            {
                "session_id": s.session_id,
                "title": s.title,
                "date": s.date_str,
                "message_count": s.message_count,
                "user_turns": s.user_turns,
            }
            for s in sessions
        ],
        "prior_candidates": candidates,
        "current_run": state.get("current_run", {}),
        "last_run_summary": state.get("last_summary", {}),
    }
