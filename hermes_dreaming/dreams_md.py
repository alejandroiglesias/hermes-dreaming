from __future__ import annotations

"""
DREAMS.md writer — the human-readable audit diary for Dreaming runs.

Format (brief §14):

  ## YYYY-MM-DD HH:MM — Dreaming run [dry-run]

  ### Light Sleep
  ...

  ### Deep Sleep
  ...

  ### REM Sleep
  ...

  ### Summary
  ...

Each run appends a dated header and its sections.
"""

from datetime import datetime, timezone

from .paths import DREAMS_MD

_KNOWN_SECTIONS = ("Light Sleep", "Deep Sleep", "REM Sleep", "Summary")


def _now_header(dry_run: bool) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    suffix = " — dry-run" if dry_run else ""
    return f"\n## {ts} — Dreaming run{suffix}\n"


def _strip_stale_stubs(text: str) -> str:
    """Remove run headers that have no section content (### ...) following them."""
    lines = text.splitlines(keepends=True)
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("## ") and "— Dreaming run" in line:
            j = i + 1
            body: list[str] = []
            while j < len(lines) and not (
                lines[j].lstrip().startswith("## ") and "— Dreaming run" in lines[j]
            ):
                body.append(lines[j])
                j += 1
            if any(l.startswith("###") for l in body):
                result.append(line)
                result.extend(body)
            i = j
        else:
            result.append(line)
            i += 1
    return "".join(result)


def open_run(dry_run: bool = False) -> None:
    """Append the dated run header to DREAMS.md, stripping any prior stale stubs."""
    if DREAMS_MD.exists():
        text = DREAMS_MD.read_text(encoding="utf-8")
        cleaned = _strip_stale_stubs(text)
        if cleaned != text:
            DREAMS_MD.write_text(cleaned, encoding="utf-8")
    header = _now_header(dry_run)
    with DREAMS_MD.open("a", encoding="utf-8") as f:
        f.write(header)


def write_section(section: str, markdown: str) -> None:
    """Append a named section (Light Sleep / Deep Sleep / REM Sleep / Summary)."""
    if section not in _KNOWN_SECTIONS:
        raise ValueError(
            f"Unknown section {section!r}. Use one of: {', '.join(_KNOWN_SECTIONS)}"
        )
    # Strip a leading header line if the agent included one (e.g. "## Light Sleep")
    body = markdown.strip()
    first, _, rest = body.partition("\n")
    if first.lstrip("#").strip().lower() == section.lower():
        body = rest.strip()
    block = f"\n### {section}\n{body}\n"
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
