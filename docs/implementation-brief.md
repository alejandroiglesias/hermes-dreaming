# Hermes Dreaming — Implementation Brief

**Project name:** `hermes-dreaming`  
**Status:** Proposed  
**Goal:** Build a Hermes plugin that feels like an analogue/port of OpenClaw Dreaming, adapted to Hermes' memory model.

---

## 1. Executive Summary

`hermes-dreaming` is a **background memory consolidation plugin for Hermes**.

It is inspired by OpenClaw Dreaming, but it should not be a line-by-line clone or a new memory architecture. Its job is to bring the *spirit* of Dreaming into Hermes:

> **Short-term/session signals → staged candidates → reflective patterns → premium durable memory updates.**

However, Hermes has a very different memory model from OpenClaw. Hermes' built-in durable memory is extremely small and always prompt-visible:

- `MEMORY.md`: ~2,200 characters
- `USER.md`: ~1,375 characters

Therefore, the plugin must not optimize for “remembering more.”

It must optimize for:

> **highest future usefulness per character.**

The plugin is only worth building if it improves the quality and currency of Hermes' premium memory. It should promote very few new memories, replace superseded entries, merge duplicates, and remove/compact stale low-value entries when appropriate.

A successful run may produce **zero durable memory writes**.

---

## 2. Design Philosophy

### 2.1 What this plugin is

`hermes-dreaming` is:

- a general Hermes plugin, not a memory provider;
- a scheduled/manual memory consolidation process;
- a curatorial layer over Hermes' existing built-in memory;
- an analogue of OpenClaw Dreaming adapted to Hermes;
- a tool for keeping `MEMORY.md` / `USER.md` compact, current, and high-signal.

### 2.2 What this plugin is not

`hermes-dreaming` is **not**:

- a replacement for Hermes' memory provider system;
- a new vector database;
- a temporal knowledge graph;
- a replacement for Honcho/Hindsight/Supermemory/etc.;
- an OpenClaw memory-core port;
- a big memory framework;
- a daily summary generator;
- a system that appends lots of memories every night.

### 2.3 Core principle

```text
Hermes durable memory is premium memory.
Every character has a permanent prompt cost.
Dreaming must maximize future usefulness per character.
```

A candidate memory should only be promoted if it is:

1. likely to affect future responses often;
2. stable enough to remain true;
3. compact enough to justify its prompt cost;
4. not already represented by existing memory;
5. better as durable memory than as session history, `DREAMS.md`, or a skill.

---

## 3. Background: Hermes vs OpenClaw Memory

### 3.1 OpenClaw Dreaming model

OpenClaw Dreaming is a background memory consolidation system in `memory-core`.

Its documented shape:

- opt-in and disabled by default;
- writes machine state to `memory/.dreams/`;
- writes human-readable diary/reports to `DREAMS.md`;
- uses three cooperative phases:
  - **Light**: stage recent short-term material; no durable writes.
  - **REM**: reflect on themes/recurring ideas; no durable writes.
  - **Deep**: score candidates and promote durable candidates to `MEMORY.md`.

OpenClaw Deep phase uses weighted scoring and threshold gates such as `minScore`, `minRecallCount`, and `minUniqueQueries`. It rehydrates snippets from live daily files before writing, skips stale/deleted source snippets, and appends promoted entries to `MEMORY.md`.

### 3.2 Hermes memory model

Hermes already has:

- bounded `MEMORY.md` and `USER.md`;
- a `memory` tool that can `add`, `replace`, or `remove`;
- automatic session storage in SQLite with FTS5 search;
- `session_search` for finding past conversations;
- optional external memory providers such as Honcho, Hindsight, Mem0, Supermemory, etc.;
- plugin support for tools, hooks, slash commands, and CLI commands;
- cron/scheduled tasks.

Hermes durable memory is much smaller than OpenClaw-style Markdown memory and is injected into the system prompt at the start of a session. It should be treated as high-value, low-capacity prompt memory.

### 3.3 The real gap

Hermes already has parts of the Dreaming mental model:

