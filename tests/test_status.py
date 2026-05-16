"""
Tests for /dreaming status output: error and instructions display.
"""
from __future__ import annotations

import json

import pytest

import hermes_dreaming.paths as _paths
import hermes_dreaming.state as _state
import hermes_dreaming.memory_io as _mio
import hermes_dreaming.commands.status as _status_cmd


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    mem_dir = tmp_path / "memories"
    mem_dir.mkdir()
    dream_dir = tmp_path / "dreaming"
    dream_dir.mkdir()
    (mem_dir / "MEMORY.md").write_text("", encoding="utf-8")
    (mem_dir / "USER.md").write_text("", encoding="utf-8")

    for mod in (_paths, _state, _mio, _status_cmd):
        if hasattr(mod, "MEMORY_MD"):
            monkeypatch.setattr(mod, "MEMORY_MD", mem_dir / "MEMORY.md")
        if hasattr(mod, "USER_MD"):
            monkeypatch.setattr(mod, "USER_MD", mem_dir / "USER.md")
        if hasattr(mod, "DREAMING_DIR"):
            monkeypatch.setattr(mod, "DREAMING_DIR", dream_dir)
        if hasattr(mod, "STATE_JSON"):
            monkeypatch.setattr(mod, "STATE_JSON", dream_dir / "state.json")
        if hasattr(mod, "CANDIDATES_JSONL"):
            monkeypatch.setattr(mod, "CANDIDATES_JSONL", dream_dir / "candidates.jsonl")
        if hasattr(mod, "PROMOTIONS_JSONL"):
            monkeypatch.setattr(mod, "PROMOTIONS_JSONL", dream_dir / "promotions.jsonl")
        if hasattr(mod, "DREAMS_MD"):
            monkeypatch.setattr(mod, "DREAMS_MD", dream_dir / "DREAMS.md")
        if hasattr(mod, "RUNS_DIR"):
            monkeypatch.setattr(mod, "RUNS_DIR", dream_dir / "runs")

    yield {"dream_dir": dream_dir}


def _write_state(dream_dir, state: dict) -> None:
    (dream_dir / "state.json").write_text(json.dumps(state))


def test_status_shows_error_when_last_run_failed(isolated_paths):
    _write_state(
        isolated_paths["dream_dir"],
        {
            "last_run": "2099-01-01T03:00:00+00:00",
            "last_successful_run": "never",
            "last_summary": {
                "success": False,
                "dry_run": False,
                "changes_applied": 0,
                "candidates_rejected": 0,
                "error": {"type": "timeout", "message": "deadline exceeded"},
            },
        },
    )
    out = _status_cmd.handle()
    assert "Last run error:" in out
    assert "timeout" in out
    assert "deadline exceeded" in out


def test_status_shows_instructions_when_present(isolated_paths):
    _write_state(
        isolated_paths["dream_dir"],
        {
            "last_run": "2099-01-01T03:00:00+00:00",
            "last_successful_run": "2099-01-01T03:00:00+00:00",
            "last_summary": {
                "success": True,
                "dry_run": False,
                "changes_applied": 1,
                "candidates_rejected": 2,
                "instructions": "focus on coding-style preferences",
                "error": None,
            },
        },
    )
    out = _status_cmd.handle()
    assert "Last run focus:" in out
    assert "focus on coding-style preferences" in out
    assert "Last run error:" not in out


def test_status_omits_error_and_focus_when_absent(isolated_paths):
    _write_state(
        isolated_paths["dream_dir"],
        {
            "last_run": "2099-01-01T03:00:00+00:00",
            "last_summary": {
                "success": True,
                "changes_applied": 0,
                "candidates_rejected": 0,
            },
        },
    )
    out = _status_cmd.handle()
    assert "Last run error:" not in out
    assert "Last run focus:" not in out


def test_status_shows_current_run_focus(isolated_paths):
    _write_state(
        isolated_paths["dream_dir"],
        {
            "current_run": {
                "id": "2099-01-01T03:00:00+00:00",
                "started_at": "2099-01-01T03:00:00+00:00",
                "dry_run": False,
                "instructions": "ignore debugging notes",
            },
        },
    )
    out = _status_cmd.handle()
    assert "Current run:" in out
    assert "Current run focus:" in out
    assert "ignore debugging notes" in out
