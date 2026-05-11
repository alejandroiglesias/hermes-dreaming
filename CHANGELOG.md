# Changelog

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
