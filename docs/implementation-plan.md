# Hermes Dreaming Plugin — Implementation Plan

## Context

The repo currently contains only [hermes-dreaming-implementation-brief.md](hermes-dreaming-implementation-brief.md) (a thorough, decided spec). The goal of this plan is to turn that brief into a concrete, executable build for `hermes-dreaming` — a general Hermes plugin that periodically curates Hermes' premium memory (`MEMORY.md` ≈2,200 chars, `USER.md` ≈1,375 chars) by promoting very few new memories, replacing superseded entries, merging duplicates, and removing stale ones.

Key constraint from the brief: optimize **future usefulness per character**, not "remember more". A successful run may produce zero durable writes.

This plan reflects three confirmed decisions:

1. **Agent-driven reasoning** — a cron-scheduled fresh Hermes session runs `/dreaming run`; the agent's own LLM does Light/REM/Deep reasoning and calls plugin helper tools. The plugin makes no direct LLM calls.
2. **Full 8-phase delivery** — matching brief §18, but shipped phase-by-phase.
3. **Editable Python package in this repo** — installed into Hermes via `pip install -e .` and the `hermes_agent.plugins` entry point.

## Hermes APIs we rely on (verified from docs)

- Plugin layout: `plugin.yaml` + `__init__.py` exposing `register(ctx)`. Distributed via `[project.entry-points."hermes_agent.plugins"]`.
- `ctx.register_tool(name, schema, handler)` — agent-callable tools.
- `ctx.register_command(name, handler, description)` — slash commands in CLI/gateway.
- `ctx.register_cli_command(name, help, setup_fn, handler_fn)` — `hermes dreaming <subcmd>`.
- `ctx.register_hook(...)` — including `on_session_finalize` (used for lightweight signal capture only; never durable writes).
- Memory files live at `~/.hermes/memories/MEMORY.md` and `~/.hermes/memories/USER.md` and are injected as a **frozen snapshot at session start** — mid-session mutations only take effect on the next session, which is fine for a nightly cron run.
- No documented Python memory-tool API → we mutate files directly with backups + `filelock` + atomic writes. Equivalent runtime effect to the `memory` tool because of frozen-snapshot loading.
- Cron via `hermes cron create "0 3 * * *" "/dreaming run"` runs the slash command in a fresh session.

## Repo layout

```
hermes-dreaming/
├── pyproject.toml                 # entry-point: hermes_agent.plugins = hermes_dreaming
├── README.md
├── plugin.yaml                    # manifest (name, version, description)
├── hermes_dreaming/
│   ├── __init__.py                # register(ctx): wires tools, commands, hooks
│   ├── config.py                  # load ~/.hermes/dreaming/config + defaults
│   ├── paths.py                   # ~/.hermes/dreaming/* path helpers
│   ├── state.py                   # state.json + runs/ read/write
│   ├── memory_io.py               # MEMORY.md / USER.md read, parse, mutate, backup, filelock
│   ├── sidecar.py                 # candidates / decisions / promotions / memory_hints JSONL
│   ├── dreams_md.py               # DREAMS.md section writer
│   ├── session_reader.py          # recent sessions via Hermes session APIs (with safe fallback)
│   ├── orchestration.py           # builds the Light/REM/Deep prompt returned by /dreaming run
│   ├── scoring.py                 # canonical score/threshold helpers (brief §12)
│   ├── tools/
│   │   ├── get_state.py           # dreaming_get_state
│   │   ├── stage_candidates.py    # dreaming_stage_candidates
│   │   ├── record_decisions.py    # dreaming_record_decisions
│   │   ├── apply_memory_op.py     # dreaming_apply_memory_op (the only mutating tool)
│   │   ├── write_dream_report.py  # dreaming_write_dream_report
│   │   └── finalize_run.py        # dreaming_finalize_run
│   ├── commands/
│   │   ├── run.py                 # /dreaming run
│   │   ├── review.py              # /dreaming review (dry-run flag)
│   │   ├── status.py              # /dreaming status
│   │   └── compact.py             # /dreaming compact
│   ├── cli.py                     # hermes dreaming <subcmd> + install-cron helper
│   └── prompts/                   # Light/REM/Deep prompt templates (brief §19)
└── tests/
    ├── test_memory_io.py
    ├── test_scoring.py
    ├── test_apply_memory_op.py    # idempotence, backup, supersession-replace
    ├── test_orchestration.py      # snapshot test of returned prompt
    └── fixtures/
        ├── memory_with_meat.md    # for brief Test 1
        └── memory_duplicates.md   # for brief Test 4
```

Runtime state (created on first run, never committed):

```
~/.hermes/dreaming/
├── DREAMS.md
├── state.json
├── candidates.jsonl
├── decisions.jsonl
├── promotions.jsonl
├── memory_hints.jsonl
├── runs/<ISO_TS>.json
└── backups/<ISO_TS>/{MEMORY.md,USER.md}
```

