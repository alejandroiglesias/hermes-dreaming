<p align="center">
  <img src="site/hermes-dreaming.png" alt="Hermes Dreaming" width="220">
</p>

# Hermes Dreaming

[![Security scan](https://github.com/alejandroiglesias/hermes-dreaming/actions/workflows/security.yml/badge.svg)](https://github.com/alejandroiglesias/hermes-dreaming/actions/workflows/security.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/alejandroiglesias/hermes-dreaming/badge)](https://securityscorecards.dev/viewer/?uri=github.com/alejandroiglesias/hermes-dreaming)
[![Socket Badge](https://socket.dev/api/badge/pypi/package/hermes-dreaming)](https://socket.dev/pypi/package/hermes-dreaming)

A background memory consolidation plugin for [Hermes](https://hermes-agent.nousresearch.com), built around Hermes' small, always-prompt-visible memory model.

## What it does

Hermes durable memory (`MEMORY.md` ≈2,200 chars, `USER.md` ≈1,375 chars) is scarce and injected into every session prompt. Hermes Dreaming runs a periodic three-phase consolidation cycle:

- **Light** — scans recent sessions for candidate facts/preferences
- **Deep** — identifies patterns, contradictions, supersessions
- **REM** — scores candidates and applies at most a few high-confidence memory operations (`add`, `replace`, `remove`)

A successful run may produce **zero durable writes**. The goal is highest future usefulness per character, not more memories.

> Note: memory mutations take effect on the **next** session start (Hermes loads memory as a frozen snapshot at session init).

## Install

```bash
hermes plugins install alejandroiglesias/hermes-dreaming
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
├── decisions.jsonl     # all Deep/REM decisions (including rejections)
├── promotions.jsonl    # applied memory operations (includes sidecar metadata)
├── runs/               # per-run JSON records
└── backups/            # timestamped MEMORY.md / USER.md snapshots
```

## Configuration

```yaml
dreaming:
  enabled: true
  schedule: '0 3 * * *'
  max_changes_per_run: 3
```

## Design

See [docs/implementation-brief.md](docs/implementation-brief.md) for the full design brief.
