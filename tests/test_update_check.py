"""
Tests for the update-check cache logic in hermes_dreaming.__init__.

Network calls are never made — _fetch_and_cache_latest is always patched.
Covers:
- Warm cache with update available → inject_message called synchronously
- Warm cache up to date → no inject_message
- Expired cache → no notification this session, background thread runs
- Cold cache (missing file) → same as expired
- _notify_if_update_available with None → silent
- Background thread notifies when cache was cold and update is found
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import hermes_dreaming.paths as _paths
import hermes_dreaming.__init__ as _plugin


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    dream_dir = tmp_path / "dreaming"
    dream_dir.mkdir()
    cache_file = dream_dir / ".update_check"

    monkeypatch.setattr(_paths, "DREAMING_DIR", dream_dir)
    monkeypatch.setattr(_plugin, "DREAMING_DIR", dream_dir)
    monkeypatch.setattr(_plugin, "_UPDATE_CACHE_FILE", cache_file)
    # Pin the "current" version so tests don't depend on plugin.yaml content
    monkeypatch.setattr(_plugin, "_current_version", lambda: "0.3.6")

    yield {"cache_file": cache_file, "dream_dir": dream_dir}


def _write_cache(cache_file: Path, latest: str, age_seconds: float = 0) -> None:
    cache_file.write_text(
        json.dumps({"ts": time.time() - age_seconds, "latest": latest})
    )


def _make_ctx() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# _read_update_cache
# ---------------------------------------------------------------------------

def test_read_cache_returns_none_when_file_missing(isolated_cache):
    assert _plugin._read_update_cache() is None


def test_read_cache_returns_version_when_fresh(isolated_cache):
    _write_cache(isolated_cache["cache_file"], "0.3.7")
    assert _plugin._read_update_cache() == "0.3.7"


def test_read_cache_returns_none_when_expired(isolated_cache):
    _write_cache(isolated_cache["cache_file"], "0.3.7", age_seconds=_plugin._UPDATE_CACHE_TTL + 1)
    assert _plugin._read_update_cache() is None


def test_read_cache_returns_none_on_malformed_file(isolated_cache):
    isolated_cache["cache_file"].write_text("not json")
    assert _plugin._read_update_cache() is None


# ---------------------------------------------------------------------------
# _notify_if_update_available
# ---------------------------------------------------------------------------

def test_notify_calls_inject_message_when_update_available():
    ctx = _make_ctx()
    with patch.object(_plugin, "_current_version", return_value="0.3.6"):
        _plugin._notify_if_update_available(ctx, "0.3.7")
    ctx.inject_message.assert_called_once()
    assert "0.3.7" in ctx.inject_message.call_args[0][0]
    assert "0.3.6" in ctx.inject_message.call_args[0][0]


def test_notify_silent_when_up_to_date():
    ctx = _make_ctx()
    with patch.object(_plugin, "_current_version", return_value="0.3.6"):
        _plugin._notify_if_update_available(ctx, "0.3.6")
    ctx.inject_message.assert_not_called()


def test_notify_silent_when_latest_is_none():
    ctx = _make_ctx()
    _plugin._notify_if_update_available(ctx, None)
    ctx.inject_message.assert_not_called()


def test_notify_silent_when_current_version_raises():
    ctx = _make_ctx()
    with patch.object(_plugin, "_current_version", side_effect=Exception("no yaml")):
        _plugin._notify_if_update_available(ctx, "0.3.7")
    ctx.inject_message.assert_not_called()


# ---------------------------------------------------------------------------
# _check_for_update — warm cache
# ---------------------------------------------------------------------------

def test_check_notifies_synchronously_from_warm_cache(isolated_cache):
    _write_cache(isolated_cache["cache_file"], "0.3.7")
    ctx = _make_ctx()

    with patch.object(_plugin, "_fetch_and_cache_latest", return_value="0.3.7") as mock_fetch:
        _plugin._check_for_update(ctx)

    # inject_message must have been called before _check_for_update returns,
    # i.e. synchronously (not from the background thread).
    ctx.inject_message.assert_called_once()
    # fetch still runs in background — we don't assert on it here


def test_check_silent_when_warm_cache_is_current(isolated_cache):
    _write_cache(isolated_cache["cache_file"], "0.3.6")
    ctx = _make_ctx()

    with patch.object(_plugin, "_fetch_and_cache_latest", return_value="0.3.6"):
        _plugin._check_for_update(ctx)

    ctx.inject_message.assert_not_called()


# ---------------------------------------------------------------------------
# _check_for_update — cold / expired cache
# ---------------------------------------------------------------------------

def test_check_does_not_notify_synchronously_on_cold_cache(isolated_cache):
    """No cache file → no synchronous notification (background thread handles it)."""
    ctx = _make_ctx()
    fetch_started = threading.Event()
    fetch_proceed = threading.Event()

    def _blocking_fetch():
        fetch_started.set()
        fetch_proceed.wait(timeout=2)
        return "0.3.7"

    with patch.object(_plugin, "_fetch_and_cache_latest", side_effect=_blocking_fetch):
        _plugin._check_for_update(ctx)
        fetch_started.wait(timeout=2)
        # Background thread is blocked inside fetch — inject_message not yet called
        ctx.inject_message.assert_not_called()
        fetch_proceed.set()  # let the thread finish


def test_check_background_thread_notifies_on_cold_cache(isolated_cache):
    """When cache is cold and background fetch finds an update, inject_message fires."""
    ctx = _make_ctx()
    done = threading.Event()

    def _fake_fetch():
        result = "0.3.7"
        done.set()
        return result

    with patch.object(_plugin, "_fetch_and_cache_latest", side_effect=_fake_fetch):
        _plugin._check_for_update(ctx)
        done.wait(timeout=2)
        # Give the thread a moment to call inject_message after fetch returns
        time.sleep(0.05)

    ctx.inject_message.assert_called_once()


def test_check_background_thread_does_not_double_notify_on_warm_cache(isolated_cache):
    """Warm cache already notified → background thread must not notify again."""
    _write_cache(isolated_cache["cache_file"], "0.3.7")
    ctx = _make_ctx()
    done = threading.Event()

    def _fake_fetch():
        done.set()
        return "0.3.7"

    with patch.object(_plugin, "_fetch_and_cache_latest", side_effect=_fake_fetch):
        _plugin._check_for_update(ctx)
        done.wait(timeout=2)
        time.sleep(0.05)

    # Only one call: the synchronous one from the warm cache
    assert ctx.inject_message.call_count == 1


def test_check_expired_cache_behaves_like_cold_cache(isolated_cache):
    """Expired cache → no synchronous notification (background thread handles it)."""
    _write_cache(isolated_cache["cache_file"], "0.3.7", age_seconds=_plugin._UPDATE_CACHE_TTL + 1)
    ctx = _make_ctx()
    fetch_started = threading.Event()
    fetch_proceed = threading.Event()

    def _blocking_fetch():
        fetch_started.set()
        fetch_proceed.wait(timeout=2)
        return "0.3.7"

    with patch.object(_plugin, "_fetch_and_cache_latest", side_effect=_blocking_fetch):
        _plugin._check_for_update(ctx)
        fetch_started.wait(timeout=2)
        # Background thread is blocked inside fetch — inject_message not yet called
        ctx.inject_message.assert_not_called()
        fetch_proceed.set()  # let the thread finish
