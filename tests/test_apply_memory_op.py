"""
Integration tests for dreaming_apply_memory_op.

These tests redirect all paths (MEMORY.md, USER.md, state.json, sidecars,
lock file, backups) to a temporary directory so they never touch the real
~/.hermes tree.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import hermes_dreaming.paths as _paths
import hermes_dreaming.state as _state
import hermes_dreaming.sidecar as _sidecar
import hermes_dreaming.memory_io as _mio
import hermes_dreaming.tools.apply_memory_op as _tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _op_hash(op, target, old_text, new_text) -> str:
    sig = f"{op}:{target}:{old_text or ''}:{new_text or ''}"
    return _content_hash(sig)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """Redirect all dreaming paths and memory paths to tmp_path."""
    mem_dir = tmp_path / "memories"
    mem_dir.mkdir()
    dream_dir = tmp_path / "dreaming"
    dream_dir.mkdir()

    memory_md = mem_dir / "MEMORY.md"
    user_md = mem_dir / "USER.md"
    user_md.write_text("", encoding="utf-8")

    # Patch path constants in all relevant modules
    for mod in (_paths, _state, _sidecar, _mio, _tool):
        if hasattr(mod, "MEMORY_MD"):
            monkeypatch.setattr(mod, "MEMORY_MD", memory_md)
        if hasattr(mod, "USER_MD"):
            monkeypatch.setattr(mod, "USER_MD", user_md)
        if hasattr(mod, "DREAMING_DIR"):
            monkeypatch.setattr(mod, "DREAMING_DIR", dream_dir)
        if hasattr(mod, "STATE_JSON"):
            monkeypatch.setattr(mod, "STATE_JSON", dream_dir / "state.json")
        if hasattr(mod, "CANDIDATES_JSONL"):
            monkeypatch.setattr(mod, "CANDIDATES_JSONL", dream_dir / "candidates.jsonl")
        if hasattr(mod, "DECISIONS_JSONL"):
            monkeypatch.setattr(mod, "DECISIONS_JSONL", dream_dir / "decisions.jsonl")
        if hasattr(mod, "PROMOTIONS_JSONL"):
            monkeypatch.setattr(mod, "PROMOTIONS_JSONL", dream_dir / "promotions.jsonl")
        if hasattr(mod, "BACKUPS_DIR"):
            monkeypatch.setattr(mod, "BACKUPS_DIR", dream_dir / "backups")
        if hasattr(mod, "RUNS_DIR"):
            monkeypatch.setattr(mod, "RUNS_DIR", dream_dir / "runs")

    # Patch lock file
    monkeypatch.setattr(_tool, "_LOCK_FILE", dream_dir / "memory_mutations.lock")

    # Yield references the test can use
    yield {
        "memory_md": memory_md,
        "user_md": user_md,
        "dream_dir": dream_dir,
        "promotions": dream_dir / "promotions.jsonl",
        "decisions": dream_dir / "decisions.jsonl",
        "backups": dream_dir / "backups",
    }


def _set_live_run(dream_dir: Path, run_id: str = "2099-01-01T03:00:00+00:00") -> None:
    """Write a live-mode state.json."""
    state_path = dream_dir / "state.json"
    state_path.write_text(
        json.dumps({
            "current_run": {
                "started_at": run_id,
                "dry_run": False,
                "changes_applied": 0,
                "adds_applied": 0,
                "new_chars_added": 0,
                "backup_created": False,
            }
        }),
        encoding="utf-8",
    )


def _set_dry_run(dream_dir: Path, run_id: str = "2099-01-01T03:00:00+00:00") -> None:
    state_path = dream_dir / "state.json"
    state_path.write_text(
        json.dumps({
            "current_run": {
                "started_at": run_id,
                "dry_run": True,
                "changes_applied": 0,
                "adds_applied": 0,
                "new_chars_added": 0,
                "backup_created": False,
            }
        }),
        encoding="utf-8",
    )


def _base_params(**overrides):
    p = {
        "op": "add",
        "target": "memory",
        "new_text": "- User avoids complex frameworks.",
        "reason": "User stated preference.",
        "sources": ["sess-abc"],
        "score": 0.91,
    }
    p.update(overrides)
    return p


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_does_not_mutate_memory(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Existing entry.\n", encoding="utf-8")
        _set_dry_run(p["dream_dir"])

        result = _tool.handler(_base_params())

        assert result.get("proposed") is True
        assert result.get("applied") is False
        assert p["memory_md"].read_text(encoding="utf-8") == "- Existing entry.\n"

    def test_dry_run_records_to_decisions(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Existing entry.\n", encoding="utf-8")
        _set_dry_run(p["dream_dir"])

        _tool.handler(_base_params())

        decisions_text = p["decisions"].read_text(encoding="utf-8")
        record = json.loads(decisions_text.strip())
        assert record["decision"] == "proposed"
        assert record["op"] == "add"


# ---------------------------------------------------------------------------
# Live-mode tests
# ---------------------------------------------------------------------------

class TestLiveAdd:
    def test_add_appends_entry(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Old entry.\n", encoding="utf-8")
        _set_live_run(p["dream_dir"])

        result = _tool.handler(_base_params(score=0.91))

        assert result["applied"] is True
        assert "- User avoids complex frameworks." in p["memory_md"].read_text(encoding="utf-8")

    def test_add_creates_backup_on_first_mutation(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Original.\n", encoding="utf-8")
        _set_live_run(p["dream_dir"])

        _tool.handler(_base_params(score=0.91))

        backups = list(p["backups"].rglob("MEMORY.md"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "- Original.\n"

    def test_add_records_to_promotions(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Old entry.\n", encoding="utf-8")
        _set_live_run(p["dream_dir"])

        _tool.handler(_base_params(score=0.91))

        promo = json.loads(p["promotions"].read_text(encoding="utf-8").strip())
        assert promo["op"] == "add"
        assert promo["status"] == "active"

    def test_add_fails_below_score_threshold(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Old.\n", encoding="utf-8")
        _set_live_run(p["dream_dir"])

        result = _tool.handler(_base_params(score=0.50))

        assert result["applied"] is False
        assert "score gate" in result.get("error", "")


class TestLiveReplace:
    def test_replace_updates_entry(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- User likes eating meat.\n- Other entry.\n", encoding="utf-8")
        _set_live_run(p["dream_dir"])

        params = _base_params(
            op="replace",
            old_text="User likes eating meat",
            new_text="- User is vegetarian and avoids meat.",
            score=0.92,
            supersession_confidence=0.90,
        )
        result = _tool.handler(params)

        assert result["applied"] is True
        content = p["memory_md"].read_text(encoding="utf-8")
        assert "vegetarian" in content
        assert "eating meat" not in content

    def test_replace_fails_when_old_text_not_found(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Unrelated entry.\n", encoding="utf-8")
        _set_live_run(p["dream_dir"])

        params = _base_params(
            op="replace",
            old_text="this does not exist",
            new_text="- Replacement.",
            score=0.90,
            supersession_confidence=0.80,
        )
        result = _tool.handler(params)

        assert result["applied"] is False
        assert "not found" in result.get("error", "")


class TestLiveRemove:
    def test_remove_deletes_entry(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Old stale entry.\n- Keep this.\n", encoding="utf-8")
        _set_live_run(p["dream_dir"])

        params = _base_params(
            op="remove",
            old_text="Old stale entry",
            new_text=None,
            score=0.0,
            supersession_confidence=0.90,
        )
        result = _tool.handler(params)

        assert result["applied"] is True
        content = p["memory_md"].read_text(encoding="utf-8")
        assert "Old stale entry" not in content
        assert "Keep this" in content

    def test_remove_fails_low_confidence(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Old stale entry.\n", encoding="utf-8")
        _set_live_run(p["dream_dir"])

        params = _base_params(
            op="remove",
            old_text="Old stale entry",
            new_text=None,
            score=0.0,
            supersession_confidence=0.50,
        )
        result = _tool.handler(params)
        assert result["applied"] is False


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------

class TestIdempotence:
    def test_second_call_with_same_op_is_skipped(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Old entry.\n", encoding="utf-8")
        _set_live_run(p["dream_dir"])

        params = _base_params(score=0.91)
        first = _tool.handler(params)
        assert first["applied"] is True

        # Reset state counters (simulate same run re-calling) but keep promotions
        _set_live_run(p["dream_dir"])
        second = _tool.handler(params)
        assert second.get("skipped") is True
        assert "idempotent" in second.get("reason", "")


# ---------------------------------------------------------------------------
# Run-level limits
# ---------------------------------------------------------------------------

class TestRunLimits:
    def _params_unique(self, n: int, **overrides):
        base = {"new_text": f"- Unique add #{n}.", "score": 0.91}
        base.update(overrides)
        return _base_params(**base)

    def _set_state_with_counts(self, dream_dir, changes=0, adds=0, chars=0):
        state_path = dream_dir / "state.json"
        state_path.write_text(
            json.dumps({
                "current_run": {
                    "started_at": "2099-01-01T03:00:00+00:00",
                    "dry_run": False,
                    "changes_applied": changes,
                    "adds_applied": adds,
                    "new_chars_added": chars,
                    "backup_created": True,
                }
            }),
            encoding="utf-8",
        )

    def test_max_changes_per_run_enforced(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Existing.\n", encoding="utf-8")
        # Already at limit
        self._set_state_with_counts(p["dream_dir"], changes=3)

        result = _tool.handler(self._params_unique(99))
        assert result["applied"] is False
        assert "max_changes_per_run" in result.get("error", "")

    def test_max_adds_per_run_enforced(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Existing.\n", encoding="utf-8")
        # One add already done
        self._set_state_with_counts(p["dream_dir"], changes=1, adds=1)

        result = _tool.handler(self._params_unique(88))
        assert result["applied"] is False
        assert "max_adds_per_run" in result.get("error", "")

    def test_max_new_chars_per_run_enforced(self, isolated_paths):
        p = isolated_paths
        p["memory_md"].write_text("- Existing.\n", encoding="utf-8")
        # 240 of 250 chars already used
        self._set_state_with_counts(p["dream_dir"], changes=0, adds=0, chars=245)

        # new_text with 20 chars would push past 250
        result = _tool.handler(self._params_unique(77, new_text="- Entry over the limit now."))
        assert result["applied"] is False
        assert "max_new_chars_per_run" in result.get("error", "")


# ---------------------------------------------------------------------------
# Brief Test 1 — superseded meat preference → vegetarian
# ---------------------------------------------------------------------------

class TestBriefTest1:
    """Seed MEMORY.md with 'User likes eating meat', apply a replace for vegetarian."""

    def test_vegetarian_replace(self, isolated_paths):
        p = isolated_paths
        fixture = FIXTURES / "memory_with_meat.md"
        p["memory_md"].write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
        _set_live_run(p["dream_dir"])

        params = {
            "op": "replace",
            "target": "memory",
            "old_text": "User likes eating meat",
            "new_text": "- User is vegetarian and avoids meat.",
            "reason": "User stated they became vegetarian.",
            "sources": ["sess-veg-001"],
            "score": 0.93,
            "supersession_confidence": 0.92,
        }
        result = _tool.handler(params)

        assert result["applied"] is True
        content = p["memory_md"].read_text(encoding="utf-8")
        assert "vegetarian" in content
        assert "eating meat" not in content

        # backup must exist with original content
        backups = list(p["backups"].rglob("MEMORY.md"))
        assert len(backups) == 1
        assert "eating meat" in backups[0].read_text(encoding="utf-8")

    def test_backup_not_duplicated_on_second_op(self, isolated_paths):
        """Only one backup per run, even with two ops."""
        p = isolated_paths
        fixture = FIXTURES / "memory_with_meat.md"
        p["memory_md"].write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

        run_id = "2099-06-01T03:00:00+00:00"
        _set_live_run(p["dream_dir"], run_id=run_id)

        # First op
        _tool.handler({
            "op": "replace",
            "target": "memory",
            "old_text": "User likes eating meat",
            "new_text": "- User is vegetarian.",
            "reason": "Became vegetarian.",
            "sources": ["sess-a"],
            "score": 0.93,
            "supersession_confidence": 0.92,
        })

        # Second op in same run — need unique new_text to avoid idempotence skip
        _tool.handler({
            "op": "replace",
            "target": "memory",
            "old_text": "User prefers concise answers",
            "new_text": "- User strongly prefers terse, direct replies.",
            "reason": "Repeated pattern.",
            "sources": ["sess-b"],
            "score": 0.88,
            "supersession_confidence": 0.82,
        })

        backup_dirs = [d for d in p["backups"].iterdir() if d.is_dir()]
        assert len(backup_dirs) == 1  # only one backup dir per run


# ---------------------------------------------------------------------------
# Brief Test 4 — duplicate merge (simple tools)
# ---------------------------------------------------------------------------

class TestBriefTest4:
    """Three near-duplicate 'simple tools' entries → one canonical merged replace."""

    def test_duplicate_merge_replaces_first_entry(self, isolated_paths):
        p = isolated_paths
        fixture = FIXTURES / "memory_duplicates.md"
        p["memory_md"].write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
        _set_live_run(p["dream_dir"])

        params = {
            "op": "replace",
            "target": "memory",
            "old_text": "User prefers simple tools over complex frameworks",
            "new_text": "- User consistently prefers simple, lightweight tools over complex frameworks.",
            "reason": "Three near-duplicate entries merged into one canonical form.",
            "sources": ["sess-x", "sess-y"],
            "score": 0.90,
            "supersession_confidence": 0.88,
        }
        result = _tool.handler(params)

        assert result["applied"] is True
        content = p["memory_md"].read_text(encoding="utf-8")
        assert "consistently prefers simple" in content
        # At least the first duplicate line is replaced
        assert "prefers simple tools over complex frameworks" not in content

    def test_then_remove_redundant_duplicates(self, isolated_paths):
        """After the merge replace, remove the two remaining redundant lines."""
        p = isolated_paths
        fixture = FIXTURES / "memory_duplicates.md"
        p["memory_md"].write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

        run_id = "2099-07-01T03:00:00+00:00"
        _set_live_run(p["dream_dir"], run_id=run_id)

        # Step 1: merge replace
        _tool.handler({
            "op": "replace",
            "target": "memory",
            "old_text": "User prefers simple tools over complex frameworks",
            "new_text": "- User consistently prefers simple, lightweight tools over complex frameworks.",
            "reason": "Merge duplicates.",
            "sources": ["sess-x"],
            "score": 0.90,
            "supersession_confidence": 0.88,
        })

        # Step 2: remove one duplicate
        _tool.handler({
            "op": "remove",
            "target": "memory",
            "old_text": "User likes simple tools for CLI tasks",
            "reason": "Redundant after merge.",
            "sources": ["sess-x"],
            "score": 0.0,
            "supersession_confidence": 0.90,
        })

        # Step 3: remove the other duplicate (hits max_changes=3 — this is 3rd op)
        _tool.handler({
            "op": "remove",
            "target": "memory",
            "old_text": "User tends to use simple tools rather than heavyweight solutions",
            "reason": "Redundant after merge.",
            "sources": ["sess-x"],
            "score": 0.0,
            "supersession_confidence": 0.90,
        })

        content = p["memory_md"].read_text(encoding="utf-8")
        # Canonical entry must exist
        assert "consistently prefers simple, lightweight tools" in content
        # All three original duplicate lines should be gone
        assert "prefers simple tools over complex frameworks" not in content
        assert "simple tools for CLI tasks" not in content
        assert "tends to use simple tools" not in content
