from __future__ import annotations

"""
DREAMS.md writer — the human-readable audit diary for Dreaming runs.

Format (brief §14):

  ---

  ## YYYY-MM-DD HH:MM — Dreaming run [dry-run]

  ### Light Sleep
  ...

  ### Deep Sleep
  ...

  ### REM Sleep
  ...

  ### Summary
  ...

Each run appends a horizontal ruler, dated header, and its sections.
"""

import json
import re
from datetime import datetime

from .paths import DREAMS_MD, RUNS_DIR

_KNOWN_SECTIONS = ("Light Sleep", "Deep Sleep", "REM Sleep", "Summary")
_RUN_SEPARATOR = "---"
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$")


def _now_header(dry_run: bool) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    suffix = " — dry-run" if dry_run else ""
    return _format_run_header(ts, suffix)


def _format_run_header(header_ts: str, suffix: str = "") -> str:
    return f"\n{_RUN_SEPARATOR}\n\n## {header_ts} — Dreaming run{suffix}\n"


def _is_run_header(line: str) -> bool:
    return line.lstrip().startswith("## ") and "— Dreaming run" in line


def _is_run_separator(line: str) -> bool:
    return line.strip() == _RUN_SEPARATOR


def _run_header_after_separator(lines: list[str], index: int) -> bool:
    if not _is_run_separator(lines[index]):
        return False
    j = index + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    return j < len(lines) and _is_run_header(lines[j])


def _is_run_start(lines: list[str], index: int) -> bool:
    return _is_run_header(lines[index]) or _run_header_after_separator(lines, index)


def _redundant_heading_names(section: str) -> tuple[str, ...]:
    if section == "Summary":
        return ("summary", "dreaming summary")
    return (section.lower(),)


def _is_redundant_section_heading(section: str, line: str) -> bool:
    match = _HEADING_RE.match(line)
    if not match:
        return False

    title = re.sub(r"\s+", " ", match.group(1).strip().lower())
    for name in _redundant_heading_names(section):
        if title == name:
            return True
        if title.startswith(name):
            suffix = title[len(name):].strip()
            if suffix and suffix[0] in "—-–:([+|":
                return True
    return False


def _is_known_phase_heading(line: str) -> bool:
    for section in _KNOWN_SECTIONS:
        if _is_redundant_section_heading(section, line):
            return True
    return False


def normalize_section_markdown(section: str, markdown: str) -> str:
    """Remove redundant phase titles from agent-supplied markdown."""
    lines = markdown.strip().splitlines()

    while lines:
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines or not _is_redundant_section_heading(section, lines[0]):
            break
        lines.pop(0)

    lines = [line for line in lines if not _is_known_phase_heading(line)]
    return "\n".join(lines).strip()


def _record_created_value(rec: dict, path) -> str:
    for key in ("created_at", "id", "run_id", "ended_at"):
        value = rec.get(key)
        if value and value != "unknown":
            return str(value)
    if path.stem != "unknown":
        return path.stem
    return ""


def _strip_stale_stubs(text: str) -> str:
    """Remove run headers that have no section content (### ...) following them."""
    lines = text.splitlines(keepends=True)
    result = []
    i = 0
    while i < len(lines):
        if _is_run_start(lines, i):
            start = i
            header_index = i
            if _run_header_after_separator(lines, i):
                header_index = i + 1
                while header_index < len(lines) and not lines[header_index].strip():
                    header_index += 1

            j = header_index + 1
            body: list[str] = []
            while j < len(lines) and not _is_run_start(lines, j):
                body.append(lines[j])
                j += 1
            if any(l.lstrip().startswith("###") for l in body):
                result.extend(lines[start:j])
            i = j
        else:
            result.append(lines[i])
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


def write_section(section: str, markdown: str) -> str:
    """Append a named section (Light Sleep / Deep Sleep / REM Sleep / Summary)."""
    if section not in _KNOWN_SECTIONS:
        raise ValueError(
            f"Unknown section {section!r}. Use one of: {', '.join(_KNOWN_SECTIONS)}"
        )
    body = normalize_section_markdown(section, markdown)
    block = f"\n### {section}\n{body}\n"
    with DREAMS_MD.open("a", encoding="utf-8") as f:
        f.write(block)
    return body


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
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        created = _record_created_value(rec, path)
        if created:
            records.append((created, path, rec))

    records.sort(key=lambda item: item[0])

    chunks: list[str] = []
    for created, _path, rec in records:
        header_ts = created
        try:
            dt = datetime.fromisoformat(created)
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            header_ts = dt.strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            pass
        suffix = " — dry-run" if rec.get("dry_run") else ""
        status = rec.get("status", "")
        if not status and rec.get("success") is True:
            status = "completed"
        status_suffix = "" if status in ("", "completed") else f" — {status}"
        chunks.append(_format_run_header(header_ts, f"{suffix}{status_suffix}"))

        sections = rec.get("sections") or {}
        if not sections:
            notes = rec.get("notes")
            if not notes and isinstance(rec.get("summary"), dict):
                notes = rec["summary"].get("notes")
            if notes:
                sections = {"Summary": notes}
        for name in _KNOWN_SECTIONS:
            body = sections.get(name)
            if not body:
                continue
            chunks.append(f"\n### {name}\n{normalize_section_markdown(name, body)}\n")

        err = rec.get("error")
        if err:
            err_type = err.get("type", "unknown") if isinstance(err, dict) else "unknown"
            err_msg = err.get("message", "") if isinstance(err, dict) else str(err)
            chunks.append(f"\n### Error\n- {err_type} — {err_msg}\n")

    rendered = "".join(chunks)
    DREAMS_MD.parent.mkdir(parents=True, exist_ok=True)
    DREAMS_MD.write_text(rendered, encoding="utf-8")
    return rendered