```text
session history → search/retrieval
MEMORY.md / USER.md → premium durable memory
memory tool → add / replace / remove
capacity pressure → consolidation
```

The missing piece is a **periodic, intentional, scoring-based curator** that asks:

- What repeated signals from recent sessions deserve premium memory?
- What current memories are superseded by newer statements?
- Which entries should be replaced, merged, or removed?
- Which details should remain only in session history?
- Which workflows belong in skills rather than memory?

This is where `hermes-dreaming` adds value.

---

## 4. Primary Objective

Build a Hermes plugin that periodically consolidates memory by:

1. scanning recent sessions and existing durable memory;
2. staging candidate facts/preferences/decisions/workflow learnings;
3. reflecting on patterns and contradictions;
4. scoring candidates by future usefulness per character;
5. applying a small number of high-confidence memory operations:
   - `add`
   - `replace`
   - `remove`
6. writing an auditable `DREAMS.md` report.

The plugin should improve Hermes memory by making it:

- more current;
- less contradictory;
- more compact;
- more useful per character;
- less cluttered with stale/superseded information.

---

## 5. Non-Goals

Do **not** implement these:

- Do not replace Hermes' memory provider system.
- Do not build a new vector database.
- Do not require Graphiti, QMD, Redis, Postgres, or external infrastructure.
- Do not modify Hermes core unless absolutely necessary.
- Do not implement a full temporal knowledge graph.
- Do not add lots of config knobs.
- Do not create compatibility modes.
- Do not implement idle “nap” runs.
- Do not ingest or promote untrusted web/email content without grounding and safety checks.
- Do not store sensitive personal attributes unless explicitly requested or clearly safe under policy.
- Do not append many new memory entries per run.
- Do not treat `DREAMS.md` as a promotion source.
- Do not make the plugin dependent on Honcho or any external memory provider.

---

## 6. Recommended Architecture

### 6.1 Plugin type

This should be a **general Hermes plugin**, not a memory provider.

Reason:

- Hermes memory providers are single-select.
- The user may want Honcho, Hindsight, or another provider active.
- Dreaming is a process, not the primary memory backend.
- General plugins can coexist with memory providers.

Desired shape:

```text
Hermes
├── built-in memory
│   ├── MEMORY.md
│   └── USER.md
├── optional external memory provider
│   └── Honcho / Hindsight / etc.
└── general plugin
    └── hermes-dreaming
```

### 6.2 Files

Suggested internal plugin storage:

```text
~/.hermes/dreaming/
├── DREAMS.md
├── state.json
├── runs/
│   └── YYYY-MM-DDTHH-mm-ss.json
├── candidates.jsonl
├── decisions.jsonl
├── promotions.jsonl
└── memory_hints.jsonl
```

`DREAMS.md` should be human-readable.

The JSONL files are machine-readable sidecars and should not be injected into the prompt by default.

### 6.3 Why sidecar metadata matters

Because `MEMORY.md` / `USER.md` are extremely small, metadata should generally live outside the durable prompt memory.

Inline memory hints may be useful, but they consume scarce prompt characters. Therefore:

- default should keep memory entries clean;
- sidecar metadata should always be recorded;
- optional inline hints may exist but should be disabled by default.

---

## 7. Configuration

Keep config minimal.

Recommended config:

```yaml
plugins:
  enabled:
    - hermes-dreaming

dreaming:
  enabled: true
  schedule: "0 3 * * *"
  max_changes_per_run: 3
  write_memory_hints: false
```

### 7.1 Config fields

#### `enabled`

Whether the plugin is active.

#### `schedule`

Default scheduled run. Recommended default:

```text
0 3 * * *
```

No idle/napping behavior.

#### `max_changes_per_run`

Maximum durable memory mutations in one Dreaming run.

Default: `3`

This includes additions, replacements, and removals.

#### `write_memory_hints`

Whether the plugin writes compact metadata inline inside `MEMORY.md` / `USER.md`.

Default: `false`.

When `false`, hints are stored only in sidecar files.

When `true`, promoted/replaced memory entries may include compact comments.

