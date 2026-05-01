from __future__ import annotations

"""
dreaming_write_dream_report — append a section to DREAMS.md.

Call once per phase with the phase name and the markdown content
for that phase's section.
"""

from typing import Any

from ..dreams_md import write_section

SCHEMA = {
    "name": "dreaming_write_dream_report",
    "description": (
        "Append a section to the DREAMS.md audit diary. "
        "Call once per phase: after Light, after REM, after Deep, and for the Summary. "
        "The section name must be one of: 'Light Sleep', 'REM Sleep', 'Deep Sleep', 'Summary'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "enum": ["Light Sleep", "REM Sleep", "Deep Sleep", "Summary"],
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


def handler(params: dict[str, Any]) -> dict[str, Any]:
    section = params.get("section", "")
    markdown = params.get("markdown", "")

    if not section:
        return {"error": "'section' is required"}
    if not markdown:
        return {"error": "'markdown' is required"}

    try:
        write_section(section, markdown)
        return {"written": True, "section": section}
    except ValueError as e:
        return {"error": str(e)}