## Tool & command surface

**Agent-callable tools** (registered via `ctx.register_tool`):

| Tool                                                                                 | Purpose                                                                                                                                                                                                                                                                                   | Mutating?         |
| ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| `dreaming_get_state`                                                                 | Returns current `MEMORY.md` / `USER.md` (with byte counts and free capacity), prior staged candidates, last run summary, recent session digests.                                                                                                                                          | no                |
| `dreaming_stage_candidates(candidates[])`                                            | Appends Light-phase candidates to `candidates.jsonl` (with hash for idempotence).                                                                                                                                                                                                         | no (sidecar only) |
| `dreaming_record_decisions(decisions[])`                                             | Records REM/Deep decisions (including rejections) for audit.                                                                                                                                                                                                                              | no (sidecar only) |
| `dreaming_apply_memory_op(op, target, old_text?, new_text?, reason, sources, score)` | Sole tool that mutates `MEMORY.md`/`USER.md`. Creates backup (once per run), enforces `max_changes_per_run`/`max_adds_per_run`/`max_new_chars_per_run`, refuses duplicates by hash, writes to `promotions.jsonl` and optional inline hint. Errors loudly when in `review` (dry-run) mode. | yes (gated)       |
| `dreaming_write_dream_report(section, markdown)`                                     | Appends to today's `DREAMS.md` entry under `Light Sleep` / `REM Sleep` / `Deep Sleep` / `Summary`.                                                                                                                                                                                        | no                |
| `dreaming_finalize_run(summary)`                                                     | Persists `runs/<ts>.json` and updates `state.json` (last_run, last_successful_run, change counts).                                                                                                                                                                                        | no                |

**Slash commands** (registered via `ctx.register_command`):

