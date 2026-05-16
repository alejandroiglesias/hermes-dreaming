from __future__ import annotations

"""
dreaming_write_dream_report — append a section to DREAMS.md.

Call once per phase with the phase name and the markdown content
for that phase's section. The section is also captured into the
current run record so DREAMS.md can be regenerated from runs/.
"""

from typing import Any

from ..dreams_md import write_section
from ..state import append_section, read as read_state

SCHEMA = {
    "name": "dreaming_write_dream_report",
    "description": (
        "Append a section to the DREAMS.md audit diary. "
        "Call once per phase: after Light, after Deep, after REM, and for the Summary. "
        "The section name must be one of: 'Light Sleep', 'Deep Sleep', 'REM Sleep', 'Summary'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "enum": ["Light Sleep", "Deep Sleep", "REM Sleep", "Summary"],
                "description": "Which section of the dream report to write.",
            },
            "markdown": {
                "type": "string",
                "description": "Markdown content for this section.",
            },
        },
        "required": ["section", "markdown"],
    },
}


def handler(params: dict[str, Any], **_) -> dict[str, Any]:
    section = params.get("section", "")
    markdown = params.get("markdown", "")

    if not section:
        return {"error": "'section' is required"}
    if not markdown:
        return {"error": "'markdown' is required"}

    try:
        write_section(section, markdown)
    except ValueError as e:
        return {"error": str(e)}

    state = read_state()
    run_ts = state.get("current_run", {}).get("started_at")
    if run_ts:
        append_section(run_ts, section, markdown)

    return {"written": True, "section": section}