Example:

```md
<!--drm:id=250501a;s=.91;p=.88;st=active-->
- Ale prefers simple, packaged, low-maintenance tools over custom infrastructure unless the custom route has a clear advantage.
```

The plugin should still write full metadata to sidecar storage.

---

## 8. Commands / User-Facing API

The plugin should expose a small command surface.

### 8.1 Slash commands

```text
/dreaming run
/dreaming review
/dreaming status
/dreaming compact
```

#### `/dreaming run`

Runs a full Dreaming cycle and applies memory changes.

This is the main command and should mirror the scheduled behavior.

#### `/dreaming review`

Runs the full cycle in dry-run mode.

It should:

- stage candidates;
- score them;
- propose add/replace/remove operations;
- write a review report;
- not mutate `MEMORY.md` / `USER.md`.

This is useful for debugging and trust-building, but scheduled runs should not be forced into review mode.

#### `/dreaming status`

Shows:

- last run;
- last successful run;
- number of staged candidates;
- last memory changes;
- current memory usage if available;
- errors/warnings.

#### `/dreaming compact`

Runs only the memory cleanup/consolidation part:

- inspect `MEMORY.md` and `USER.md`;
- detect duplicates, contradictions, superseded entries, stale entries;
- propose or apply compacting operations.

This can be implemented as a focused subset of Deep.

### 8.2 CLI commands

Optional, but useful:

```text
hermes dreaming run
hermes dreaming review
hermes dreaming status
hermes dreaming compact
```

---

## 9. Dreaming Phases

The plugin should preserve the conceptual OpenClaw phase model, but adapt Deep to Hermes' small memory.

### 9.1 Light Phase — stage signals

Purpose:

- collect recent evidence;
- deduplicate obvious repeats;
- stage candidate lines;
- record reinforcement signals;
- never write durable memory.

Inputs:

- recent Hermes sessions;
- session search results;
- existing `MEMORY.md`;
- existing `USER.md`;
- sidecar state from previous runs;
- optionally tool-failure/correction traces if accessible.

Outputs:

- staged candidates in `candidates.jsonl`;
- Light section in `DREAMS.md` or current run report.

Candidate categories:

- user preference;
- communication preference;
- project/environment fact;
- decision;
- correction;
- recurring workflow;
- supersession signal;
- stale/obsolete signal;
- skill candidate.

Light should be cheap and conservative.

### 9.2 REM Phase — reflect on patterns

Purpose:

- identify recurring themes;
- detect contradictions;
- identify candidate canonical memories;
- distinguish durable preferences from session-specific details;
- identify facts better suited to skills or session history.

REM does not write durable memory.

Outputs:

- reflective summaries in `DREAMS.md`;
- reinforcement signals for Deep;
- suggested canonical phrasings.

REM should ask:

```text
What did we learn that may still matter in a month?
What older memory does this update or replace?
What should remain only in session history?
What belongs in a skill rather than memory?
```

### 9.3 Deep Phase — mutate premium memory

Purpose:

- decide what enters, leaves, or changes in `MEMORY.md` / `USER.md`.

Deep is the only phase allowed to mutate durable memory.

Allowed operations:

- `add`
- `replace`
- `remove`

Deep should strongly prefer:

1. no-op;
2. replace/merge;
3. remove obsolete entries;
4. add new entries only when truly premium.

Deep should not behave like a nightly append process.

---

## 10. Premium Memory Policy

Hermes durable memory is always prompt-visible and scarce.

Deep should maximize:

```text
future usefulness per character
```

### 10.1 Promotion criteria

Promote only if the candidate is:

- stable;
- repeatedly observed or explicitly stated;
- likely to affect future responses;
- compact;
- not already represented;
- not easily recoverable from session history;
- not better represented as a skill;
- not sensitive unless explicitly approved/allowed.

### 10.2 Reasons to reject

Reject if the candidate is:

- a one-off implementation detail;
- a temporary plan;
- too verbose;
- redundant;
- low-confidence;
- sensitive;
- session-specific;
- better as a skill;
- interesting but not broadly useful;
- already retrievable from session history.

