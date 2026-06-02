# ADR-0013: Cache-Aware Append-Only Context Rendering

> Status: accepted
> Date: 2026-06-02
> Related: [Context Manager](../architecture/context-manager.md), [Context Manager 1.0 Plan](../plans/feature/context-manager-1-0.md), [Context Manager 1.0 Technical Design](../plans/feature/context-manager-1-0-technical-design.zh-CN.md), [ADR-0006](ADR-0006-llm-provider-transport-boundary.md), [ADR-0010](ADR-0010-line-first-authoring-experience-for-1-0.md)

---

## Context

Context Manager 1.0 introduced the correct architectural boundary: it is the
component responsible for deciding the final input sent to the stateless LLM API.
The accepted implementation renders a full structured execution context before
`llm.chat(...)`.

The current rendering shape is cache-hostile:

```text
system
full regenerated task execution context
prior AgentLoop messages
```

The full context contains high-churn fields near the front of the request:

- `task_id`, `root_task_id`, `parent_task_id`;
- status and claim state;
- event ids, observation ids, and raw refs;
- recent tool results;
- selected file snippets;
- trace/snapshot-derived references.

Prompt caching uses maximum prefix matching. When volatile fields appear before
the execution transcript, the stable prefix ends quickly. In observed Product
1.0 usage, cache hit rate can fall below 10%.

The previous AgentLoop shape had much better cache behavior because it was
naturally append-only:

```text
turn 1: system, task
turn 2: system, task, assistant_1, tool_1
turn 3: system, task, assistant_1, tool_1, assistant_2, tool_2
```

Each call reused the previous call as a prefix and appended new messages. Cache
hit rates near 90% are plausible for this pattern on multi-step tasks.

Context governance must not destroy this useful property. The goal is not to
return to unmanaged prompts. The goal is for Context Manager to govern the
append-only transcript rather than replacing it with a regenerated full context
on every call.

---

## Decision

Context Manager will use **cache-aware append-only rendering** for Product 1.0
execution calls.

Context Manager remains the owner of final LLM input assembly, but its rendering
strategy changes from "full context before every call" to:

```text
stable start context
append-only execution transcript
minimal context deltas
periodic context checkpoints
```

### 1. Stable Start Context

At the start of a Task run, Context Manager emits stable prefix messages:

- system prompt;
- Context Manager contract;
- stable project/session rules;
- stable output requirements;
- stable Task brief, including original target and durable constraints.

These messages should remain byte-stable for the same Task run whenever the
underlying facts have not changed.

Volatile ids and timestamps should not appear in this stable prefix unless they
are required for model behavior. Exact provenance belongs in snapshots, traces,
Audit, and logs.

### 2. Append-Only Execution Transcript

After the stable start context, AgentLoop messages remain append-only:

- assistant messages;
- tool calls;
- tool observations;
- user confirmations;
- interruption/retry messages;
- explicit system/runtime observations needed by the model.

Context Manager must preserve provider tool-call protocol ordering. It must not
reorder or rewrite previous assistant/tool messages just to refresh context.

### 3. Minimal Context Delta

On ordinary turns, Context Manager may append a short context delta when there
is new information that affects the next decision:

- latest user instruction;
- pending approval;
- interruption request;
- important tool error;
- important file change summary;
- newly relevant workspace evidence.

The delta is appended near the end of the message list. It does not replace the
stable prefix or the existing transcript.

### 4. Periodic Context Checkpoint

Every N execution steps, or after important lifecycle changes, Context Manager
appends a checkpoint message.

The first Product 1.0 implementation should start with a simple default such as
`checkpoint_interval_steps = 5`. The value can become configurable later.

Checkpoint triggers include:

- step interval reached;
- retry begins;
- interruption requested or resolved;
- confirmation resolved;
- repeated tool errors;
- file changes exceed a small threshold;
- context budget pressure requires a compact current-state reminder.

Checkpoint content should be compact:

- current objective;
- completed facts;
- important observations;
- pending approvals or open questions;
- files changed;
- recommended next step.

Checkpoint content should not include:

- large file content;
- full event or tool-result history;
- raw `event_id` / `observation_id` / `trace_id` lists;
- repeated task goal text when the stable prefix already contains it.

### 5. Snapshot And Trace Remain Complete

LLM input is not the audit record.

Context Manager should still persist enough snapshot and trace data to explain
why a call saw a specific input. Snapshot/trace records may include provenance
and ids that are intentionally omitted from the prompt prefix.

The prompt should contain what the model needs to act. Audit/diagnostics should
contain what the system needs to explain and replay.

---

## Consequences

Positive:

- Preserves Context Manager as the single owner of LLM input assembly.
- Restores the cache-friendly property of append-only AgentLoop execution.
- Expected cache hit rate for multi-step tasks should improve materially, with
  70%-90% cached-token ratios plausible when tasks mostly append tool/assistant
  transcript and avoid large new file snippets.
- Reduces input prefill latency and cached-token cost when the provider supports
  prefix caching.
- Keeps model-visible execution history in causal order.
- Avoids using LLM prompt content as an audit dump.

Negative:

- Context rendering becomes stateful across a Task run.
- Tests must verify stable-prefix invariants and tool-call ordering.
- A sparse delta can hurt model quality if it omits important current state.
- Checkpoint policy introduces another tuning surface.
- Cache hit rate remains provider-dependent and should be measured through
  provider metadata where available.

Neutral:

- This decision does not add semantic retrieval, vector search, long-term
  memory, custom user context policies, MCP context expansion, or multimodal
  packing.
- This decision does not require changing TaskBus authority, EventStream facts,
  or workspace ownership.

---

## Implementation Guidance

The implementation should be incremental:

1. Add explicit render modes or segment metadata for:
   - `start_context`;
   - `delta_context`;
   - `checkpoint_context`.
2. Make the AgentLoop context provider preserve the append-only transcript after
   the start context is established.
3. Append delta/checkpoint messages instead of replacing the existing context
   prefix on every call.
4. Keep snapshot/trace persistence independent from what is included in the
   prompt.
5. Add tests for:
   - stable prefix equality across repeated calls with unchanged stable facts;
   - volatile ids absent from the stable prefix;
   - delta/checkpoint messages appended rather than inserted before transcript;
   - OpenAI-style assistant/tool-call protocol ordering preserved;
   - rendered input still contains necessary current-state facts.

The first Product 1.0 hardening slice should avoid advanced deduplication,
semantic selection, or compression. Those can be layered later after the
append-only rendering contract is stable.

---

## Alternatives Considered

### Keep Full Context Regeneration

This keeps the implementation simple and makes each call self-contained, but it
breaks prompt-cache prefix matching and repeats volatile facts near the front of
every request.

Rejected for Product 1.0 hardening.

### Only Reorder Full Context By Stability

Moving stable fields earlier would improve cache behavior somewhat, but the
renderer would still rewrite a large context block on every call. It would not
recover the old AgentLoop's append-only cache behavior.

Rejected as insufficient.

### Provider-Specific Prompt Cache Controls

Some providers may expose prompt-cache controls or metadata. Those can help
measurement, but they do not solve the architectural issue. The transcript
shape should be cache-friendly before adding provider-specific optimizations.

Deferred.

---

## Follow-Up Work

- Update Context Manager architecture and plan docs to reference this ADR.
- Implement cache-aware rendering as a Product 1.0 hardening slice.
- Add provider metadata logging for cached-token ratio and prefill latency when
  available.
- Later Product 1.1 work may add context delta deduplication, file snippet
  late injection, event digesting, semantic retrieval, and compression.
