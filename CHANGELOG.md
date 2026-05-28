# Changelog

## [0.3.12] - 2026-05-27

### Changed
- `DREAMS.md` run headers now render in local time (`YYYY-MM-DD HH:MM`) for easier human scanning, both during live writes and when rebuilding the diary from canonical run records.

### Added
- Development extras in `pyproject.toml` (`[project.optional-dependencies].dev`) now include `pytest`.
- `Makefile` now provides a `make test` shortcut that runs tests via the project-local `.venv` and prints setup guidance when the venv is missing.

## [0.3.11] - 2026-05-27

### Fixed
- Dreaming tools now defensively bootstrap a missing `current_run` so cron-delivered runs no longer fall back to `run_id: "unknown"` or accidentally default to dry-run behavior in live cycles.
- `/dreaming install-cron` now installs an explicit orchestration prompt that starts with `dreaming_get_state(ensure_run=true, dry_run=false)` to avoid slash-command routing ambiguities in scheduled jobs.
- `USER.md` entry parsing now supports Hermes' `§`-delimited paragraph format in addition to bullet lists, so status/usage reporting reflects real entry counts.

## [0.3.6] - 2026-05-16

### Added
- **Per-run instructions**: `/dreaming run <text>` and `hermes dreaming run --instructions "<text>"` inject a free-text focus into the orchestration prompt for that cycle. `/dreaming review` supports the same flag. Falls back to `dreaming.instructions` in `~/.hermes/config.yaml` for unattended cron runs.
- **Error taxonomy**: `dreaming_finalize_run` now accepts `error_type` (one of `timeout`, `internal_error`, `tool_error`, `input_too_large`, `invalid_state`, `user_canceled`) and `error_message` when `success=false`. `/dreaming status` surfaces both fields so overnight cron failures are no longer silent.
- **Canonical run-record schema**: `runs/*.json` now has stable typed fields — `schema_version`, `id`, `status`, `dry_run`, `instructions`, `created_at`, `ended_at`, `error`, `summary`, `sections`. `start_run` writes an initial `"running"` record; `dreaming_write_dream_report` accumulates phase sections into a sidecar that `finish_run` folds in.
- `render_dreams_md_from_runs()` to rebuild `DREAMS.md` from canonical run records.
- `dreaming.instructions` config key in `~/.hermes/config.yaml` for a persistent per-schedule focus.

## [0.3.5] - 2026-05-11

### Changed
- Update check now queries the GitHub releases API instead of PyPI, matching how the plugin is distributed (`hermes plugins install`).
- Removed all PyPI publishing infrastructure (`.github/workflows/publish.yml`).

## [0.3.4] - 2026-05-11

### Fixed
- Update notification now says `hermes plugins update hermes-dreaming` instead of a pip command.
- Install docs replaced with `hermes plugins install alejandroiglesias/hermes-dreaming` and `hermes plugins update hermes-dreaming` — no pip or Python path wrangling needed.

## [0.3.3] - 2026-05-11

### Fixed
- Update notification and install docs now use `python3 -m pip` instead of `pip`, and the notification shows the exact `sys.executable` path so users on venv-only setups aren't left with a broken command.

## [0.3.2] - 2026-05-11

### Fixed
- Update check now surfaces via `inject_message` so the notification is visible in Hermes chat, instead of only going to the Python logger (which Hermes does not display).

## [0.3.1] - 2026-05-11

### Fixed
- `install-cron` now reads cron schedule from `config.yaml` instead of ignoring it and always using `0 3 * * *`

## [0.3.0] - 2026-05-10

### Added
- Background update check on plugin load: spawns a daemon thread that compares the installed version against PyPI and logs a warning with the upgrade command if a newer version is available. Fails silently on network errors.

## [0.2.0] - 2026-05-10

### Fixed
- `toolset` parameter was missing from all `register_tool` calls, causing tools to silently fail to register and leaving `/dreaming run` as a display-only prompt wall.
- `/dreaming run` and `/dreaming review` now use `inject_message` to feed the orchestration prompt back to the agent, so the cycle actually executes instead of being shown as text.
- Tool handlers now accept `**kwargs` to handle `task_id` and other arguments passed by the Hermes registry dispatcher.
- Tool handlers now return JSON strings instead of raw dicts; raw dicts caused HTTP 400 errors from every provider on the tool result message.
- Stale stub headers (run headers with no phase content, left by failed or interrupted runs) are now stripped from `DREAMS.md` at the start of each new run.
- Agent-included section headers in the markdown passed to `dreaming_write_dream_report` are stripped to avoid duplicate headers in `DREAMS.md`.

## [0.1.0] - 2026-05-01

### Added
- Initial release.
- Light → Deep → REM sleep cycle for curating `MEMORY.md` and `USER.md`.
- Agent-driven orchestration: `/dreaming run` returns a prompt that drives the cycle via `dreaming_*` tools.
- `dreaming_stage_candidates` — stage Light-phase candidate memories with deduplication.
- `dreaming_record_decisions` — persist Deep and REM phase decisions to `decisions.jsonl`.
- `dreaming_apply_memory_op` — apply scored memory operations with threshold enforcement and run-level limits.
- `dreaming_write_dream_report` — append phase sections to `DREAMS.md`.
- `dreaming_get_state` — re-read memory, sessions, and prior candidates mid-cycle.
- `dreaming_finalize_run` — record run outcome to `state.json` and `runs/`.
- `/dreaming review` dry-run mode: proposes operations without mutating memory files.
- `/dreaming status` — show last run, candidate counts, and memory usage.
- `/dreaming compact` — merge duplicates and remove obsolete entries without adding new ones.
- `/dreaming install-cron` — register a nightly dreaming cron job.
- `on_session_end` hook to record session pointers for the next cycle.
- Scoring model with 13 dimensions and configurable per-operation thresholds.
- `query_diversity`, `recency`, and `actionability` scoring dimensions.
