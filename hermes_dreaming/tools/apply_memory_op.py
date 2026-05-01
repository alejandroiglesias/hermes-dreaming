from __future__ import annotations

"""
dreaming_apply_memory_op — the only tool that may mutate MEMORY.md / USER.md.

Dry-run mode (started via /dreaming review):
  Validates thresholds, records proposal to decisions.jsonl, returns proposed=True.

Live mode (started via /dreaming run):
  1. Acquires filelock.
  2. Creates timestamped backup (once per run).
  3. Enforces run-level limits from config.
  4. Checks idempotence via promotions.jsonl hash.
  5. Validates score thresholds via scoring.validate_op.
  6. Applies mutation atomically (memory_io.apply_*).
  7. Records to promotions.jsonl + optional inline hint.
  8. Updates current_run counters in state.json.
"""

import hashlib
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import filelock

from ..config import load as load_config
from ..memory_io import (
    MutationResult,
    apply_add,
    apply_remove,
    apply_replace,
    read as read_memory,
)
from ..paths import (
    BACKUPS_DIR,
    DREAMING_DIR,
    HERMES_MEMORIES_DIR,
    MEMORY_MD,
    USER_MD,
    ensure_dirs,
)
from ..scoring import ProposedOp, validate_op, thresholds_for_prompt
from ..sidecar import append_decisions, append_promotion, existing_promotion_hashes
from ..state import read as read_state, write as write_state

logger = logging.getLogger(__name__)

SCHEMA = {
    "name": "dreaming_apply_memory_op",
    "description": (
        "Propose or apply a durable memory operation (add / replace / remove). "
        "In dry-run mode (started via /dreaming review) this records the proposal "
        "without touching MEMORY.md or USER.md. "
        "In live mode (started via /dreaming run) this mutates the file after "
        "validating score thresholds and run-level limits."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": ["add", "replace", "remove"],
                "description": "Memory operation to perform.",
            },
            "target": {
                "type": "string",
                "enum": ["memory", "user"],
                "description": "Which file to modify: 'memory' (MEMORY.md) or 'user' (USER.md).",
            },
            "old_text": {
                "type": "string",
                "description": (
                    "Exact substring of the existing entry to replace or remove. "
                    "Required for 'replace' and 'remove'."
                ),
            },
            "new_text": {
                "type": "string",
                "description": (
                    "New memory entry text. Required for 'add' and 'replace'. "
                    "Should be a single compact bullet-list line starting with '- '."
                ),
            },
            "reason": {
                "type": "string",
                "description": "One sentence explaining why this operation is warranted.",
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Session IDs or turn references that ground this operation.",
            },
            "score": {
                "type": "number",
                "description": "Composite future-usefulness score (0.0–1.0) from Deep scoring.",
            },
            "supersession_confidence": {
                "type": "number",
                "description": (
                    "Confidence that old_text is truly superseded or obsolete (0.0–1.0). "
                    "Required for 'replace' and 'remove'."
                ),
            },
        },
        "required": ["op", "target", "reason", "sources", "score"],
    },
}

_LOCK_FILE = DREAMING_DIR / "memory_mutations.lock"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _op_hash(op: str, target: str, old_text: str | None, new_text: str | None) -> str:
    sig = f"{op}:{target}:{old_text or ''}:{new_text or ''}"
    return _content_hash(sig)


def _make_backup(run_ts: str) -> None:
    """Snapshot MEMORY.md and USER.md into backups/<run_ts>/."""
    safe_ts = run_ts.replace(":", "-")
    backup_dir = BACKUPS_DIR / safe_ts
    backup_dir.mkdir(parents=True, exist_ok=True)
    for src in (MEMORY_MD, USER_MD):
        if src.exists():
            shutil.copy2(src, backup_dir / src.name)
        else:
            (backup_dir / src.name).write_text("", encoding="utf-8")
    logger.info("dreaming: backup created at %s", backup_dir)


def _target_path(target: str) -> Path:
    return MEMORY_MD if target == "memory" else USER_MD


def _inline_hint(op_id: str, score: float) -> str:
    return f"<!--drm:id={op_id};s={score:.2f};st=active-->"


