from __future__ import annotations

from pathlib import Path

from ..paths import CANDIDATES_JSONL, PROMOTIONS_JSONL, DREAMS_MD
from ..state import read as read_state
from ..memory_io import read_both


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def handle(args: str = "") -> str:
    state = read_state()

    last_run = state.get("last_run", "never")
    last_ok = state.get("last_successful_run", "never")
    current = state.get("current_run")
    summary = state.get("last_summary", {})

    candidates = _count_lines(CANDIDATES_JSONL)
    promotions = _count_lines(PROMOTIONS_JSONL)

    files = read_both()

    lines = [
        "## Dreaming status",
        "",
        f"Last run:            {last_run}",
        f"Last successful run: {last_ok}",
    ]

    if current:
        mode = "dry-run" if current.get("dry_run") else "live"
        lines.append(f"Current run:         in progress ({mode}, started {current['started_at']})")

    lines += [
        "",
        f"Staged candidates:   {candidates}",
        f"Total promotions:    {promotions}",
    ]

    if summary:
        changes = summary.get("changes_applied", 0)
        rejected = summary.get("candidates_rejected", 0)
        lines.append(f"Last run changes:    {changes} applied, {rejected} rejected")

    lines += ["", "Memory usage:"]
    for mf in files.values():
        lines.append(f"  {mf.summary_line()}")

    if DREAMS_MD.exists():
        lines.append(f"\nDREAMS.md: {DREAMS_MD}")

    return "\n".join(lines)
