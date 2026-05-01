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

from ..memory_io import read_both
from ..session_reader import list_recent
from ..sidecar import read_candidates
from ..state import read as read_state
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
        "properties": {},
        "required": [],
    },
}


def handler(_params: dict[str, Any]) -> dict[str, Any]:
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
        "last_run_summary": state.get("last_summary", {}),
    }
