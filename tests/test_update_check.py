"""
Tests for the update-check cache logic in hermes_dreaming.__init__.

Network calls are never made — _fetch_and_cache_latest is always patched.
The notification sink is plain stdout (captured via capsys), because plugins
load before the CLI sets _cli_ref so ctx.inject_message is unavailable.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

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


def test_read_cache_returns_none_on_malformed_file(isolated_cache, caplog):
    isolated_cache["cache_file"].write_text("not json")
    assert _plugin._read_update_cache() is None
    # Malformed cache must surface a warning, not be silently swallowed
    assert any("malformed update cache" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _notify_if_update_available
# ---------------------------------------------------------------------------

def test_notify_prints_when_update_available(capsys):
    with patch.object(_plugin, "_current_version", return_value="0.3.6"):
        _plugin._notify_if_update_available("0.3.7")
    out = capsys.readouterr().out
    assert "0.3.7" in out
    assert "0.3.6" in out
    assert "hermes plugins update hermes-dreaming" in out


def test_notify_silent_when_up_to_date(capsys):
    with patch.object(_plugin, "_current_version", return_value="0.3.6"):
        _plugin._notify_if_update_available("0.3.6")
    assert capsys.readouterr().out == ""


def test_notify_silent_when_latest_is_none(capsys):
    _plugin._notify_if_update_available(None)
    assert capsys.readouterr().out == ""


def test_notify_propagates_when_current_version_raises(capsys, caplog):
    """A broken _current_version must NOT be silently swallowed by the notifier.

    _check_for_update wraps the call with logging, so the exception bubbles
    out of _notify_if_update_available and is reported there.
    """
    with patch.object(_plugin, "_current_version", side_effect=RuntimeError("no yaml")):
        with pytest.raises(RuntimeError):
            _plugin._notify_if_update_available("0.3.7")
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# _check_for_update — warm cache
# ---------------------------------------------------------------------------

def test_check_notifies_synchronously_from_warm_cache(isolated_cache, capsys):
    _write_cache(isolated_cache["cache_file"], "0.3.7")

    with patch.object(_plugin, "_fetch_and_cache_latest", return_value="0.3.7"):
        _plugin._check_for_update()

    # Notification must have been printed before _check_for_update returns,
    # i.e. synchronously (not from the background thread).
    assert "0.3.7" in capsys.readouterr().out


def test_check_silent_when_warm_cache_is_current(isolated_cache, capsys):
    _write_cache(isolated_cache["cache_file"], "0.3.6")

    with patch.object(_plugin, "_fetch_and_cache_latest", return_value="0.3.6"):
        _plugin._check_for_update()

    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# _check_for_update — cold / expired cache
# ---------------------------------------------------------------------------

def test_check_does_not_notify_synchronously_on_cold_cache(isolated_cache, capsys):
    """No cache file → no synchronous notification (background thread handles it)."""
    fetch_started = threading.Event()
    fetch_proceed = threading.Event()
    fetch_done = threading.Event()

    def _blocking_fetch():
        fetch_started.set()
        fetch_proceed.wait(timeout=2)
        try:
            return "0.3.7"
        finally:
            fetch_done.set()

    with patch.object(_plugin, "_fetch_and_cache_latest", side_effect=_blocking_fetch):
        _plugin._check_for_update()
        fetch_started.wait(timeout=2)
        # Background thread is blocked inside fetch — nothing printed yet
        assert capsys.readouterr().out == ""
        fetch_proceed.set()
        fetch_done.wait(timeout=2)
        time.sleep(0.05)  # let the thread call print before capsys tears down
        capsys.readouterr()  # drain so output doesn't leak into next test


def test_check_background_thread_notifies_on_cold_cache(isolated_cache, capsys):
    """When cache is cold and background fetch finds an update, notification prints."""
    done = threading.Event()

    def _fake_fetch():
        done.set()
        return "0.3.7"

    with patch.object(_plugin, "_fetch_and_cache_latest", side_effect=_fake_fetch):
        _plugin._check_for_update()
        done.wait(timeout=2)
        time.sleep(0.05)  # let the thread call print after fetch returns

    assert "0.3.7" in capsys.readouterr().out


def test_check_background_thread_does_not_double_notify_on_warm_cache(isolated_cache, capsys):
    """Warm cache already notified → background thread must not notify again."""
    _write_cache(isolated_cache["cache_file"], "0.3.7")
    done = threading.Event()

    def _fake_fetch():
        done.set()
        return "0.3.7"

    with patch.object(_plugin, "_fetch_and_cache_latest", side_effect=_fake_fetch):
        _plugin._check_for_update()
        done.wait(timeout=2)
        time.sleep(0.05)

    # Only one notification: the synchronous one from the warm cache
    out = capsys.readouterr().out
    assert out.count("Update available") == 1


def test_check_expired_cache_behaves_like_cold_cache(isolated_cache, capsys):
    """Expired cache → no synchronous notification (background thread handles it)."""
    _write_cache(isolated_cache["cache_file"], "0.3.7", age_seconds=_plugin._UPDATE_CACHE_TTL + 1)
    fetch_started = threading.Event()
    fetch_proceed = threading.Event()
    fetch_done = threading.Event()

    def _blocking_fetch():
        fetch_started.set()
        fetch_proceed.wait(timeout=2)
        try:
            return "0.3.7"
        finally:
            fetch_done.set()

    with patch.object(_plugin, "_fetch_and_cache_latest", side_effect=_blocking_fetch):
        _plugin._check_for_update()
        fetch_started.wait(timeout=2)
        assert capsys.readouterr().out == ""
        fetch_proceed.set()
        fetch_done.wait(timeout=2)
        time.sleep(0.05)
        capsys.readouterr()


# ---------------------------------------------------------------------------
# Exception surfacing — no silent swallows
# ---------------------------------------------------------------------------

def test_check_logs_when_cache_read_raises(isolated_cache, caplog, capsys):
    """If _read_update_cache itself blows up, _check_for_update logs and falls through."""
    with patch.object(_plugin, "_read_update_cache", side_effect=RuntimeError("boom")):
        with patch.object(_plugin, "_fetch_and_cache_latest", return_value=None):
            _plugin._check_for_update()
    assert any("update cache read failed" in rec.message for rec in caplog.records)


def test_check_logs_when_notify_raises(isolated_cache, caplog):
    """If the notifier raises, _check_for_update logs at WARNING, not silent pass."""
    _write_cache(isolated_cache["cache_file"], "0.3.7")
    with patch.object(_plugin, "_notify_if_update_available", side_effect=RuntimeError("boom")):
        with patch.object(_plugin, "_fetch_and_cache_latest", return_value=None):
            _plugin._check_for_update()
    assert any("update notify failed" in rec.message for rec in caplog.records)
