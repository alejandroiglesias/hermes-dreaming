from __future__ import annotations

"""
dreaming_record_decisions — REM and Deep phase tool.

Records per-candidate decisions (promote, reject, supersedes, skill_candidate)
to decisions.jsonl for audit. Does not mutate durable memory.
"""

from typing import Any

from ..sidecar import append_decisions
from ..state import read as read_state

SCHEMA = {
    "name": "dreaming_record_decisions",
    "description": (
        "Record REM-phase reflections and Deep-phase scoring decisions for each "
        "staged candidate. Does NOT mutate MEMORY.md or USER.md. "
        "Call once after REM reflection with all per-candidate decisions, "
        "and again after Deep scoring with final outcomes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "enum": ["REM", "Deep"],
                "description": "Which phase these decisions come from.",
            },
            "decisions": {
                "type": "array",
                "description": "Per-candidate decision records.",
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_text": {
                            "type": "string",
                            "description": "The candidate text being decided on.",
                        },
                        "candidate_hash": {
                            "type": "string",
                            "description": (
                                "Hash from candidates.jsonl (if known). "
                                "Omit if not available."
                            ),
                        },
                        "decision": {
                            "type": "string",
                            "enum": [
                                "promote",
                                "reject_ephemeral",
                                "reject_redundant",
                                "reject_low_confidence",
                                "reject_sensitive",
                                "reject_verbose",
                                "better_as_skill",
                                "supersedes_memory_entry",
                                "merge_with_existing",
                                "remove_existing",
                                "defer",
                            ],
                            "description": "The decision made for this candidate.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "One sentence explaining the decision.",
                        },
                        "supersedes_entry": {
                            "type": "string",
                            "description": (
                                "Exact substring of the existing MEMORY.md or USER.md "
                                "entry that this candidate supersedes or merges with. "
                                "Required when decision is 'supersedes_memory_entry' "
                                "or 'merge_with_existing'."
                            ),
                        },
                        "canonical_text": {
                            "type": "string",
                            "description": (
                                "Refined, canonical phrasing for the memory entry. "
                                "Provide for 'promote', 'supersedes_memory_entry', "
                                "and 'merge_with_existing' decisions."
                            ),
                        },
                        "score": {
                            "type": "number",
                            "description": "0.0–1.0 composite usefulness score (Deep phase).",
                        },
                        "target": {
                            "type": "string",
                            "enum": ["memory", "user"],
                            "description": "Which file this entry belongs in (Deep phase).",
                        },
                    },
                    "required": ["candidate_text", "decision", "reason"],
                },
            },
            "themes": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "REM only: recurring themes identified across the staged candidates "
                    "and recent sessions. Include 1–5 brief theme labels."
                ),
            },
            "contradictions": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "REM only: contradictions found between candidates and existing "
                    "memory entries. Each item is a one-sentence description."
                ),
            },
        },
        "required": ["phase", "decisions"],
    },
}


def handler(params: dict[str, Any]) -> dict[str, Any]:
    phase = params.get("phase", "REM")
    decisions = params.get("decisions", [])
    themes = params.get("themes", [])
    contradictions = params.get("contradictions", [])

    if not isinstance(decisions, list):
        return {"error": "'decisions' must be a list"}

    state = read_state()
    run_id = state.get("current_run", {}).get("started_at", "unknown")

    extra = {}
    if themes:
        extra["themes"] = themes
    if contradictions:
        extra["contradictions"] = contradictions

    append_decisions(
        [{**d, "phase": phase, **extra} for d in decisions],
        run_id=run_id,
    )

    by_decision: dict[str, int] = {}
    for d in decisions:
        key = d.get("decision", "unknown")
        by_decision[key] = by_decision.get(key, 0) + 1

    return {
        "recorded": len(decisions),
        "phase": phase,
        "themes_noted": len(themes),
        "contradictions_noted": len(contradictions),
        "by_decision": by_decision,
    }
