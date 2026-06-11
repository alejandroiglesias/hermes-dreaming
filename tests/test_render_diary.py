"""
Tests for dreams_md.render_dreams_md_from_runs().

Covers:
- Renders completed records with their sections in known order.
- Renders failed records with error section.
- Ignores sidecar files (*.sections.json).
- Sorts records by created_at (oldest first).
- Handles empty runs/ directory.
- Output is written to DREAMS.md.
"""
from __future__ import annotations

import json

import pytest

import hermes_dreaming.paths as _paths
import hermes_dreaming.dreams_md as _dreams


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    dream_dir = tmp_path / "dreaming"
    dream_dir.mkdir()
    runs_dir = dream_dir / "runs"
    runs_dir.mkdir()

    for mod in (_paths, _dreams):
        if hasattr(mod, "DREAMING_DIR"):
            monkeypatch.setattr(mod, "DREAMING_DIR", dream_dir)
        if hasattr(mod, "RUNS_DIR"):
            monkeypatch.setattr(mod, "RUNS_DIR", runs_dir)
        if hasattr(mod, "DREAMS_MD"):
            monkeypatch.setattr(mod, "DREAMS_MD", dream_dir / "DREAMS.md")

    yield {"dream_dir": dream_dir, "runs_dir": runs_dir}


def _write_record(runs_dir, record: dict) -> None:
    run_id = record["id"]
    path = runs_dir / f"{run_id.replace(':', '-')}.json"
    path.write_text(json.dumps(record))


def _base_record(run_id: str, **kwargs) -> dict:
    return {
        "schema_version": 1,
        "id": run_id,
        "status": "completed",
        "dry_run": False,
        "instructions": "",
        "created_at": run_id,
        "ended_at": run_id,
        "error": None,
        "summary": {"changes_applied": 0, "candidates_staged": 0, "candidates_rejected": 0, "notes": ""},
        "sections": {},
        **kwargs,
    }


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------

def test_render_includes_sections_in_known_order(isolated_paths):
    _write_record(isolated_paths["runs_dir"], _base_record(
        "2099-01-01T03:00:00+00:00",
        sections={
            "Light Sleep": "light body",
            "Deep Sleep": "deep body",
            "REM Sleep": "rem body",
            "Summary": "summary body",
        },
    ))

    rendered = _dreams.render_dreams_md_from_runs()

    assert "### Light Sleep" in rendered
    assert "light body" in rendered
    assert "### Deep Sleep" in rendered
    assert "### REM Sleep" in rendered
    assert "### Summary" in rendered
    # Check order: Light before Deep before REM before Summary
    assert rendered.index("### Light Sleep") < rendered.index("### Deep Sleep")
    assert rendered.index("### Deep Sleep") < rendered.index("### REM Sleep")
    assert rendered.index("### REM Sleep") < rendered.index("### Summary")


def test_render_writes_to_dreams_md(isolated_paths):
    _write_record(isolated_paths["runs_dir"], _base_record(
        "2099-01-01T03:00:00+00:00",
        sections={"Summary": "one change applied"},
    ))
    _dreams.render_dreams_md_from_runs()

    written = (isolated_paths["dream_dir"] / "DREAMS.md").read_text()
    assert "one change applied" in written


def test_render_includes_dreaming_run_header(isolated_paths):
    _write_record(isolated_paths["runs_dir"], _base_record("2099-06-15T03:00:00+00:00"))
    rendered = _dreams.render_dreams_md_from_runs()
    assert rendered.startswith(f"\n{_dreams._RUN_SEPARATOR}\n\n## ")
    assert "Dreaming run" in rendered
    assert "## " in rendered


def test_render_separates_each_run_with_ruler(isolated_paths):
    _write_record(isolated_paths["runs_dir"], _base_record(
        "2099-01-01T03:00:00+00:00", sections={"Summary": "first"}
    ))
    _write_record(isolated_paths["runs_dir"], _base_record(
        "2099-01-02T03:00:00+00:00", sections={"Summary": "second"}
    ))

    rendered = _dreams.render_dreams_md_from_runs()

    assert rendered.count(f"\n{_dreams._RUN_SEPARATOR}\n\n## ") == 2


