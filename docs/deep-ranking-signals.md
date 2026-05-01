# Deep Ranking Signals

The Deep phase scores each candidate memory operation on a composite 0.0–1.0 scale before deciding whether to promote, replace, merge, or remove an entry. The score is computed holistically by the agent's LLM using the dimensions below — no fixed weights are applied, which allows contextual emphasis (a `correction_signal` on a factual error carries more weight than one on a stylistic preference).

Hard threshold gates are enforced by `dreaming_apply_memory_op` regardless of holistic score:

| Operation | Score threshold | Extra gate |
|---|---|---|
| `add` | ≥ 0.88 | Entry must improve future sessions across many different task types |
| `replace` | ≥ 0.80 | `supersession_confidence` ≥ 0.75 |
| `remove` | — | `supersession_confidence` ≥ 0.85 |
| `merge` (as replace) | ≥ 0.80 | `supersession_confidence` ≥ 0.80 |

## Positive signals

### `future_usefulness`
Will this memory improve future answers often? This is the primary signal: a memory that rarely surfaces in responses is not worth the permanent prompt budget it consumes.

### `query_diversity`
How many *different types* of future tasks or questions benefit from this memory? A fact that helps only with one narrow category of question is less valuable than one that crosses domains. This is breadth, not just frequency — a memory that appears in every session but only for one task type scores lower here than one that helps with coding, planning, writing, and debugging alike.

### `stability`
Is this memory likely to remain true over time? Stable facts (long-term preferences, consistent working styles, persistent constraints) are preferred over observations that are likely to become outdated within weeks or months.

### `recurrence`
Has this signal appeared across multiple sessions? A pattern seen once is speculative; one seen across many sessions over time is structural. Single-session observations require strong explicitness or correction_signal to compensate.

### `recency`
How recently did this signal last appear? A pattern seen last week outweighs one from six months ago with no reinforcement. Recency is bounded — it is a tie-breaker between otherwise equal candidates, not a standalone promotion signal.

### `explicitness`
Did the user state this directly? Explicit user statements ("I prefer X", "always do Y") are more reliable than inferred patterns. A score of 1.0 means the user said it in plain language; lower values indicate the signal was derived from behaviour or context.

### `correction_signal`
Did the user correct the assistant because of a missing or wrong memory? Corrections are the strongest possible signal that a memory is needed. A user rephrasing the same preference for the third time after the assistant ignores it should almost always result in promotion.

### `actionability`
Will knowing this actually change what the assistant says or does? Pure context that never alters a response — interesting background that the assistant would behave identically without — is low-value regardless of how frequently it appears. Memories must earn their prompt budget by changing behaviour.

### `compression_value`
Does this entry compactly summarise many observations into one canonical fact? High compression value means the entry replaces several weaker signals with a single durable one, reducing total memory footprint while preserving the information.

## Negative signals

### `character_cost`
How much prompt budget will this entry consume? Every character in `MEMORY.md` or `USER.md` has a permanent per-session token cost. Verbose entries are penalised even if their content is useful; the same information expressed more compactly scores better.

### `duplication`
Is this already covered by an existing memory entry? Partial or full overlap with current memory is a strong rejection signal. The Deep phase should prefer `replace` or `merge` over `add` when any existing entry covers the same ground.

### `volatility`
Is this memory likely to change soon? High-volatility observations (current project status, temporary constraints, in-progress decisions) belong in session history, not durable memory. Volatility is the inverse of stability.

### `sensitivity`
Does this involve sensitive personal attributes? Health information, religion, political views, precise location, credentials, and private financial details must not be promoted into durable memory. This is a near-absolute disqualifier regardless of other scores.

## Relation to OpenClaw's model

This model was designed alongside OpenClaw's Dreaming system. The table below maps overlapping signals:

| OpenClaw signal | Weight | Equivalent here |
|---|---|---|
| Relevance | 0.30 | `future_usefulness` |
| Frequency | 0.24 | `recurrence` |
| Query diversity | 0.15 | `query_diversity` |
| Recency | 0.15 | `recency` |
| Consolidation | 0.10 | `compression_value` |
| Conceptual richness | 0.06 | partially `compression_value` |

Signals present here but not in OpenClaw's model: `stability`, `volatility`, `explicitness`, `correction_signal`, `actionability`, `character_cost`, `duplication`, `sensitivity`. These reflect the additional conservatism required when memory is strictly prompt-visible and every character has a token cost.

Unlike OpenClaw, no fixed weights are applied. The agent's LLM applies contextual weighting, which allows the relative importance of signals to shift based on the specific candidate and existing memory state.
