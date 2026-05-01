# hermes-dreaming

A background memory consolidation plugin for [Hermes](https://hermes-agent.nousresearch.com).

Inspired by OpenClaw Dreaming, adapted to Hermes' small, always-prompt-visible memory model.

## What it does

Hermes durable memory (`MEMORY.md` ≈2,200 chars, `USER.md` ≈1,375 chars) is scarce and injected into every session prompt. `hermes-dreaming` runs a periodic three-phase consolidation cycle:

- **Light** — scans recent sessions for candidate facts/preferences
- **REM** — identifies patterns, contradictions, supersessions
- **Deep** — scores candidates and applies at most a few high-confidence memory operations (`add`, `replace`, `remove`)

A successful run may produce **zero durable writes**. The goal is highest future usefulness per character, not more memories.

> Note: memory mutations take effect on the **next** session start (Hermes loads memory as a frozen snapshot at session init).

## Install

**Development (symlink into user plugins — no pip needed):**

```bash
mkdir -p ~/.hermes/plugins
ln -s ~/Development/hermes-dreaming/hermes_dreaming ~/.hermes/plugins/hermes-dreaming
# then enable in ~/.hermes/config.yaml:
# plugins:
#   enabled:
#     - hermes-dreaming
```

`plugin.yaml` lives inside `hermes_dreaming/` alongside `__init__.py`, so Hermes discovers it automatically via the symlink.

**Via pip (into the Python environment that runs hermes):**

```bash
pip install -e ~/Development/hermes-dreaming
```

## Commands

```
/dreaming run       — full cycle (schedules + manual)
/dreaming review    — dry-run; proposes ops without mutating memory
/dreaming status    — last run, candidate counts, memory usage
/dreaming compact   — merge duplicates + remove obsolete; no new adds
```

CLI equivalents:

```bash
hermes dreaming run
hermes dreaming review
hermes dreaming status
hermes dreaming compact
hermes dreaming install-cron   # register nightly 03:00 cron job
```

## State files

All runtime state lives in `~/.hermes/dreaming/`:

```
~/.hermes/dreaming/
├── DREAMS.md           # human-readable audit diary
├── state.json          # last run metadata
├── candidates.jsonl    # staged Light-phase candidates
├── decisions.jsonl     # all REM/Deep decisions (including rejections)
├── promotions.jsonl    # applied memory operations
├── memory_hints.jsonl  # sidecar metadata for each promoted entry
├── runs/               # per-run JSON records
└── backups/            # timestamped MEMORY.md / USER.md snapshots
```

## Configuration

```yaml
dreaming:
  enabled: true
  schedule: "0 3 * * *"
  max_changes_per_run: 3
  write_memory_hints: false
```

## Design

See [docs/implementation-brief.md](docs/implementation-brief.md) for the full design brief.
