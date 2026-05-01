"""Tests for hermes_dreaming.commands.install_cron."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hermes_dreaming.commands.install_cron import handle, _find_existing, _JOB_NAME


def _make_job(job_id="abc123", schedule_display="0 3 * * *", enabled=True):
    return {
        "id": job_id,
        "name": _JOB_NAME,
        "schedule_display": schedule_display,
        "enabled": enabled,
        "next_run_at": "2099-01-02T03:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# _find_existing
# ---------------------------------------------------------------------------

def test_find_existing_returns_job_when_name_matches():
    jobs = [_make_job()]
    result = _find_existing(lambda **kw: jobs)
    assert result is not None
    assert result["id"] == "abc123"


def test_find_existing_returns_none_when_not_found():
    jobs = [{"id": "x", "name": "other-job"}]
    result = _find_existing(lambda **kw: jobs)
    assert result is None


def test_find_existing_returns_none_on_list_error():
    def bad_list(**kw):
        raise RuntimeError("db gone")
    result = _find_existing(bad_list)
    assert result is None


# ---------------------------------------------------------------------------
# handle — cron module unavailable
# ---------------------------------------------------------------------------

def test_handle_graceful_when_cron_unavailable():
    with patch.dict("sys.modules", {"cron.jobs": None}):
        result = handle()
    assert "not available" in result.lower() or "error" in result.lower()


# ---------------------------------------------------------------------------
# handle — idempotence (already installed)
# ---------------------------------------------------------------------------

def test_handle_idempotent_when_job_exists():
    fake_job = _make_job()

    mock_cron = MagicMock()
    mock_cron.list_jobs.return_value = [fake_job]

    with patch.dict("sys.modules", {"cron.jobs": mock_cron}):
        result = handle()

    assert "Already installed" in result
    assert "abc123" in result
    mock_cron.create_job.assert_not_called()


# ---------------------------------------------------------------------------
# handle — happy path (create)
# ---------------------------------------------------------------------------

def test_handle_creates_job_when_none_exists():
    created_job = _make_job(job_id="new999")
    created_job["schedule_display"] = "At 03:00 every day"

    mock_cron = MagicMock()
    mock_cron.list_jobs.return_value = []
    mock_cron.create_job.return_value = created_job

    with patch.dict("sys.modules", {"cron.jobs": mock_cron}):
        result = handle()

    mock_cron.create_job.assert_called_once()
    call_kwargs = mock_cron.create_job.call_args
    assert call_kwargs.kwargs.get("prompt") == "/dreaming run" or "/dreaming run" in str(call_kwargs)
    assert "new999" in result
    assert "registered" in result.lower()


def test_handle_passes_custom_schedule():
    created_job = _make_job(job_id="sched001")
    created_job["schedule_display"] = "At 04:30 every day"

    mock_cron = MagicMock()
    mock_cron.list_jobs.return_value = []
    mock_cron.create_job.return_value = created_job

    with patch.dict("sys.modules", {"cron.jobs": mock_cron}):
        result = handle(schedule="30 4 * * *")

    call_kwargs = mock_cron.create_job.call_args
    assert "30 4 * * *" in str(call_kwargs)


def test_handle_delivers_local():
    created_job = _make_job(job_id="local001")
    mock_cron = MagicMock()
    mock_cron.list_jobs.return_value = []
    mock_cron.create_job.return_value = created_job

    with patch.dict("sys.modules", {"cron.jobs": mock_cron}):
        handle()

    call_kwargs = mock_cron.create_job.call_args
    assert call_kwargs.kwargs.get("deliver") == "local" or "local" in str(call_kwargs)


# ---------------------------------------------------------------------------
# handle — create_job raises
# ---------------------------------------------------------------------------

def test_handle_reports_error_when_create_fails():
    mock_cron = MagicMock()
    mock_cron.list_jobs.return_value = []
    mock_cron.create_job.side_effect = ValueError("bad schedule")

    with patch.dict("sys.modules", {"cron.jobs": mock_cron}):
        result = handle(schedule="not-valid")

    assert "Error" in result
    assert "bad schedule" in result
