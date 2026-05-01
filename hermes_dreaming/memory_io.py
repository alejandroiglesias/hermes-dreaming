from __future__ import annotations

"""
Read, parse, and write Hermes durable memory files (MEMORY.md, USER.md).

Write helpers are used exclusively by tools/apply_memory_op.py, which
handles the filelock, backup, run-limit tracking, and sidecar logging.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from .paths import MEMORY_MD, USER_MD, MEMORY_MD_LIMIT, USER_MD_LIMIT


class MemoryFile(NamedTuple):
    target: str          # "memory" or "user"
    path: Path
    raw: str             # full file text
    entries: list[str]   # parsed bullet entries
    char_count: int
    char_limit: int

    @property
    def free(self) -> int:
        return max(0, self.char_limit - self.char_count)

    @property
    def usage_pct(self) -> float:
        return round(100 * self.char_count / self.char_limit, 1)

    @property
    def near_capacity(self) -> bool:
        return self.usage_pct >= 80

    def summary_line(self) -> str:
        return (
            f"{self.target.upper()}.md  "
            f"{self.char_count}/{self.char_limit} chars "
            f"({self.usage_pct}%)  —  {len(self.entries)} entries"
        )


def _parse_entries(text: str) -> list[str]:
    """Extract bullet-list lines from a memory file."""
    entries = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-") or stripped == "-":
            continue
        entries.append(stripped)
    return entries


def read(target: str) -> MemoryFile:
    """Read and parse a memory file. target is 'memory' or 'user'."""
    if target == "memory":
        path, limit = MEMORY_MD, MEMORY_MD_LIMIT
    elif target == "user":
        path, limit = USER_MD, USER_MD_LIMIT
    else:
        raise ValueError(f"Unknown target: {target!r}. Use 'memory' or 'user'.")

    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    return MemoryFile(
        target=target,
        path=path,
        raw=raw,
        entries=_parse_entries(raw),
        char_count=len(raw),
        char_limit=limit,
    )


def read_both() -> dict[str, MemoryFile]:
    """Return {'memory': MemoryFile, 'user': MemoryFile}."""
    return {"memory": read("memory"), "user": read("user")}


@dataclass
class MutationResult:
    ok: bool
    new_text: str = ""   # full file text after mutation
    char_delta: int = 0  # chars added (negative = removed)
    error: str = ""


def _write_atomic(path: Path, content: str) -> None:
    """Write *content* to *path* via a temp file + os.replace for atomicity."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".drm_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _find_line(lines: list[str], substring: str) -> int:
    """Return index of first line containing *substring*, or -1."""
    for i, line in enumerate(lines):
        if substring in line:
            return i
    return -1


def apply_add(path: Path, new_text: str) -> MutationResult:
    """Append *new_text* as a new bullet line."""
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    separator = "\n" if raw and not raw.endswith("\n") else ""
    updated = raw + separator + new_text + "\n"
    _write_atomic(path, updated)
    return MutationResult(ok=True, new_text=updated, char_delta=len(updated) - len(raw))


def apply_replace(path: Path, old_text: str, new_text: str) -> MutationResult:
    """Replace the line containing *old_text* with *new_text*."""
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = raw.splitlines(keepends=True)
    idx = _find_line([l.rstrip("\n") for l in lines], old_text)
    if idx == -1:
        return MutationResult(
            ok=False,
            error=f"old_text not found in {path.name}: {old_text!r}",
        )
    lines[idx] = f"{new_text}\n"
    updated = "".join(lines)
    _write_atomic(path, updated)
    return MutationResult(ok=True, new_text=updated, char_delta=len(updated) - len(raw))


def apply_remove(path: Path, old_text: str) -> MutationResult:
    """Remove the line containing *old_text*."""
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = raw.splitlines(keepends=True)
    idx = _find_line([l.rstrip("\n") for l in lines], old_text)
    if idx == -1:
        return MutationResult(
            ok=False,
            error=f"old_text not found in {path.name}: {old_text!r}",
        )
    removed_len = len(lines[idx])
    del lines[idx]
    updated = "".join(lines)
    _write_atomic(path, updated)
    return MutationResult(ok=True, new_text=updated, char_delta=-removed_len)


def format_for_prompt(mf: MemoryFile) -> str:
    """Render a MemoryFile for inclusion in an orchestration prompt."""
    header = (
        f"### {mf.target.upper()}.md  "
        f"[{mf.char_count}/{mf.char_limit} chars, {mf.usage_pct}% used"
        + (", NEAR CAPACITY" if mf.near_capacity else "")
        + "]\n"
    )
    if not mf.raw.strip():
        return header + "(empty)\n"
    return header + mf.raw + "\n"