- `/dreaming run` — dry_run=False. Returns the orchestration prompt (current memory + recent sessions + Light/REM/Deep instructions + tool inventory + the brief's prompt templates from §19) so the agent can drive the cycle.
- `/dreaming review` — dry_run=True. Same prompt, but `dreaming_apply_memory_op` rejects mutations and only logs proposed ops to `decisions.jsonl` and `DREAMS.md`.
- `/dreaming status` — prints last run, last successful run, staged candidate count, last memory-change summary, current MEMORY/USER usage, recent errors.
- `/dreaming compact` — same as `run` but the orchestration prompt scopes Deep to "merge duplicates + remove obsolete entries; do not add".

**CLI commands** (registered via `ctx.register_cli_command`):

- `hermes dreaming {run,review,status,compact}` — thin wrappers that delegate to slash-command handlers.
- `hermes dreaming install-cron` — calls Hermes' `cronjob` tool (action="create") to register `0 3 * * *` running `/dreaming run`. Idempotent.

**Hooks**:

- `on_session_finalize` — optional cheap signal collector: appends a minimal session-id pointer to `state.json` (last 50). **Never** writes durable memory or extracts candidates. This avoids needing full session-search at run time when `session_reader.py` can simply read the recent pointers. If Hermes session-store APIs don't expose what we need, this hook is the fallback.

## Memory mutation strategy

`dreaming_apply_memory_op` is the only path to durable change. It:

1. Acquires a `filelock` on `~/.hermes/memories/`.
2. On first call per run, snapshots both files into `~/.hermes/dreaming/backups/<ISO_TS>/`.
3. Validates against run-level limits (brief §12.3): `max_changes_per_run=3`, `max_adds_per_run=1`, `max_new_chars_per_run=250`.
4. Rejects if candidate hash already in `promotions.jsonl` for the active session run (idempotence — brief §15.5).
5. Performs `add` / `replace` / `remove` with substring match for `replace`/`remove` (mirroring the built-in `memory` tool semantics).
6. Atomic write (write to tmpfile + `os.replace`).
7. Appends to `promotions.jsonl` with full sidecar (`id`, `target`, `text`, `status`, `score`, `sources`, `operation`, timestamps).
8. If `write_memory_hints: true`, prefixes the line with the compact `<!--drm:...-->` form from brief §13.5.

`replace` is preferred over `add`; `remove` is allowed when the agent flags an entry as superseded with confidence ≥0.85 (brief §12.2).

## Orchestration prompt (returned by `/dreaming run`)

Built in `orchestration.py`. Contains, in order:

1. **Premium-memory framing** — brief §2.3 + §10 condensed.
2. **Current state** — `MEMORY.md`, `USER.md`, byte counts, % capacity, prior unresolved candidates.
3. **Recent sessions** — N=14 most recent session digests via `session_reader`.
4. **Phase instructions**:
   - Light: extract candidates → call `dreaming_stage_candidates` → call `dreaming_write_dream_report("Light Sleep", ...)`.
   - REM: identify themes/contradictions → call `dreaming_record_decisions` (no mutations) → call `dreaming_write_dream_report("REM Sleep", ...)`.
   - Deep: score candidates with brief §12 model → call `dreaming_apply_memory_op` for each promoted op → call `dreaming_write_dream_report("Deep Sleep", ...)`.
   - Finalize: call `dreaming_finalize_run`.
5. **Hard limits & safety** — brief §15 (sensitive attributes, untrusted content, source grounding) and §12.3 (run limits).
6. **Prompt templates** — verbatim brief §19.1, §19.2, §19.3.

The agent then drives the cycle entirely through the registered tools.

## Phased deliverables (mirrors brief §18)

| Phase | Deliverable                                                                                                                          | Acceptance                                                                                                    |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| 1     | `pyproject.toml`, `plugin.yaml`, `__init__.py` skeleton, paths/config, stub commands, state dir creation.                            | `pip install -e .` registers plugin; `/dreaming status` prints empty state.                                   |
| 2     | `memory_io.py` (read + capacity), `session_reader.py` (recent sessions with safe fallback to the `on_session_finalize` pointer log). | `/dreaming review` lists current memory entries and recent session digests.                                   |
| 3     | Light: `dreaming_stage_candidates`, `dreaming_write_dream_report`, candidate hashing.                                                | `/dreaming review` produces a Light section in `DREAMS.md`; no durable writes.                                |
| 4     | REM: `dreaming_record_decisions`, contradiction/supersession heuristics in the orchestration prompt.                                 | REM section appears in `DREAMS.md`; no durable writes.                                                        |
| 5     | Deep review: `scoring.py` thresholds, `dreaming_apply_memory_op` in **dry-run** mode (proposes only).                                | `/dreaming review` writes a Deep proposal section with old/new/score/reason; `MEMORY.md`/`USER.md` unchanged. |
| 6     | Deep apply: real mutations, backups, run-level limits, idempotence.                                                                  | `/dreaming run` applies ≤3 changes; repeated immediate runs are no-ops; backups created.                      |
| 7     | `hermes dreaming install-cron` + docs.                                                                                               | Nightly run executes; output visible in `~/.hermes/cron/output/`; failures logged.                            |
| 8     | Optional inline hints behind `write_memory_hints: true`.                                                                             | Inline hint format matches brief §13.5; default keeps memory clean.                                           |

## Critical files (for the implementer)

- [hermes-dreaming-implementation-brief.md](hermes-dreaming-implementation-brief.md) — source of truth.
- New: `hermes_dreaming/__init__.py` — `register(ctx)` is the only entry point.
- New: `hermes_dreaming/tools/apply_memory_op.py` — the single mutating tool; highest-risk file. Needs filelock, backup, idempotence, dry-run, sidecar log, atomic write.
- New: `hermes_dreaming/orchestration.py` — defines the agent's behavior; treat as a prompt-engineered file under version control.
- New: `hermes_dreaming/scoring.py` — encodes thresholds from brief §12.2/§12.3 in one place for tuning.

## Verification (end-to-end)

1. **Install**: `pip install -e .` from this repo, then `hermes plugins list` shows `hermes-dreaming`.
2. **Status**: `/dreaming status` in a Hermes session prints the empty initial state and creates `~/.hermes/dreaming/`.
3. **Review on real memory**: `/dreaming review` writes a `DREAMS.md` entry with proposed ops; verify `MEMORY.md` and `USER.md` checksums unchanged.
4. **Brief Test 1 (superseded preference)** — fixture-driven: seed `MEMORY.md` with "User likes eating meat", inject a "I became vegetarian" turn, run `/dreaming run`, expect a `replace` op and a backup.
5. **Brief Test 4 (duplicate merge)** — seed three duplicate "simple tools" entries, run `/dreaming run`, expect a single merged replace.
6. **Idempotence** — run `/dreaming run` twice in a row; second run is a no-op (no new entries in `promotions.jsonl`, identical memory hashes).
7. **Run-level limit** — synthesize 10 high-score candidates, expect at most 3 applied (1 add, ≤2 replace/remove), rest deferred to `decisions.jsonl`.
8. **Cron**: `hermes dreaming install-cron`, then `hermes cron list` shows the job; manually trigger via `hermes cron run <id>` and verify output.
9. **Backup recovery**: confirm a manual `cp ~/.hermes/dreaming/backups/<ts>/*.md ~/.hermes/memories/` restores prior state.

## Open risks

- **Session reader API**: docs don't expose the SQLite/FTS5 store to general plugins. Phase 2 must verify Hermes exposes a usable Python helper; if not, fall back to the `on_session_finalize` pointer log + best-effort plain-text scrape from `~/.hermes/sessions/` (to be confirmed empirically before finalizing Phase 2).
- **Sensitive content**: brief §15.1 list is enforced in the orchestration prompt only — there is no Python-side guard. Acceptable per brief, but worth a regex deny-list in `apply_memory_op` for credential-shaped strings as belt-and-suspenders.
- **Frozen-snapshot semantics**: nightly mutations only take effect next session — explicitly desired, but should be called out in `README.md` so users don't expect mid-session updates.