def handler(params: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    state = read_state()
    cfg = load_config()
    run_info = state.get("current_run", {})
    dry_run = run_info.get("dry_run", True)
    run_id = run_info.get("started_at", "unknown")

    op_str = params.get("op", "")
    target = params.get("target", "")
    old_text = params.get("old_text") or None
    new_text = params.get("new_text") or None
    reason = params.get("reason", "")
    sources = params.get("sources", [])
    score = float(params.get("score", 0.0))
    supersession_confidence = float(params.get("supersession_confidence", 0.0))

    op_hash = _op_hash(op_str, target, old_text, new_text)

    # Idempotence: skip if already promoted in a previous live run
    if op_hash in existing_promotion_hashes():
        return {
            "skipped": True,
            "reason": "already applied in a previous run (idempotent)",
            "hash": op_hash,
        }

    proposed = ProposedOp(
        op=op_str,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        old_text=old_text,
        new_text=new_text,
        reason=reason,
        sources=sources,
        score=score,
        supersession_confidence=supersession_confidence,
    )
    validation = validate_op(proposed)
    if not validation.ok:
        return {
            "applied": False,
            "dry_run": dry_run,
            "error": f"score gate failed: {validation.error}",
            "thresholds": thresholds_for_prompt(),
        }

    decision_record = {
        "hash": op_hash,
        "op": op_str,
        "target": target,
        "old_text": old_text,
        "new_text": new_text,
        "reason": reason,
        "sources": sources,
        "score": score,
        "supersession_confidence": supersession_confidence,
        "decision": "proposed" if dry_run else "applied",
        "phase": "Deep",
    }
    append_decisions([decision_record], run_id=run_id)

    if dry_run:
        return {
            "applied": False,
            "dry_run": True,
            "proposed": True,
            "op": op_str,
            "target": target,
            "old_text": old_text,
            "new_text": new_text,
            "score": score,
            "reason": reason,
            "hash": op_hash,
        }

    return _apply_live(proposed, op_hash, run_id, cfg, state)


def _apply_live(
    proposed: ProposedOp,
    op_hash: str,
    run_id: str,
    cfg: Any,
    state: dict[str, Any],
) -> dict[str, Any]:
    run_info = state.get("current_run", {})
    changes_applied = run_info.get("changes_applied", 0)
    adds_applied = run_info.get("adds_applied", 0)
    new_chars_added = run_info.get("new_chars_added", 0)

    max_changes = getattr(cfg, "max_changes_per_run", 3)
    max_adds = getattr(cfg, "max_adds_per_run", 1)
    max_new_chars = getattr(cfg, "max_new_chars_per_run", 250)

    # Run-level limits
    if changes_applied >= max_changes:
        return {
            "applied": False,
            "error": f"run limit reached: max_changes_per_run={max_changes} already applied",
        }
    if proposed.op == "add" and adds_applied >= max_adds:
        return {
            "applied": False,
            "error": f"run limit reached: max_adds_per_run={max_adds} already applied",
        }
    if proposed.op in ("add", "replace") and proposed.new_text:
        incoming_chars = len(proposed.new_text)
        if new_chars_added + incoming_chars > max_new_chars:
            return {
                "applied": False,
                "error": (
                    f"run limit reached: adding {incoming_chars} chars would exceed "
                    f"max_new_chars_per_run={max_new_chars} "
                    f"({new_chars_added} already added this run)"
                ),
            }

    path = _target_path(proposed.target)

    with filelock.FileLock(str(_LOCK_FILE), timeout=10):
        # Backup once per run (first mutation)
        if not run_info.get("backup_created"):
            _make_backup(run_id)
            run_info["backup_created"] = True

        # Build optional inline hint prefix
        hint_prefix = ""
        if getattr(cfg, "write_memory_hints", False):
            hint_prefix = _inline_hint(op_hash[:8], proposed.score)

        # Apply mutation
        result: MutationResult
        if proposed.op == "add":
            result = apply_add(path, proposed.new_text or "", hint_prefix=hint_prefix)
        elif proposed.op == "replace":
            result = apply_replace(
                path,
                proposed.old_text or "",
                proposed.new_text or "",
                hint_prefix=hint_prefix,
            )
        elif proposed.op == "remove":
            result = apply_remove(path, proposed.old_text or "")
        else:
            return {"applied": False, "error": f"unknown op: {proposed.op!r}"}

        if not result.ok:
            return {"applied": False, "error": result.error}

    # Update run counters in state
    changes_applied += 1
    if proposed.op == "add":
        adds_applied += 1
    if proposed.op in ("add", "replace") and result.char_delta > 0:
        new_chars_added += result.char_delta

    run_info.update({
        "changes_applied": changes_applied,
        "adds_applied": adds_applied,
        "new_chars_added": new_chars_added,
    })
    state["current_run"] = run_info
    write_state(state)

    # Record to promotions sidecar
    now_iso = datetime.now(timezone.utc).isoformat()
    append_promotion({
        "hash": op_hash,
        "op": proposed.op,
        "target": proposed.target,
        "old_text": proposed.old_text,
        "new_text": proposed.new_text,
        "reason": proposed.reason,
        "sources": proposed.sources,
        "score": proposed.score,
        "supersession_confidence": proposed.supersession_confidence,
        "status": "active",
        "promoted_at": now_iso,
        "run_id": run_id,
    })

    logger.info(
        "dreaming: applied %s on %s (score=%.2f, hash=%s)",
        proposed.op, proposed.target, proposed.score, op_hash,
    )

    return {
        "applied": True,
        "dry_run": False,
        "op": proposed.op,
        "target": proposed.target,
        "old_text": proposed.old_text,
        "new_text": proposed.new_text,
        "score": proposed.score,
        "reason": proposed.reason,
        "char_delta": result.char_delta,
        "changes_applied_this_run": changes_applied,
        "hash": op_hash,
    }
