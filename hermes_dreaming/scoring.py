from __future__ import annotations

"""
Scoring thresholds and run-level limits for the Deep phase (brief §12).

The agent computes scores using its own LLM judgement.
This module is the authoritative source of threshold values that:
  - the orchestration prompt quotes verbatim, and
  - apply_memory_op enforces as hard gates.
"""

from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Per-operation score thresholds (brief §12.2)
# ---------------------------------------------------------------------------

ADD_MIN_SCORE: float = 0.88
REPLACE_MIN_SCORE: float = 0.80
REPLACE_MIN_SUPERSESSION_CONFIDENCE: float = 0.75
REMOVE_MIN_CONFIDENCE: float = 0.85
MERGE_MIN_OVERLAP_CONFIDENCE: float = 0.80

# ---------------------------------------------------------------------------
# Run-level hard limits (brief §12.3)
# ---------------------------------------------------------------------------

DEFAULT_MAX_CHANGES_PER_RUN: int = 3
DEFAULT_MAX_ADDS_PER_RUN: int = 1
DEFAULT_MAX_NEW_CHARS_PER_RUN: int = 250

Op = Literal["add", "replace", "remove"]


@dataclass
class ProposedOp:
    op: Op
    target: Literal["memory", "user"]
    old_text: str | None
    new_text: str | None
    reason: str
    sources: list[str]
    score: float
    supersession_confidence: float = 0.0


@dataclass
class ValidationResult:
    ok: bool
    error: str = ""


def validate_op(op: ProposedOp) -> ValidationResult:
    """
    Check whether a proposed operation passes score thresholds.

    Does NOT enforce run-level limits (those are tracked in apply_memory_op).
    """
    if op.op == "add":
        if op.new_text is None:
            return ValidationResult(ok=False, error="add requires new_text")
        if op.score < ADD_MIN_SCORE:
            return ValidationResult(
                ok=False,
                error=f"add score {op.score:.2f} < threshold {ADD_MIN_SCORE}",
            )

    elif op.op == "replace":
        if op.old_text is None or op.new_text is None:
            return ValidationResult(ok=False, error="replace requires old_text and new_text")
        if op.score < REPLACE_MIN_SCORE:
            return ValidationResult(
                ok=False,
                error=f"replace score {op.score:.2f} < threshold {REPLACE_MIN_SCORE}",
            )
        if op.supersession_confidence < REPLACE_MIN_SUPERSESSION_CONFIDENCE:
            return ValidationResult(
                ok=False,
                error=(
                    f"replace supersession_confidence {op.supersession_confidence:.2f} "
                    f"< threshold {REPLACE_MIN_SUPERSESSION_CONFIDENCE}"
                ),
            )

    elif op.op == "remove":
        if op.old_text is None:
            return ValidationResult(ok=False, error="remove requires old_text")
        if op.supersession_confidence < REMOVE_MIN_CONFIDENCE:
            return ValidationResult(
                ok=False,
                error=(
                    f"remove confidence {op.supersession_confidence:.2f} "
                    f"< threshold {REMOVE_MIN_CONFIDENCE}"
                ),
            )

    else:
        return ValidationResult(ok=False, error=f"unknown op: {op.op!r}")

    return ValidationResult(ok=True)


def thresholds_for_prompt() -> str:
    """Return a Markdown table of thresholds for inclusion in the orchestration prompt."""
    return f"""\
| Operation | Score threshold | Extra gate |
|---|---|---|
| `add` | ≥ {ADD_MIN_SCORE} | — |
| `replace` | ≥ {REPLACE_MIN_SCORE} | supersession_confidence ≥ {REPLACE_MIN_SUPERSESSION_CONFIDENCE} |
| `remove` | — | supersession_confidence ≥ {REMOVE_MIN_CONFIDENCE} |
| `merge` (as replace) | ≥ {REPLACE_MIN_SCORE} | overlap_confidence ≥ {MERGE_MIN_OVERLAP_CONFIDENCE} |

Run-level hard limits:
- max_changes_per_run: {DEFAULT_MAX_CHANGES_PER_RUN}
- max_adds_per_run: {DEFAULT_MAX_ADDS_PER_RUN}
- max_new_chars_per_run: {DEFAULT_MAX_NEW_CHARS_PER_RUN}"""
