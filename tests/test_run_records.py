"""
Tests for the canonical run-record schema and error taxonomy.

Covers:
- `state.start_run` writes an initial "running" record.
- `state.finish_run` writes a canonical, schema-versioned record.
- `state.finish_run` with an error sets status="failed" and persists the error.
- `dreaming_finalize_run` tool defaults / coerces error_type when needed.
- `state.append_section` accumulates sections that finish_run folds in.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import hermes_dreaming.paths as _paths
import hermes_dreaming.state as _state
import hermes_dreaming.dreams_md as _dreams
import hermes_dreaming.tools.finalize_run as _finalize


REQUIRED_RECORD_KEYS = {
    "schema_version",
    "id",
    "status",
    "dry_run",
    "instructions",
    "created_at",
    "ended_at",
    "error",
    "summary",
    "sections",
}


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    dream_dir = tmp_path / "dreaming"
    dream_dir.mkdir()
    runs_dir = dream_dir / "runs"
    runs_dir.mkdir()

    for mod in (_paths, _state, _dreams, _finalize):
        if hasattr(mod, "DREAMING_DIR"):
            monkeypatch.setattr(mod, "DREAMING_DIR", dream_dir)
        if hasattr(mod, "STATE_JSON"):
            monkeypatch.setattr(mod, "STATE_JSON", dream_dir / "state.json")
        if hasattr(mod, "RUNS_DIR"):
            monkeypatch.setattr(mod, "RUNS_DIR", runs_dir)
        if hasattr(mod, "DREAMS_MD"):
            monkeypatch.setattr(mod, "DREAMS_MD", dream_dir / "DREAMS.md")

    yield {"dream_dir": dream_dir, "runs_dir": runs_dir}


def _load_run(runs_dir: Path, run_ts: str) -> dict:
    path = runs_dir / f"{run_ts.replace(':', '-')}.json"
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# start_run / finish_run schema
# ---------------------------------------------------------------------------

def test_start_run_writes_initial_running_record(isolated_paths):
    run_ts = _state.start_run(dry_run=False, instructions="focus on X")
    rec = _load_run(isolated_paths["runs_dir"], run_ts)

    assert REQUIRED_RECORD_KEYS <= set(rec)
    assert rec["schema_version"] == _state.RUN_SCHEMA_VERSION
    assert rec["status"] == "running"
    assert rec["dry_run"] is False
    assert rec["instructions"] == "focus on X"
    assert rec["created_at"] == run_ts
    assert rec["ended_at"] is None
    assert rec["error"] is None
    assert rec["sections"] == {}


def test_finish_run_canonical_completed_schema(isolated_paths):
    run_ts = _state.start_run(dry_run=False, instructions="")
    _state.finish_run(
        run_ts,
        {
            "success": True,
            "dry_run": False,
            "changes_applied": 2,
            "candidates_staged": 5,
            "candidates_rejected": 3,
            "notes": "ok",
        },
    )
    rec = _load_run(isolated_paths["runs_dir"], run_ts)

    assert REQUIRED_RECORD_KEYS <= set(rec)
    assert rec["schema_version"] == _state.RUN_SCHEMA_VERSION
    assert rec["status"] == "completed"
    assert rec["dry_run"] is False
    assert rec["error"] is None
    assert rec["id"] == run_ts
    assert rec["created_at"] == run_ts
    assert rec["ended_at"] is not None
    assert rec["summary"] == {
        "changes_applied": 2,
        "candidates_staged": 5,
        "candidates_rejected": 3,
        "notes": "ok",
    }


def test_finish_run_with_error_marks_failed(isolated_paths):
    run_ts = _state.start_run(dry_run=False, instructions="")
    _state.finish_run(
        run_ts,
        {"success": False, "dry_run": False},
        error={"type": "timeout", "message": "exceeded budget"},
    )
    rec = _load_run(isolated_paths["runs_dir"], run_ts)

    assert rec["status"] == "failed"
    assert rec["error"] == {"type": "timeout", "message": "exceeded budget"}

    state = _state.read()
    assert state.get("last_run") == run_ts
    assert state.get("last_successful_run") in (None, "")  # not advanced on failure
    assert state["last_summary"]["error"] == {"type": "timeout", "message": "exceeded budget"}


def test_finish_run_overwrites_initial_record(isolated_paths):
    run_ts = _state.start_run(dry_run=True, instructions="")
    _state.finish_run(
        run_ts,
        {"success": True, "dry_run": True, "changes_applied": 0,
         "candidates_staged": 1, "candidates_rejected": 1},
    )
    rec = _load_run(isolated_paths["runs_dir"], run_ts)
    assert rec["status"] == "completed"
    assert rec["dry_run"] is True


# ---------------------------------------------------------------------------
# append_section -> sections folded into finish_run
# ---------------------------------------------------------------------------

def test_finish_run_folds_in_sections(isolated_paths):
    run_ts = _state.start_run(dry_run=False, instructions="")
    _state.append_section(run_ts, "Light Sleep", "scanned 5 sessions")
    _state.append_section(run_ts, "Summary", "0 changes")

    _state.finish_run(
        run_ts,
        {"success": True, "dry_run": False, "changes_applied": 0,
         "candidates_staged": 0, "candidates_rejected": 0},
    )
    rec = _load_run(isolated_paths["runs_dir"], run_ts)

    assert rec["sections"]["Light Sleep"] == "scanned 5 sessions"
    assert rec["sections"]["Summary"] == "0 changes"

    # Sidecar should be consumed/removed
    sidecar = isolated_paths["runs_dir"] / f"{run_ts.replace(':', '-')}.sections.json"
    assert not sidecar.exists()


# ---------------------------------------------------------------------------
# finalize_run tool — error_type handling
# ---------------------------------------------------------------------------

def test_finalize_tool_defaults_error_type_when_unsuccessful(isolated_paths):
    run_ts = _state.start_run(dry_run=False, instructions="")
    result = _finalize.handler({"success": False, "dry_run": False})
    rec = _load_run(isolated_paths["runs_dir"], run_ts)

    assert rec["status"] == "failed"
    assert rec["error"]["type"] == "internal_error"
    assert rec["error"]["message"]  # non-empty default
    assert result["error"]["type"] == "internal_error"


def test_finalize_tool_coerces_unknown_error_type(isolated_paths):
    run_ts = _state.start_run(dry_run=False, instructions="")
    _finalize.handler({
        "success": False,
        "dry_run": False,
        "error_type": "made_up_thing",
        "error_message": "real reason",
    })
    rec = _load_run(isolated_paths["runs_dir"], run_ts)

    assert rec["error"]["type"] == "internal_error"
    # The unknown type label is preserved in the message for diagnostics.
    assert "made_up_thing" in rec["error"]["message"]
    assert "real reason" in rec["error"]["message"]


def test_finalize_tool_accepts_known_error_type(isolated_paths):
    run_ts = _state.start_run(dry_run=False, instructions="")
    _finalize.handler({
        "success": False,
        "dry_run": False,
        "error_type": "tool_error",
        "error_message": "stage_candidates raised",
    })
    rec = _load_run(isolated_paths["runs_dir"], run_ts)

    assert rec["error"] == {"type": "tool_error", "message": "stage_candidates raised"}


def test_finalize_tool_success_leaves_no_error(isolated_paths):
    run_ts = _state.start_run(dry_run=False, instructions="")
    _finalize.handler({
        "success": True,
        "dry_run": False,
        "changes_applied": 1,
        "candidates_staged": 2,
        "candidates_rejected": 1,
    })
    rec = _load_run(isolated_paths["runs_dir"], run_ts)

    assert rec["status"] == "completed"
    assert rec["error"] is None
