"""
Tests for commands/run.py and commands/review.py instruction pass-through.

Verifies that `handle(instructions)` forwards the string to `orchestration.build`
as the `instructions` kwarg, without testing the full build pipeline.
"""
from __future__ import annotations

from unittest.mock import patch, call

import hermes_dreaming.commands.run as _run_cmd
import hermes_dreaming.commands.review as _review_cmd


def test_run_handle_passes_instructions_to_build():
    with patch("hermes_dreaming.commands.run.build", return_value="prompt") as mock_build:
        result = _run_cmd.handle("focus on coding-style preferences")
    mock_build.assert_called_once_with(dry_run=False, instructions="focus on coding-style preferences")
    assert result == "prompt"


def test_run_handle_passes_empty_string_by_default():
    with patch("hermes_dreaming.commands.run.build", return_value="prompt") as mock_build:
        result = _run_cmd.handle()
    mock_build.assert_called_once_with(dry_run=False, instructions="")
    assert result == "prompt"


def test_review_handle_passes_instructions_to_build():
    with patch("hermes_dreaming.commands.review.build", return_value="prompt") as mock_build:
        result = _review_cmd.handle("ignore debugging notes")
    mock_build.assert_called_once_with(dry_run=True, instructions="ignore debugging notes")
    assert result == "prompt"


def test_review_handle_passes_empty_string_by_default():
    with patch("hermes_dreaming.commands.review.build", return_value="prompt") as mock_build:
        result = _review_cmd.handle()
    mock_build.assert_called_once_with(dry_run=True, instructions="")
    assert result == "prompt"
