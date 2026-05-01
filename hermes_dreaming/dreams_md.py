from __future__ import annotations

"""
DREAMS.md writer — the human-readable audit diary for Dreaming runs.

Format (brief §14):

  ## YYYY-MM-DD HH:MM — Dreaming run [dry-run]

  ### Light Sleep
  ...

  ### REM Sleep
  ...

  ### Deep Sleep
  ...

  ### Summary
  ...

Each run appends a dated header and its sections.
"""

from datetime import datetime, timezone

from .paths import DREAMS_MD

_KNOWN_SECTIONS = ("Light Sleep", "REM Sleep", "Deep Sleep", "Summary")


def _now_header(dry_run: bool) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    suffix = " — dry-run" if dry_run else ""
    return f"\n## {ts} — Dreaming run{suffix}\n"


def open_run(dry_run: bool = False) -> None:
    """Append the dated run header to DREAMS.md."""
    header = _now_header(dry_run)
    with DREAMS_MD.open("a", encoding="utf-8") as f:
        f.write(header)


def write_section(section: str, markdown: str) -> None:
    """Append a named section (Light Sleep / REM Sleep / Deep Sleep / Summary)."""
    if section not in _KNOWN_SECTIONS:
        raise ValueError(
            f"Unknown section {section!r}. Use one of: {', '.join(_KNOWN_SECTIONS)}"
        )
    block = f"\n### {section}\n{markdown.strip()}\n"
    with DREAMS_MD.open("a", encoding="utf-8") as f:
        f.write(block)


def write_summary(
    changes_applied: int,
    candidates_staged: int,
    candidates_rejected: int,
    dry_run: bool = False,
) -> None:
    """Write a standardised Summary section."""
    mode = "dry-run — no memory changes applied" if dry_run else f"{changes_applied} durable memory change(s) applied"
    lines = [
        f"- Mode: {mode}",
        f"- Candidates staged: {candidates_staged}",
        f"- Candidates rejected: {candidates_rejected}",
    ]
    write_section("Summary", "\n".join(lines))
