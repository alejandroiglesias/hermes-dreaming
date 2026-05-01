from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import STATE_JSON, RUNS_DIR

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def start_run(dry_run: bool = False) -> str:
    """Record run start, return ISO timestamp used as run ID."""
    ts = _now_iso()
    state = read()
    state["current_run"] = {"started_at": ts, "dry_run": dry_run}
    write(state)
    return ts


def finish_run(run_ts: str, summary: dict[str, Any]) -> None:
    """Persist run record and update state after a completed run."""
    run_record = {"run_id": run_ts, **summary}
    run_file = RUNS_DIR / f"{run_ts.replace(':', '-')}.json"
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_file.write_text(json.dumps(run_record, indent=2))

    state = read()
    state.pop("current_run", None)
    state["last_run"] = run_ts
    if summary.get("success"):
        state["last_successful_run"] = run_ts
    state["last_summary"] = summary
    write(state)
