from __future__ import annotations

"""
Retrieve recent Hermes sessions and compact message digests for use in
the Dreaming orchestration prompt.

Strategy:
  1. Try hermes_state.SessionDB (preferred — uses Hermes' own APIs).
  2. Fall back to direct SQLite read of ~/.hermes/state.db.
  3. Final fallback: pointer log from state.json (session IDs only, no content).

Sessions are returned as SessionDigest objects — compact enough to paste
into the orchestration prompt without flooding it.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Cap per session to keep the orchestration prompt from bloating
_MAX_TURNS_PER_SESSION = 6
_MAX_CHARS_PER_TURN = 400
_MAX_CHARS_PER_SESSION = 1200


class SessionDigest:
    def __init__(
        self,
        session_id: str,
        title: str | None,
        started_at: float | None,
        message_count: int,
        source: str,
        user_turns: list[str],
    ):
        self.session_id = session_id
        self.title = title
        self.started_at = started_at
        self.message_count = message_count
        self.source = source
        self.user_turns = user_turns

    @property
    def date_str(self) -> str:
        if self.started_at:
            try:
                dt = datetime.fromtimestamp(self.started_at, tz=timezone.utc)
                return dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                pass
        return "unknown date"

    def label(self) -> str:
        return self.title or f"Session {self.session_id[:8]}"

    def to_prompt_block(self) -> str:
        lines = [f"**{self.label()}** ({self.date_str}, {self.message_count} messages)"]
        for turn in self.user_turns:
            lines.append(f"  > {turn}")
        return "\n".join(lines)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def _extract_user_turns(messages: list[dict[str, Any]]) -> list[str]:
    """Pull the N most-substantive user turns from a message list."""
    turns = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content") or ""
        if isinstance(content, list):
            # OpenAI-style content blocks
            parts = [
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            content = " ".join(parts)
        content = str(content).strip()
        if not content or len(content) < 10:
            continue
        turns.append(_truncate(content, _MAX_CHARS_PER_TURN))
        if len(turns) >= _MAX_TURNS_PER_SESSION:
            break
    return turns


def _db_path() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home()) / "state.db"
    except Exception:
        return Path.home() / ".hermes" / "state.db"


# ---------------------------------------------------------------------------
# Primary path: hermes_state.SessionDB
# ---------------------------------------------------------------------------

def _read_via_session_db(limit: int) -> list[SessionDigest] | None:
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        rows = db.list_sessions_rich(limit=limit, order_by_last_active=True)
        digests = []
        for row in rows:
            sid = row.get("id", "")
            if not sid:
                continue
            msgs = []
            try:
                msgs = db.get_messages(sid)
            except Exception as exc:
                logger.debug("dreaming: get_messages(%s) failed: %s", sid[:8], exc)
            digests.append(SessionDigest(
                session_id=sid,
                title=row.get("title"),
                started_at=row.get("started_at"),
                message_count=row.get("message_count", 0),
                source=row.get("source", ""),
                user_turns=_extract_user_turns(msgs),
            ))
        return digests
    except Exception as exc:
        logger.debug("dreaming: SessionDB read failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Fallback 1: direct SQLite read
# ---------------------------------------------------------------------------

def _read_via_sqlite(limit: int) -> list[SessionDigest] | None:
    db_file = _db_path()
    if not db_file.exists():
        return None
    try:
        with sqlite3.connect(str(db_file)) as conn:
            conn.row_factory = sqlite3.Row
            session_rows = conn.execute(
                """
                SELECT s.id, s.title, s.started_at, s.message_count, s.source
                FROM sessions s
                LEFT JOIN (
                    SELECT session_id, MAX(timestamp) AS last_active
                    FROM messages GROUP BY session_id
                ) m ON m.session_id = s.id
                WHERE s.parent_session_id IS NULL OR EXISTS (
                    SELECT 1 FROM sessions p
                    WHERE p.id = s.parent_session_id AND p.end_reason = 'branched'
                )
                ORDER BY COALESCE(m.last_active, s.started_at) DESC, s.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            digests = []
            for row in session_rows:
                sid = row["id"]
                msg_rows = conn.execute(
                    "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp, id",
                    (sid,),
                ).fetchall()
                raw_msgs = [{"role": r["role"], "content": r["content"]} for r in msg_rows]
                digests.append(SessionDigest(
                    session_id=sid,
                    title=row["title"],
                    started_at=row["started_at"],
                    message_count=row["message_count"] or 0,
                    source=row["source"] or "",
                    user_turns=_extract_user_turns(raw_msgs),
                ))
        return digests
    except Exception as exc:
        logger.debug("dreaming: direct SQLite read failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Fallback 2: pointer log from state.json
# ---------------------------------------------------------------------------

def _read_via_pointer_log(limit: int) -> list[SessionDigest]:
    from .state import read as read_state
    state = read_state()
    ids = state.get("recent_session_ids", [])[-limit:]
    return [
        SessionDigest(
            session_id=sid,
            title=None,
            started_at=None,
            message_count=0,
            source="unknown",
            user_turns=[],
        )
        for sid in reversed(ids)
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_recent(limit: int = 14) -> list[SessionDigest]:
    """Return up to *limit* recent sessions, most recent first."""
    result = _read_via_session_db(limit)
    if result is not None:
        return result

    result = _read_via_sqlite(limit)
    if result is not None:
        return result

    logger.warning("dreaming: all session read paths failed; using pointer log only")
    return _read_via_pointer_log(limit)


def format_for_prompt(sessions: list[SessionDigest]) -> str:
    """Render session digests for inclusion in an orchestration prompt."""
    if not sessions:
        return "No recent sessions found.\n"
    lines = [f"### Recent sessions ({len(sessions)} shown)\n"]
    for s in sessions:
        lines.append(s.to_prompt_block())
        lines.append("")
    return "\n".join(lines)
