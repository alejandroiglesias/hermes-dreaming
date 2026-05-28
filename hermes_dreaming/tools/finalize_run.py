from __future__ import annotations

"""
dreaming_finalize_run — record run completion to state.json and runs/.

Call at the very end of every Dreaming cycle (both run and review modes).
"""

from typing import Any

from ..state import ERROR_TYPES, ensure_current_run, read as read_state, finish_run

SCHEMA = {
    "name": "dreaming_finalize_run",
    "description": (
        "Record the outcome of the current Dreaming cycle to state.json and "
        "the runs/ log. Call this at the very end of every cycle — both live "
        "runs and dry-run reviews. When success=false, pass error_type and "
        "error_message so /dreaming status can surface why the run failed."
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
                "description": "Number of candidates rejected by Deep/REM scoring.",
            },
            "notes": {
                "type": "string",
                "description": "Optional free-text notes about the run.",
            },
            "error_type": {
                "type": "string",
                "enum": sorted(ERROR_TYPES),
                "description": (
                    "Required when success=false. Typed failure mode. "
                    "Use 'tool_error' if a dreaming_* tool raised, 'timeout' "
                    "if a deadline was exceeded, 'invalid_state' for missing/"
                    "malformed state, 'input_too_large' if memory/sessions "
                    "exceeded limits, otherwise 'internal_error'."
                ),
            },
            "error_message": {
                "type": "string",
                "description": "Short human-readable reason. Required when success=false.",
            },
        },
        "required": ["success", "dry_run"],
    },
}


def handler(params: dict[str, Any], **_) -> dict[str, Any]:
    state = read_state()
    current = state.get("current_run") or ensure_current_run(
        dry_run=bool(params.get("dry_run", False)),
        instructions="auto-started by dreaming_finalize_run",
    )
    run_ts = current.get("started_at", "unknown")

    success = bool(params.get("success", False))

    summary = {
        "success": success,
        "dry_run": bool(params.get("dry_run", True)),
        "changes_applied": params.get("changes_applied", 0),
        "candidates_staged": params.get("candidates_staged", 0),
        "candidates_rejected": params.get("candidates_rejected", 0),
        "notes": params.get("notes", ""),
    }

    error: dict[str, Any] | None = None
    if not success:
        raw_type = (params.get("error_type") or "").strip()
        message = (params.get("error_message") or "").strip()

        if raw_type in ERROR_TYPES:
            error_type = raw_type
        else:
            error_type = "internal_error"
            if raw_type:
                # Preserve the original value for diagnostics.
                prefix = f"[unknown error_type {raw_type!r}] "
                message = prefix + message if message else prefix.strip()
            elif not message:
                message = "Run reported success=false with no error details."
        if not message:
            message = "(no error message provided)"

        error = {"type": error_type, "message": message}

    finish_run(run_ts, summary, error=error)
    return {"finalized": True, "run_id": run_ts, "error": error, **summary}
