from __future__ import annotations

"""
dreaming_stage_candidates — Light phase tool.

Appends extracted candidate memories to candidates.jsonl, deduplicating
by content hash so repeated runs do not accumulate duplicates.
"""

from typing import Any

from ..sidecar import append_candidates
from ..state import read as read_state

SCHEMA = {
    "name": "dreaming_stage_candidates",
    "description": (
        "Stage Light-phase candidate memories for later REM reflection and Deep "
        "scoring. Each candidate must include at minimum: type, candidate_text, "
        "confidence, and sources. Duplicates (by content hash) are silently skipped. "
        "Call this once per Light phase with all extracted candidates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "description": "List of candidate memory objects to stage.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": (
                                "Candidate category: user_preference, "
                                "communication_preference, project_fact, "
                                "decision, correction, recurring_workflow, "
                                "supersession_signal, stale_signal, skill_candidate."
                            ),
                        },
                        "candidate_text": {
                            "type": "string",
                            "description": "Compact, standalone memory candidate text.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "0.0–1.0 confidence this is worth staging.",
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Session IDs or turn references that support this candidate.",
                        },
                        "explicitness": {
                            "type": "number",
                            "description": "0.0–1.0; 1.0 = user stated it directly.",
                        },
                        "recurrence_hint": {
                            "type": "string",
                            "description": "How often this pattern appears (once, repeated, explicit).",
                        },
                        "why_future_useful": {
                            "type": "string",
                            "description": "One sentence: why this would improve future responses.",
                        },
                        "why_not_ephemeral": {
                            "type": "string",
                            "description": "One sentence: why this belongs in durable memory, not session history.",
                        },
                    },
                    "required": ["type", "candidate_text", "confidence", "sources"],
                },
            }
        },
        "required": ["candidates"],
    },
}


def handler(params: dict[str, Any]) -> dict[str, Any]:
    candidates = params.get("candidates", [])
    if not isinstance(candidates, list):
        return {"error": "'candidates' must be a list"}

    state = read_state()
    run_id = state.get("current_run", {}).get("started_at", "unknown")

    added, skipped = append_candidates(candidates, run_id=run_id)
    return {
        "staged": added,
        "skipped_duplicates": skipped,
        "total_submitted": len(candidates),
    }
