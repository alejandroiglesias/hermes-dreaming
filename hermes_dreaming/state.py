from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .paths import STATE_JSON, RUNS_DIR

logger = logging.getLogger(__name__)

RUN_SCHEMA_VERSION = 1

ERROR_TYPES = frozenset({
    "timeout",
    "internal_error",
    "tool_error",
    "input_too_large",
    "invalid_state",
    "user_canceled",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_record_path(run_ts: str):
    return RUNS_DIR / f"{run_ts.replace(':', '-')}.json"


def _sections_sidecar_path(run_ts: str):
    return RUNS_DIR / f"{run_ts.replace(':', '-')}.sections.json"


def _write_run_record(run_ts: str, record: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _run_record_path(run_ts).write_text(json.dumps(record, indent=2))


def _read_sections_for_run(run_ts: str) -> dict[str, str]:
    path = _sections_sidecar_path(run_ts)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("dreaming: failed to read sections sidecar %s: %s", path, exc)
    return {}


def _consume_sections_for_run(run_ts: str) -> dict[str, str]:
    """Read and delete the sections sidecar for a run."""
    sections = _read_sections_for_run(run_ts)
    path = _sections_sidecar_path(run_ts)
    if path.exists():
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("dreaming: failed to remove sections sidecar %s: %s", path, exc)
    return sections


def append_section(run_ts: str, section: str, markdown: str) -> None:
    """Append a phase section to the run's sidecar (overwrites same-name section)."""
    sections = _read_sections_for_run(run_ts)
    sections[section] = markdown
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _sections_sidecar_path(run_ts).write_text(json.dumps(sections, indent=2))


def read() -> dict[str, Any]:
    if not STATE_JSON.exists():
        return {}
    try:
        return json.loads(STATE_JSON.read_text())
    except json.JSONDecodeError as exc:
        logger.warning("dreaming: ignoring malformed state file %s: %s", STATE_JSON, exc)
        return {}
    except OSError:
        logger.exception("dreaming: failed to read state file %s", STATE_JSON)
        raise


def write(data: dict[str, Any]) -> None:
    STATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATE_JSON.write_text(json.dumps(data, indent=2))


def record_session_pointer(session_id: str) -> None:
    """Append a lightweight session pointer from on_session_finalize hook."""
    state = read()
    pointers: list[str] = state.get("recent_session_ids", [])
    if session_id not in pointers:
        pointers.append(session_id)
    state["recent_session_ids"] = pointers[-50:]
    write(state)


def start_run(dry_run: bool = False, instructions: str = "") -> str:
    """Record run start, return ISO timestamp used as run ID."""
    ts = _now_iso()
    current = {
        "id": ts,
        "status": "running",
        "dry_run": dry_run,
        "instructions": instructions,
        "created_at": ts,
    }
    state = read()
    state["current_run"] = {**current, "started_at": ts}
    write(state)

    initial = {
        "schema_version": RUN_SCHEMA_VERSION,
        **current,
        "ended_at": None,
        "error": None,
        "summary": {},
        "sections": {},
    }
    _write_run_record(ts, initial)
    return ts


def finish_run(
    run_ts: str,
    summary: dict[str, Any],
    error: dict[str, Any] | None = None,
) -> None:
    """Persist run record and update state after a completed run."""
    state = read()
    current = state.get("current_run") or {}
    success = bool(summary.get("success")) and error is None

    summary_payload = {
        "changes_applied": int(summary.get("changes_applied", 0) or 0),
        "candidates_staged": int(summary.get("candidates_staged", 0) or 0),
        "candidates_rejected": int(summary.get("candidates_rejected", 0) or 0),
        "notes": summary.get("notes", "") or "",
    }

    record = {
        "schema_version": RUN_SCHEMA_VERSION,
        "id": run_ts,
        "status": "completed" if success else "failed",
        "dry_run": bool(current.get("dry_run", summary.get("dry_run", False))),
        "instructions": current.get("instructions", "") or "",
        "created_at": current.get("created_at", run_ts),
        "ended_at": _now_iso(),
        "error": error,
        "summary": summary_payload,
        "sections": _consume_sections_for_run(run_ts),
    }
    _write_run_record(run_ts, record)

    state.pop("current_run", None)
    state["last_run"] = run_ts
    if success:
        state["last_successful_run"] = run_ts
    state["last_summary"] = {
        **summary_payload,
        "success": success,
        "dry_run": record["dry_run"],
        "instructions": record["instructions"],
        "error": error,
    }
    write(state)
