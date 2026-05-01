"""Tests for hermes_dreaming.scoring threshold enforcement."""
from __future__ import annotations

import pytest

from hermes_dreaming.scoring import (
    ADD_MIN_SCORE,
    REMOVE_MIN_CONFIDENCE,
    REPLACE_MIN_SCORE,
    REPLACE_MIN_SUPERSESSION_CONFIDENCE,
    ProposedOp,
    validate_op,
)


def _make_op(**kwargs) -> ProposedOp:
    defaults = dict(
        op="add",
        target="memory",
        old_text=None,
        new_text="- New entry.",
        reason="test",
        sources=["sess-1"],
        score=0.90,
        supersession_confidence=0.0,
    )
    defaults.update(kwargs)
    return ProposedOp(**defaults)


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_passes_above_threshold():
    op = _make_op(op="add", score=ADD_MIN_SCORE)
    assert validate_op(op).ok


def test_add_fails_below_threshold():
    op = _make_op(op="add", score=ADD_MIN_SCORE - 0.01)
    result = validate_op(op)
    assert not result.ok
    assert "add score" in result.error


def test_add_requires_new_text():
    op = _make_op(op="add", new_text=None)
    result = validate_op(op)
    assert not result.ok
    assert "new_text" in result.error


# ---------------------------------------------------------------------------
# replace
# ---------------------------------------------------------------------------

def test_replace_passes_with_valid_inputs():
    op = _make_op(
        op="replace",
        old_text="- Old entry.",
        score=REPLACE_MIN_SCORE,
        supersession_confidence=REPLACE_MIN_SUPERSESSION_CONFIDENCE,
    )
    assert validate_op(op).ok


def test_replace_fails_low_score():
    op = _make_op(
        op="replace",
        old_text="- Old entry.",
        score=REPLACE_MIN_SCORE - 0.01,
        supersession_confidence=REPLACE_MIN_SUPERSESSION_CONFIDENCE,
    )
    assert not validate_op(op).ok


def test_replace_fails_low_supersession_confidence():
    op = _make_op(
        op="replace",
        old_text="- Old entry.",
        score=REPLACE_MIN_SCORE,
        supersession_confidence=REPLACE_MIN_SUPERSESSION_CONFIDENCE - 0.01,
    )
    result = validate_op(op)
    assert not result.ok
    assert "supersession_confidence" in result.error


def test_replace_requires_old_and_new_text():
    op = _make_op(op="replace", old_text=None, score=0.85, supersession_confidence=0.80)
    assert not validate_op(op).ok

    op2 = _make_op(op="replace", old_text="- Old.", new_text=None, score=0.85, supersession_confidence=0.80)
    assert not validate_op(op2).ok


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

def test_remove_passes_with_high_confidence():
    op = _make_op(op="remove", old_text="- Old entry.", score=0.0, supersession_confidence=REMOVE_MIN_CONFIDENCE)
    assert validate_op(op).ok


def test_remove_fails_low_confidence():
    op = _make_op(op="remove", old_text="- Old entry.", score=0.0, supersession_confidence=REMOVE_MIN_CONFIDENCE - 0.01)
    assert not validate_op(op).ok


def test_remove_requires_old_text():
    op = _make_op(op="remove", old_text=None, supersession_confidence=0.90)
    assert not validate_op(op).ok


# ---------------------------------------------------------------------------
# unknown op
# ---------------------------------------------------------------------------

def test_unknown_op_returns_error():
    op = _make_op(op="upsert")  # type: ignore[arg-type]
    result = validate_op(op)
    assert not result.ok
    assert "unknown" in result.error