### 10.3 Examples

Bad durable memory:

```md
- Ale discussed whether Hermes Dreaming should have review or auto mode.
```

Good durable memory:

```md
- Ale prefers simple, packaged, low-maintenance tools over custom infrastructure unless the custom route has a clear practical advantage.
```

Bad durable memory:

```md
- Ale asked about idle naps for Dreaming and then decided not to do them.
```

Good durable memory:

```md
- Ale is cost-sensitive about background agent tasks and prefers scheduled/manual runs over idle LLM activity.
```

---

## 11. Memory Mutation Strategy

### 11.1 Add

Use `add` rarely.

Add only when the candidate is premium and not represented by an existing entry.

Example:

```md
- Ale values agent memory that stays compact, current, and high-signal rather than verbose historical recall.
```

### 11.2 Replace

Prefer `replace` over `add` when a new memory updates or improves an existing one.

Example:

Old:

```md
- Ale is considering OpenClaw as his primary personal assistant.
```

New:

```md
- Ale currently prefers Hermes as his primary assistant because it is simpler and more packaged; OpenClaw remains interesting mainly for advanced memory experiments.
```

### 11.3 Remove

Use `remove` when an entry is clearly obsolete, false, superseded, redundant, or low-value.

Example:

Old:

```md
- Ale likes eating meat.
```

New evidence:

```text
Ale became vegetarian.
```

Action:

- remove old memory if it is no longer useful;
- or replace with current truth:

```md
- Ale currently follows a vegetarian diet.
```

Do not preserve obsolete historical detail in premium memory unless history itself is useful.

Session history already preserves the past.

### 11.4 Merge

If several entries describe the same stable preference, merge into one compact canonical entry.

Example:

Old:

```md
- Ale likes simple tools.
- Ale prefers packaged solutions.
- Ale avoids overengineering agent infrastructure.
```

New:

```md
- Ale prefers simple, packaged, low-maintenance systems over custom infrastructure unless custom work provides a clear advantage.
```

---

## 12. Scoring Model

The exact weights can be adjusted, but the plugin should score candidates using a model like this:

```text
score =
  future_usefulness
+ stability
+ recurrence
+ explicitness
+ correction_signal
+ compression_value
- character_cost
- duplication
- volatility
- sensitivity
```

### 12.1 Suggested dimensions

#### `future_usefulness`

Will this improve future answers often?

#### `stability`

Is it likely to remain true?

#### `recurrence`

Has it appeared across multiple sessions/turns?

#### `explicitness`

Did the user say it directly?

#### `correction_signal`

Did the user correct the assistant or clarify a preference?

Corrections should be strong signals.

#### `compression_value`

Does this compactly summarize many observations?

#### `character_cost`

How much prompt budget will it consume?

#### `duplication`

Is it already covered?

#### `volatility`

Is it likely to change soon?

#### `sensitivity`

Does it involve sensitive personal attributes?

### 12.2 Durable mutation thresholds

Suggested defaults:

```text
add:
  score >= 0.88

replace:
  score >= 0.80
  and supersession confidence >= 0.75

remove:
  obsolete/redundant/superseded confidence >= 0.85

merge:
  duplicate/overlap confidence >= 0.80
  and merged entry is shorter or clearer
```

### 12.3 Run-level limits

Suggested hard limits:

```text
max_changes_per_run = 3
max_adds_per_run = 1
max_new_chars_per_run = 250
```

If a run has more candidates, prioritize:

1. replacing contradictions/superseded entries;
2. merging duplicates;
3. adding one exceptional memory.

---

## 13. Memory Hints

### 13.1 Purpose

Memory hints exist to help future consolidation.

They should help the plugin and Hermes decide:

- what is current;
- what is superseded;
- what is low-value;
- what was promoted by Dreaming;
- what has high/low retrieval value;
- what sources support a memory.

### 13.2 Default behavior

Default:

```yaml
write_memory_hints: false
```

Full hints should be stored in sidecar files, not inline.

