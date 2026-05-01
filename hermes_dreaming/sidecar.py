from __future__ import annotations

"""
JSONL sidecar file read/write for candidates, decisions, and promotions.

All writes are append-only. Deduplication is by content hash so
repeated runs over the same data don't accumulate duplicates.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import (
    CANDIDATES_JSONL,
    DECISIONS_JSONL,
    PROMOTIONS_JSONL,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(text: str) -> str:
    """Stable 12-char hash for deduplication."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Low-level JSONL helpers
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("sidecar: skipping malformed line in %s", path.name)
    return records


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

def read_candidates() -> list[dict[str, Any]]:
    return _read_jsonl(CANDIDATES_JSONL)


def existing_candidate_hashes() -> set[str]:
    return {r["hash"] for r in read_candidates() if "hash" in r}


def append_candidates(candidates: list[dict[str, Any]], run_id: str) -> tuple[int, int]:
    """
    Append new candidates, skipping duplicates by content hash.

    Returns (added, skipped).
    """
    existing = existing_candidate_hashes()
    added = skipped = 0
    for cand in candidates:
        text = cand.get("candidate_text", "") or cand.get("text", "")
        h = _content_hash(text)
        if h in existing:
            skipped += 1
            continue
        record = {
            "hash": h,
            "run_id": run_id,
            "staged_at": _now_iso(),
            **cand,
        }
        _append_jsonl(CANDIDATES_JSONL, record)
        existing.add(h)
        added += 1
    return added, skipped


# ---------------------------------------------------------------------------
# Decisions (REM/Deep rejections + proposals)
# ---------------------------------------------------------------------------

def append_decisions(decisions: list[dict[str, Any]], run_id: str) -> None:
    for decision in decisions:
        record = {"run_id": run_id, "decided_at": _now_iso(), **decision}
        _append_jsonl(DECISIONS_JSONL, record)


# ---------------------------------------------------------------------------
# Promotions (applied memory operations)
# ---------------------------------------------------------------------------

def read_promotions() -> list[dict[str, Any]]:
    return _read_jsonl(PROMOTIONS_JSONL)


def existing_promotion_hashes() -> set[str]:
    return {r["hash"] for r in read_promotions() if "hash" in r}


def append_promotion(record: dict[str, Any]) -> None:
    _append_jsonl(PROMOTIONS_JSONL, record)


