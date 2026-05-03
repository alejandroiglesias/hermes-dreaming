"""Tests for hermes_dreaming.orchestration prompt content."""
from __future__ import annotations

import pytest

from hermes_dreaming.orchestration import _rem_instructions
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