Reason: Hermes memory is tiny and inline metadata consumes prompt budget.

### 13.3 Sidecar hint schema

Example JSONL entry:

```json
{
  "id": "drm_20260501_001",
  "target": "user",
  "text": "Ale prefers simple, packaged, low-maintenance tools over custom infrastructure unless the custom route has a clear advantage.",
  "status": "active",
  "retrieval_priority": 0.92,
  "score": 0.91,
  "promoted_at": "2026-05-01T03:00:00Z",
  "last_seen": "2026-05-01T03:00:00Z",
  "recall_count": 4,
  "sources": ["session:abc123", "session:def456"],
  "operation": "add"
}
```

### 13.4 Allowed statuses

Use a small vocabulary:

```text
active
stale
superseded
archived
removed
```

#### `active`

Still current and useful.

#### `stale`

Possibly outdated or unused, but not clearly replaced.

#### `superseded`

Replaced by a newer/better memory.

#### `archived`

Kept for historical/audit context in sidecar, not premium memory.

#### `removed`

Removed from durable memory by Dreaming.

### 13.5 Inline hints

If `write_memory_hints: true`, inline hints should be compact.

Example:

```md
<!--drm:id=250501a;s=.91;p=.92;st=active-->
- Ale prefers simple, packaged, low-maintenance tools over custom infrastructure unless the custom route has a clear advantage.
```

Do not write verbose YAML/JSON comments inside `MEMORY.md`.

---

## 14. `DREAMS.md` Format

`DREAMS.md` is the human-readable audit diary.

It should not be used as a promotion source.

Suggested format:

```md
# DREAMS.md

## 2026-05-01 03:00 — Nightly Dream

### Light Sleep
- Scanned 14 recent sessions.
- Staged 12 candidates.
- Deduped 4 repeats.

### REM Sleep
Recurring themes:
- Preference for simple packaged systems.
- Concern about background token costs.
- Interest in premium-memory consolidation.

### Deep Sleep
Memory operations:
1. REPLACE user memory
   - Old: Ale is considering OpenClaw as primary assistant.
   - New: Ale currently prefers Hermes as primary assistant because it is simpler and more packaged; OpenClaw remains interesting mainly for advanced memory experiments.
   - Reason: newer explicit preference supersedes older evaluation.

2. ADD user memory
   - New: Ale is cost-sensitive about background agent tasks and prefers scheduled/manual runs over idle LLM activity.
   - Reason: stable preference likely to affect future assistant architecture decisions.

Rejected:
- Detailed discussion of `apply_mode` was too implementation-specific.
- OpenClaw/QMD/Graphiti architecture details belong in session history or project docs, not premium memory.

Summary:
- 2 durable memory changes applied.
- 10 candidates rejected.
```

---

## 15. Safety and Trust

### 15.1 Sensitive information

Do not persist or infer sensitive personal attributes unless:

- the user explicitly asks to remember them;
- or the information is already explicitly present in memory and the plugin is updating/removing it.

Sensitive areas include:

- health;
- sexuality;
- political affiliation/opinions;
- religion;
- precise location;
- criminal history;
- financial secrets;
- credentials;
- private relationship details.

### 15.2 Untrusted content

The plugin must treat web/email/document content as untrusted.

Do not promote untrusted content into durable memory unless:

- it is clearly grounded;
- it is not an instruction to the agent;
- it is relevant to the user;
- it passes safety checks;
- it is not prompt injection.

### 15.3 Source grounding

Every proposed memory operation should include sources in sidecar state.

At minimum:

```json
{
  "sources": ["session:<id>", "turn:<id>"]
}
```

### 15.4 Backups

Before mutating `MEMORY.md` or `USER.md`, create a timestamped backup.

Example:

```text
~/.hermes/dreaming/backups/2026-05-01T03-00-00/
├── MEMORY.md
└── USER.md
```

### 15.5 Idempotence

Repeated runs over the same data should not repeatedly add the same memory.

Use:

- source IDs;
- candidate hashes;
- duplicate detection;
- operation logs.

---

## 16. Interaction with External Memory Providers

