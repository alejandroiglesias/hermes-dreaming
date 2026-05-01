from __future__ import annotations

"""
dreaming_finalize_run — record run completion to state.json and runs/.

Call at the very end of every Dreaming cycle (both run and review modes).
"""

from typing import Any

from ..state import read as read_state, finish_run

SCHEMA = {
    "name": "dreaming_finalize_run",
    "description": (
        "Record the outcome of the current Dreaming cycle to state.json and "
        "the runs/ log. Call this at the very end of every cycle — both live "
        "runs and dry-run reviews."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "Whether the cycle completed without errors.",
            },
            "dry_run": {
                "type": "boolean",
                "description": "True if this was a /dreaming review (no mutations).",
            },
            "changes_applied": {
                "type": "integer",
                "description": "Number of durable memory operations applied (0 for dry-run).",
            },
            "candidates_staged": {
                "type": "integer",
                "description": "Number of new candidates staged in the Light phase.",
            },
            "candidates_rejected": {
                "type": "integer",
                "description": "Number of candidates rejected by REM/Deep scoring.",
            },
            "notes": {
                "type": "string",
                "description": "Optional free-text notes about the run.",
            },
        },
        "required": ["success", "dry_run"],
    },
}


def handler(params: dict[str, Any]) -> dict[str, Any]:
    state = read_state()
    run_ts = state.get("current_run", {}).get("started_at", "unknown")

    summary = {
        "success": params.get("success", False),
        "dry_run": params.get("dry_run", True),
        "changes_applied": params.get("changes_applied", 0),
        "candidates_staged": params.get("candidates_staged", 0),
        "candidates_rejected": params.get("candidates_rejected", 0),
        "notes": params.get("notes", ""),
    }

    finish_run(run_ts, summary)
    return {"finalized": True, "run_id": run_ts, **summary}
