"""Tests for hermes_dreaming.orchestration prompt content."""
from __future__ import annotations

import pytest

import hermes_dreaming.config as _config
import hermes_dreaming.dreams_md as _dreams
import hermes_dreaming.memory_io as _mio
import hermes_dreaming.paths as _paths
import hermes_dreaming.session_reader as _sr
import hermes_dreaming.sidecar as _sidecar
import hermes_dreaming.state as _state
import hermes_dreaming.orchestration as _orch
from hermes_dreaming.orchestration import _rem_instructions, build
from hermes_dreaming.scoring import (
    ADD_MIN_SCORE,
    REPLACE_MIN_SCORE,
    REPLACE_MIN_SUPERSESSION_CONFIDENCE,
    thresholds_for_prompt,
)

# All scoring dimensions the REM phase must include, with their direction.
EXPECTED_POSITIVE = [
    "future_usefulness",
    "query_diversity",
    "stability",
    "recurrence",
    "recency",
    "explicitness",
    "correction_signal",
    "actionability",
    "compression_value",
]

EXPECTED_NEGATIVE = [
    "character_cost",
    "duplication",
    "volatility",
    "sensitivity",
]


@pytest.fixture()
def rem_prompt():
    return _rem_instructions(dry_run=False, thresholds=thresholds_for_prompt())


@pytest.fixture()
def rem_prompt_dry():
    return _rem_instructions(dry_run=True, thresholds=thresholds_for_prompt())


# ---------------------------------------------------------------------------
# All dimensions are present
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dimension", EXPECTED_POSITIVE)
def test_positive_dimension_present(rem_prompt, dimension):
    assert dimension in rem_prompt, f"Missing positive dimension: {dimension!r}"


@pytest.mark.parametrize("dimension", EXPECTED_NEGATIVE)
def test_negative_dimension_present(rem_prompt, dimension):
    assert dimension in rem_prompt, f"Missing negative dimension: {dimension!r}"


# ---------------------------------------------------------------------------
# Directions are correctly marked
# ---------------------------------------------------------------------------

def test_positive_dimensions_marked_with_plus(rem_prompt):
    for dim in EXPECTED_POSITIVE:
        # The table row must have a '+' on the same line as the dimension name
        for line in rem_prompt.splitlines():
            if dim in line:
                assert "+" in line, (
                    f"Dimension {dim!r} found but not marked as positive (+):\n  {line}"
                )
                break


def test_negative_dimensions_marked_with_minus(rem_prompt):
    for dim in EXPECTED_NEGATIVE:
        for line in rem_prompt.splitlines():
            if dim in line:
                assert "−" in line or "-" in line, (
                    f"Dimension {dim!r} found but not marked as negative (−):\n  {line}"
                )
                break


# ---------------------------------------------------------------------------
# Dry-run vs live mode banner
# ---------------------------------------------------------------------------

def test_live_mode_banner(rem_prompt):
    assert "LIVE MODE" in rem_prompt
    assert "DRY-RUN" not in rem_prompt


def test_dry_run_banner(rem_prompt_dry):
    assert "DRY-RUN" in rem_prompt_dry
    assert "LIVE MODE" not in rem_prompt_dry


# ---------------------------------------------------------------------------
# Threshold gates are included
# ---------------------------------------------------------------------------

def test_add_threshold_in_prompt(rem_prompt):
    assert str(ADD_MIN_SCORE) in rem_prompt


def test_replace_threshold_in_prompt(rem_prompt):
    assert str(REPLACE_MIN_SCORE) in rem_prompt


def test_supersession_confidence_threshold_in_prompt(rem_prompt):
    assert str(REPLACE_MIN_SUPERSESSION_CONFIDENCE) in rem_prompt


# ---------------------------------------------------------------------------
# Operation preference order is stated
# ---------------------------------------------------------------------------

def test_operation_preference_order_present(rem_prompt):
    assert "no-op" in rem_prompt
    assert "replace" in rem_prompt
    assert "remove" in rem_prompt
    assert "add" in rem_prompt


# ---------------------------------------------------------------------------
# Per-run instructions plumbing
# ---------------------------------------------------------------------------

@pytest.fixture()
def isolated_build(tmp_path, monkeypatch):
    """Redirect paths and stub session listing so `build` runs in isolation."""
    mem_dir = tmp_path / "memories"
    mem_dir.mkdir()
    dream_dir = tmp_path / "dreaming"
    dream_dir.mkdir()
    (mem_dir / "MEMORY.md").write_text("", encoding="utf-8")
    (mem_dir / "USER.md").write_text("", encoding="utf-8")

    for mod in (_paths, _state, _sidecar, _mio, _config, _dreams, _orch):
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
        if hasattr(mod, "DREAMS_MD"):
            monkeypatch.setattr(mod, "DREAMS_MD", dream_dir / "DREAMS.md")
        if hasattr(mod, "RUNS_DIR"):
            monkeypatch.setattr(mod, "RUNS_DIR", dream_dir / "runs")
        if hasattr(mod, "CONFIG_FILE"):
            monkeypatch.setattr(mod, "CONFIG_FILE", dream_dir / "config.yaml")

    # Stub session listing so we don't hit ~/.hermes/state.db
    monkeypatch.setattr(_orch, "list_recent", lambda limit=14: [])
    monkeypatch.setattr(_orch, "fmt_sessions", lambda sessions: "")

    # Force config reload per test
    monkeypatch.setattr(_config, "_config", None)

    return {"dream_dir": dream_dir}


def test_build_includes_explicit_instructions_section(isolated_build):
    prompt = build(dry_run=False, instructions="focus on coding-style preferences")
    assert "## Run instructions" in prompt
    assert "focus on coding-style preferences" in prompt


def test_build_omits_instructions_section_when_empty(isolated_build):
    prompt = build(dry_run=False, instructions="")
    assert "## Run instructions" not in prompt


def test_build_falls_back_to_config_instructions(isolated_build, monkeypatch):
    cfg = _config.DreamingConfig(instructions="from config: ignore debugging")
    monkeypatch.setattr(_config, "_config", cfg)
    prompt = build(dry_run=False, instructions="")
    assert "## Run instructions" in prompt
    assert "from config: ignore debugging" in prompt


def test_build_positional_instructions_override_config(isolated_build, monkeypatch):
    cfg = _config.DreamingConfig(instructions="from config")
    monkeypatch.setattr(_config, "_config", cfg)
    prompt = build(dry_run=False, instructions="from caller")
    assert "from caller" in prompt
    assert "from config" not in prompt


def test_build_records_instructions_in_run_record(isolated_build):
    build(dry_run=False, instructions="targeted focus")
    state = _state.read()
    assert state["current_run"]["instructions"] == "targeted focus"