The plugin must work whether or not a memory provider is active.

### 16.1 With Honcho

If Honcho is active, `hermes-dreaming` should not replace or duplicate Honcho.

Honcho can continue to provide user modeling and semantic memory. The Dreaming plugin focuses on Hermes' built-in premium memory.

Potential optional behavior:

- read provider status if available;
- avoid adding detailed facts that are better handled by provider memory;
- promote only the most stable/user-visible facts into `USER.md` / `MEMORY.md`.

### 16.2 With Hindsight / Supermemory / others

Same principle:

- provider = broader long-term memory;
- `MEMORY.md` / `USER.md` = always-prompt-visible premium memory;
- Dreaming = curator of premium memory.

---

## 17. Scheduling

### 17.1 Default

Default schedule:

```text
0 3 * * *
```

### 17.2 No idle runs

Do not implement idle naps.

Reason:

- idle runs can create hidden token cost;
- memory consolidation should be predictable;
- scheduled/manual runs are easier to audit.

### 17.3 Manual runs

Manual runs are important for development:

```text
/dreaming review
/dreaming run
/dreaming compact
```

---

## 18. Implementation Plan

### Phase 1 — Basic plugin skeleton

Deliver:

- `plugin.yaml`;
- `__init__.py`;
- command registration;
- state directory creation;
- `/dreaming status`;
- `/dreaming review` stub;
- `/dreaming run` stub.

Acceptance:

- plugin installs and enables normally;
- commands are available in CLI/gateway sessions;
- state directory is created;
- no memory mutations yet.

### Phase 2 — Memory and session readers

Deliver:

- read current `MEMORY.md` and `USER.md`;
- inspect usage/capacity if available;
- retrieve recent sessions via Hermes APIs/tools if available;
- fallback to direct SQLite/session access only if acceptable and stable.

Acceptance:

- `/dreaming review` can list current memory entries and recent sessions.

### Phase 3 — Light phase

Deliver:

- candidate extraction from recent sessions;
- deduplication;
- source grounding;
- candidate JSONL storage;
- Light section in `DREAMS.md`.

Acceptance:

- no durable memory writes;
- staged candidates include type, text, sources, confidence.

### Phase 4 — REM phase

Deliver:

- theme extraction;
- contradiction detection against current memory;
- supersession detection;
- skill-vs-memory classification;
- REM section in `DREAMS.md`.

Acceptance:

- no durable memory writes;
- outputs are useful and readable.

### Phase 5 — Deep phase review

Deliver:

- scoring;
- proposed operations:
  - add;
  - replace;
  - remove;
  - merge via replace;
- `/dreaming review` dry-run report.

Acceptance:

- no durable memory writes in review mode;
- proposals include source, score, reason, old/new text.

### Phase 6 — Deep phase apply

Deliver:

- backup memory files before change;
- apply memory operations via Hermes memory tool if possible;
- fallback direct file editing only if tool access is not available or unsuitable;
- write operation logs.

Acceptance:

- `/dreaming run` applies at most `max_changes_per_run`;
- idempotent repeated runs;
- backups are created;
- `DREAMS.md` records changes.

### Phase 7 — Scheduled run integration

Deliver:

- setup instructions for cron;
- optional helper command to create scheduled Dreaming job;
- no recursive scheduling.

Acceptance:

- nightly run works;
- run result is visible in configured output/logs;
- failures are logged.

### Phase 8 — Optional memory hints

Deliver:

- sidecar hints always;
- inline hints only if `write_memory_hints: true`;
- compact inline format.

Acceptance:

- inline hints do not exceed compact format;
- default memory stays clean.

---

## 19. Suggested Prompt Templates

### 19.1 Light extraction prompt

```text
You are extracting candidate memory signals for Hermes Dreaming.

Hermes durable memory is extremely scarce and always prompt-visible.
Do not summarize the session.
Extract only compact candidates that may affect future responses.

Return JSON candidates with:
- type
- candidate_text
- source_turns
- confidence
- explicitness
- recurrence_hint
- why_future_useful
- why_not_ephemeral
```

