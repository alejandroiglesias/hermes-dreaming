"""Tests for hermes_dreaming.memory_io read/write helpers."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from hermes_dreaming.memory_io import (
    MutationResult,
    _find_line,
    _parse_entries,
    apply_add,
    apply_remove,
    apply_replace,
    read,
)


@pytest.fixture()
def tmp_md(tmp_path):
    p = tmp_path / "MEMORY.md"
    p.write_text("- Entry one.\n- Entry two.\n- Entry three.\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _parse_entries
# ---------------------------------------------------------------------------

def test_parse_entries_basic():
    text = "- Entry one.\n- Entry two.\n"
    entries = _parse_entries(text)
    assert entries == ["- Entry one.", "- Entry two."]


def test_parse_entries_strips_hints():
    text = "<!--drm:id=abc;s=0.91;st=active-->- Entry with hint.\n"
    entries = _parse_entries(text)
    assert len(entries) == 1
    assert "hint" in entries[0]
    assert "<!--drm" not in entries[0]


def test_parse_entries_ignores_non_bullet_lines():
    text = "# Header\n- Bullet.\nNormal text.\n"
    entries = _parse_entries(text)
    assert entries == ["- Bullet."]


# ---------------------------------------------------------------------------
# apply_add
# ---------------------------------------------------------------------------

def test_apply_add_appends_new_line(tmp_md):
    result = apply_add(tmp_md, "- New entry.")
    assert result.ok
    assert "- New entry." in result.new_text
    assert result.char_delta > 0
    assert tmp_md.read_text(encoding="utf-8").endswith("- New entry.\n")


def test_apply_add_creates_file_if_missing(tmp_path):
    p = tmp_path / "NEW.md"
    result = apply_add(p, "- First entry.")
    assert result.ok
    assert p.exists()
    assert "- First entry." in p.read_text(encoding="utf-8")


def test_apply_add_with_hint_prefix(tmp_md):
    result = apply_add(tmp_md, "- Hinted entry.", hint_prefix="<!--drm:id=abc;s=0.92;st=active-->")
    assert result.ok
    content = tmp_md.read_text(encoding="utf-8")
    assert "<!--drm:id=abc" in content
    assert "- Hinted entry." in content


def test_apply_add_separator_when_no_trailing_newline(tmp_path):
    p = tmp_path / "MEM.md"
    p.write_text("- Existing.", encoding="utf-8")  # no trailing newline
    result = apply_add(p, "- Added.")
    assert result.ok
    content = p.read_text(encoding="utf-8")
    assert content == "- Existing.\n- Added.\n"


# ---------------------------------------------------------------------------
# apply_replace
# ---------------------------------------------------------------------------

def test_apply_replace_replaces_matching_line(tmp_md):
    result = apply_replace(tmp_md, "Entry one", "- Entry one UPDATED.")
    assert result.ok
    content = tmp_md.read_text(encoding="utf-8")
    assert "- Entry one UPDATED." in content
    assert "Entry one.\n" not in content


def test_apply_replace_returns_error_when_not_found(tmp_md):
    result = apply_replace(tmp_md, "nonexistent substring", "- Replacement.")
    assert not result.ok
    assert "not found" in result.error


def test_apply_replace_char_delta_is_correct(tmp_md):
    old_text = tmp_md.read_text(encoding="utf-8")
    result = apply_replace(tmp_md, "Entry two", "- Entry two REPLACED.")
    new_text = tmp_md.read_text(encoding="utf-8")
    assert result.char_delta == len(new_text) - len(old_text)


def test_apply_replace_with_hint_prefix(tmp_md):
    result = apply_replace(tmp_md, "Entry three", "- Entry three updated.", hint_prefix="<!--drm:id=xyz;s=0.85;st=active-->")
    assert result.ok
    content = tmp_md.read_text(encoding="utf-8")
    assert "<!--drm:id=xyz" in content


# ---------------------------------------------------------------------------
# apply_remove
# ---------------------------------------------------------------------------

def test_apply_remove_removes_matching_line(tmp_md):
    result = apply_remove(tmp_md, "Entry two")
    assert result.ok
    content = tmp_md.read_text(encoding="utf-8")
    assert "Entry two" not in content
    assert "Entry one" in content
    assert "Entry three" in content


def test_apply_remove_returns_error_when_not_found(tmp_md):
    result = apply_remove(tmp_md, "this does not exist")
    assert not result.ok
    assert "not found" in result.error


def test_apply_remove_char_delta_is_negative(tmp_md):
    result = apply_remove(tmp_md, "Entry one")
    assert result.ok
    assert result.char_delta < 0


# ---------------------------------------------------------------------------
# _find_line with hint-stripped content
# ---------------------------------------------------------------------------

def test_find_line_matches_through_hint():
    lines = ["<!--drm:id=abc;s=0.90;st=active-->- Entry with hint."]
    idx = _find_line(lines, "Entry with hint")
    assert idx == 0


def test_find_line_returns_minus_one_when_missing():
    lines = ["- Entry one.", "- Entry two."]
    assert _find_line(lines, "Entry three") == -1
