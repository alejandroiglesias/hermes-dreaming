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

import json
from datetime import datetime, timezone

from .paths import DREAMS_MD, RUNS_DIR

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


def render_dreams_md_from_runs() -> str:
    """Rebuild DREAMS.md from canonical run records.

    Run records (~/.hermes/dreaming/runs/*.json) are the source of truth.
    This function reproduces the diary that is otherwise appended live,
    enabling reconstruction if DREAMS.md is lost or out of sync.

    Skips sidecar files (*.sections.json). Records are sorted by created_at.
    """
    if not RUNS_DIR.exists():
        DREAMS_MD.write_text("", encoding="utf-8")
        return ""

    records = []
    for path in RUNS_DIR.iterdir():
        if not path.is_file() or path.suffix != ".json":
            continue
        if path.name.endswith(".sections.json"):
            continue
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue

    records.sort(key=lambda r: r.get("created_at") or r.get("id") or "")

    chunks: list[str] = []
    for rec in records:
        created = rec.get("created_at") or rec.get("id") or ""
        header_ts = created
        try:
            dt = datetime.fromisoformat(created)
            header_ts = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except (TypeError, ValueError):
            pass
        suffix = " — dry-run" if rec.get("dry_run") else ""
        status = rec.get("status", "")
        status_suffix = "" if status == "completed" else f" — {status}"
        chunks.append(f"\n## {header_ts} — Dreaming run{suffix}{status_suffix}\n")

        sections = rec.get("sections") or {}
        for name in _KNOWN_SECTIONS:
            body = sections.get(name)
            if not body:
                continue
            chunks.append(f"\n### {name}\n{body.strip()}\n")

        err = rec.get("error")
        if err:
            err_type = err.get("type", "unknown") if isinstance(err, dict) else "unknown"
            err_msg = err.get("message", "") if isinstance(err, dict) else str(err)
            chunks.append(f"\n### Error\n- {err_type} — {err_msg}\n")

    rendered = "".join(chunks)
    DREAMS_MD.parent.mkdir(parents=True, exist_ok=True)
    DREAMS_MD.write_text(rendered, encoding="utf-8")
    return rendered
