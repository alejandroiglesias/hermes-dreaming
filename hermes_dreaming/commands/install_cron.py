from __future__ import annotations

"""
/dreaming install-cron (or `hermes dreaming install-cron`)

Registers a nightly Hermes cron job that runs '/dreaming run' in a fresh
agent session. Idempotent: if a job named 'hermes-dreaming' already exists,
it prints the existing job details without creating a duplicate.
"""

_JOB_NAME = "hermes-dreaming"
_DEFAULT_SCHEDULE = "0 3 * * *"
_PROMPT = "/dreaming run"


def handle(schedule: str = _DEFAULT_SCHEDULE) -> str:
    try:
        from cron.jobs import create_job, list_jobs
    except ImportError:
        return (
            "## hermes dreaming install-cron\n\n"
            "**Error:** Hermes cron module not available in this environment.\n\n"
            "The cron scheduler requires Hermes to be running in interactive or "
            "gateway mode. Start Hermes normally and retry."
        )

    schedule = (schedule or _DEFAULT_SCHEDULE).strip()

    # --- Idempotence check ---
    existing = _find_existing(list_jobs)
    if existing:
        return (
            "## hermes dreaming install-cron\n\n"
            f"**Already installed.** A cron job named `{_JOB_NAME}` exists:\n\n"
            f"- Job ID:   `{existing['id']}`\n"
            f"- Schedule: {existing.get('schedule_display', existing.get('schedule', '?'))}\n"
            f"- Enabled:  {existing.get('enabled', True)}\n"
            f"- Next run: {existing.get('next_run_at', 'unknown')}\n\n"
            "Run `hermes dreaming status` to see the last run outcome.\n"
            "To change the schedule, remove the existing job first:\n"
            f"  `hermes dreaming uninstall-cron` (or use the Hermes cron tool with job_id `{existing['id']}`)"
        )

    # --- Create ---
    try:
        job = create_job(
            prompt=_PROMPT,
            schedule=schedule,
            name=_JOB_NAME,
            deliver="local",
        )
    except Exception as exc:
        return (
            "## hermes dreaming install-cron\n\n"
            f"**Error creating cron job:** {exc}\n\n"
            f"Check that the schedule expression `{schedule}` is valid "
            "(e.g. `0 3 * * *` for nightly at 03:00)."
        )

    job_id = job["id"]
    schedule_display = job.get("schedule_display", schedule)
    next_run = job.get("next_run_at", "unknown")

    return (
        "## hermes dreaming install-cron\n\n"
        f"**Cron job registered.**\n\n"
        f"- Job ID:    `{job_id}`\n"
        f"- Name:      `{_JOB_NAME}`\n"
        f"- Schedule:  {schedule_display}\n"
        f"- Next run:  {next_run}\n"
        f"- Delivers:  local (output saved to DREAMS.md)\n\n"
        "Each night Hermes will run `/dreaming run` in a fresh session, "
        "promoting at most 1 new memory, 3 total changes, and 250 new chars.\n\n"
        "To review without applying: `hermes dreaming install-cron --schedule '0 3 * * *'`\n"
        "To remove: use `hermes cron` with the job ID above, or:\n"
        f"  ask Hermes to `remove cron job {job_id}`"
    )


def _find_existing(list_jobs_fn) -> dict | None:
    try:
        for job in list_jobs_fn(include_disabled=True):
            if job.get("name") == _JOB_NAME:
                return job
    except Exception:
        pass
    return None