### 19.2 REM reflection prompt

```text
You are reflecting on staged memory candidates.

Find:
- recurring themes
- corrections from the user
- stable preferences
- contradicted/superseded memories
- candidates that are too ephemeral
- candidates that belong in skills instead of memory

Do not propose verbose memories.
Prefer compact canonical phrasing.
```

### 19.3 Deep scoring prompt

```text
You are deciding whether to mutate Hermes premium memory.

Hermes MEMORY.md and USER.md are very small and always injected into the prompt.

Optimize for future usefulness per character.

Allowed operations:
- add
- replace
- remove
- no-op

Prefer no-op or replace over add.
Only add if the candidate deserves to be present in almost every future session.

For each proposed operation, include:
- operation
- target: memory or user
- old_text if replacing/removing
- new_text if adding/replacing
- score
- reason
- source_ids
```

---

## 20. Acceptance Criteria

The plugin is successful if:

- it runs as a normal Hermes plugin;
- it does not require a new memory provider;
- it does not require external infrastructure;
- it can run manually and on cron;
- it writes a useful `DREAMS.md`;
- it makes durable memory changes rarely and carefully;
- it can replace superseded memories;
- it can merge duplicate/redundant entries;
- it can remove clearly obsolete entries;
- it avoids appending low-value memories;
- it keeps `MEMORY.md` / `USER.md` compact;
- it produces auditable backups/logs;
- it remains compatible with Honcho or any other external memory provider.

---

## 21. Key Design Tests

### Test 1 — Superseded preference

Input memory:

```md
- User likes eating meat.
```

Recent session:

```text
User: I became vegetarian. Please take that into account from now on.
```

Expected operation:

```text
replace
```

New memory:

```md
- User currently follows a vegetarian diet.
```

### Test 2 — Temporary implementation detail

Recent session:

```text
User discussed whether Dreaming should expose apply_mode=review or auto.
```

Expected:

```text
no-op
```

Reason:

- too implementation-specific;
- not likely to matter broadly;
- session history is enough.

### Test 3 — Stable meta-preference

Recent repeated signal:

```text
User repeatedly prefers packaged, low-maintenance systems over custom architecture unless custom work has clear practical value.
```

Expected:

```text
add or replace
```

Memory:

```md
- User prefers simple, packaged, low-maintenance systems over custom infrastructure unless the custom route has a clear practical advantage.
```

### Test 4 — Duplicate merge

Input memory:

```md
- User likes simple tools.
- User prefers packaged solutions.
- User avoids overengineering agent infrastructure.
```

Expected:

```text
replace/merge
```

New memory:

```md
- User prefers simple, packaged, low-maintenance systems over custom infrastructure unless custom work provides a clear advantage.
```

### Test 5 — Existing memory almost full

If memory usage is above 80%:

Expected behavior:

- prefer replace/merge/remove;
- avoid add unless exceptional;
- report capacity pressure in `DREAMS.md`.

---

## 22. Documentation Notes for Implementer

The implementation should verify current Hermes APIs before coding. Specifically check:

- plugin command registration;
- hook registration;
- access to memory tool or memory manager;
- access to session search/session store;
- cron job creation;
- gateway command compatibility;
- filesystem paths for `MEMORY.md` / `USER.md`.

Avoid direct file mutation if Hermes exposes stable APIs for memory operations.

If direct file mutation is required, implement:

- file locks;
- backups;
- exact diff logs;
- atomic writes.

---

## 23. References

### Hermes

- Persistent Memory: https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
- Plugins: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
- Cron/Scheduled Tasks: https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
- Memory Providers: https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers

### OpenClaw

- Dreaming: https://docs.openclaw.ai/concepts/dreaming
- Memory Overview: https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md

---

## 24. One-Line Summary

`hermes-dreaming` should be a simple Hermes plugin that ports the spirit of OpenClaw Dreaming into Hermes by curating scarce premium memory — promoting very little, replacing what is superseded, merging what is redundant, and keeping durable prompt memory compact, current, and high-signal.
