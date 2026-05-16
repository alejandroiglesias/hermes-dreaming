"""
Tests for dreaming_write_dream_report tool.

Covers:
- Writes the section to DREAMS.md (existing behaviour, regression guard).
- Also appends the section to the per-run sidecar in runs/.
- Sidecar is not written when no current_run is in state.
- Handler returns an error for an unknown section name.
"""
from __future__ import annotations

import json

import pytest

import hermes_dreaming.paths as _paths
import hermes_dreaming.state as _state
import hermes_dreaming.dreams_md as _dreams
import hermes_dreaming.tools.write_dream_report as _wdr


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    dream_dir = tmp_path / "dreaming"
    dream_dir.mkdir()
    (dream_dir / "runs").mkdir()

    for mod in (_paths, _state, _dreams, _wdr):
        if hasattr(mod, "DREAMING_DIR"):
            monkeypatch.setattr(mod, "DREAMING_DIR", dream_dir)
        if hasattr(mod, "STATE_JSON"):
            monkeypatch.setattr(mod, "STATE_JSON", dream_dir / "state.json")
        if hasattr(mod, "RUNS_DIR"):
            monkeypatch.setattr(mod, "RUNS_DIR", dream_dir / "runs")
        if hasattr(mod, "DREAMS_MD"):
            monkeypatch.setattr(mod, "DREAMS_MD", dream_dir / "DREAMS.md")

    yield {"dream_dir": dream_dir}


def _set_current_run(dream_dir, run_ts: str = "2099-01-01T03:00:00+00:00") -> str:
    (dream_dir / "state.json").write_text(
        json.dumps({
            "current_run": {
                "started_at": run_ts,
                "id": run_ts,
                "dry_run": False,
                "instructions": "",
            }
        })
    )
    return run_ts


# ---------------------------------------------------------------------------
# DREAMS.md is still written (regression guard)
# ---------------------------------------------------------------------------

def test_handler_appends_to_dreams_md(isolated_paths):
    _set_current_run(isolated_paths["dream_dir"])
    # DREAMS.md needs a run header first (normally written by open_run)
    dreams_md = isolated_paths["dream_dir"] / "DREAMS.md"
    dreams_md.write_text("\n## 2099-01-01 03:00 UTC — Dreaming run\n")

    result = _wdr.handler({"section": "Light Sleep", "markdown": "scanned 5 sessions"})

    assert result == {"written": True, "section": "Light Sleep"}
    assert "### Light Sleep" in dreams_md.read_text()
    assert "scanned 5 sessions" in dreams_md.read_text()


# ---------------------------------------------------------------------------
# Sidecar is written alongside DREAMS.md
# ---------------------------------------------------------------------------

def test_handler_writes_section_to_sidecar(isolated_paths):
    run_ts = _set_current_run(isolated_paths["dream_dir"])
    dreams_md = isolated_paths["dream_dir"] / "DREAMS.md"
    dreams_md.write_text("\n## 2099-01-01 03:00 UTC — Dreaming run\n")

    _wdr.handler({"section": "Light Sleep", "markdown": "first section"})

    sidecar = isolated_paths["dream_dir"] / "runs" / f"{run_ts.replace(':', '-')}.sections.json"
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["Light Sleep"] == "first section"


def test_handler_accumulates_multiple_sections_in_sidecar(isolated_paths):
    run_ts = _set_current_run(isolated_paths["dream_dir"])
    dreams_md = isolated_paths["dream_dir"] / "DREAMS.md"
    dreams_md.write_text("\n## 2099-01-01 03:00 UTC — Dreaming run\n")

    _wdr.handler({"section": "Light Sleep", "markdown": "light content"})
    _wdr.handler({"section": "Deep Sleep", "markdown": "deep content"})
    _wdr.handler({"section": "Summary", "markdown": "summary content"})

    sidecar = isolated_paths["dream_dir"] / "runs" / f"{run_ts.replace(':', '-')}.sections.json"
    data = json.loads(sidecar.read_text())
    assert data["Light Sleep"] == "light content"
    assert data["Deep Sleep"] == "deep content"
    assert data["Summary"] == "summary content"


def test_handler_does_not_write_sidecar_when_no_current_run(isolated_paths):
    """No state.json / no current_run → DREAMS.md still written, no sidecar created."""
    dreams_md = isolated_paths["dream_dir"] / "DREAMS.md"
    dreams_md.write_text("\n## 2099-01-01 03:00 UTC — Dreaming run\n")

    result = _wdr.handler({"section": "Light Sleep", "markdown": "orphan section"})

    assert result["written"] is True
    runs_dir = isolated_paths["dream_dir"] / "runs"
    sidecars = list(runs_dir.glob("*.sections.json"))
    assert sidecars == [], f"unexpected sidecar: {sidecars}"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_handler_returns_error_for_unknown_section(isolated_paths):
    result = _wdr.handler({"section": "Made Up", "markdown": "some content"})
    assert "error" in result


def test_handler_returns_error_when_section_missing(isolated_paths):
    result = _wdr.handler({"markdown": "some content"})
    assert result == {"error": "'section' is required"}


def test_handler_returns_error_when_markdown_missing(isolated_paths):
    result = _wdr.handler({"section": "Light Sleep"})
    assert result == {"error": "'markdown' is required"}