def test_render_strips_redundant_section_headings(isolated_paths):
    _write_record(isolated_paths["runs_dir"], _base_record(
        "2099-01-01T03:00:00+00:00",
        sections={
            "REM Sleep": "## REM Sleep — June 4, 2026\n\n### Scored decisions\nok\n\n### Summary\nrem result",
            "Summary": "### Summary\n## Dreaming Summary — June 4, 2026\n\nfinal",
        },
    ))

    rendered = _dreams.render_dreams_md_from_runs()

    assert "## REM Sleep — June 4, 2026" not in rendered
    assert "## Dreaming Summary — June 4, 2026" not in rendered
    assert rendered.count("### REM Sleep") == 1
    assert rendered.count("### Summary") == 1
    assert "### Scored decisions" in rendered
    assert "rem result" in rendered
    assert "final" in rendered


def test_render_supports_legacy_run_id_records(isolated_paths):
    path = isolated_paths["runs_dir"] / "2099-01-01T03-00-00+00-00.json"
    path.write_text(json.dumps({
        "run_id": "2099-01-01T03:00:00+00:00",
        "success": True,
        "dry_run": False,
        "notes": "legacy summary",
    }))

    rendered = _dreams.render_dreams_md_from_runs()

    assert "## 2099-01-01" in rendered
    assert "Dreaming run — " not in rendered
    assert "### Summary" in rendered
    assert "legacy summary" in rendered


def test_render_marks_dry_run_in_header(isolated_paths):
    _write_record(isolated_paths["runs_dir"], _base_record(
        "2099-01-01T03:00:00+00:00", dry_run=True
    ))
    rendered = _dreams.render_dreams_md_from_runs()
    assert "dry-run" in rendered


# ---------------------------------------------------------------------------
# Error records
# ---------------------------------------------------------------------------

def test_render_includes_error_section_for_failed_runs(isolated_paths):
    _write_record(isolated_paths["runs_dir"], _base_record(
        "2099-01-01T03:00:00+00:00",
        status="failed",
        error={"type": "timeout", "message": "budget exceeded"},
    ))
    rendered = _dreams.render_dreams_md_from_runs()
    assert "### Error" in rendered
    assert "timeout" in rendered
    assert "budget exceeded" in rendered


# ---------------------------------------------------------------------------
# Sorting and multiple records
# ---------------------------------------------------------------------------

def test_render_sorts_by_created_at_oldest_first(isolated_paths):
    _write_record(isolated_paths["runs_dir"], _base_record(
        "2099-03-01T03:00:00+00:00", sections={"Summary": "second"}
    ))
    _write_record(isolated_paths["runs_dir"], _base_record(
        "2099-01-01T03:00:00+00:00", sections={"Summary": "first"}
    ))

    rendered = _dreams.render_dreams_md_from_runs()
    assert rendered.index("first") < rendered.index("second")


# ---------------------------------------------------------------------------
# Sidecar files are ignored
# ---------------------------------------------------------------------------

def test_render_ignores_sections_sidecar_files(isolated_paths):
    runs_dir = isolated_paths["runs_dir"]
    sidecar = runs_dir / "2099-01-01T03-00-00+00-00.sections.json"
    sidecar.write_text(json.dumps({"Light Sleep": "should not appear"}))

    rendered = _dreams.render_dreams_md_from_runs()

    assert "should not appear" not in rendered


# ---------------------------------------------------------------------------
# Empty runs directory
# ---------------------------------------------------------------------------

def test_render_empty_runs_dir_produces_empty_output(isolated_paths):
    rendered = _dreams.render_dreams_md_from_runs()
    assert rendered == ""
    assert (isolated_paths["dream_dir"] / "DREAMS.md").read_text() == ""
