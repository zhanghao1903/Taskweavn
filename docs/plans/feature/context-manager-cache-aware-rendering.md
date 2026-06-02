# Feature Plan: Context Manager Cache-Aware Rendering

> Status: planned
> Type: Product 1.0 Context Manager performance and latency hardening
> Last Updated: 2026-06-02
> ADR: [ADR-0013 Cache-Aware Append-Only Context Rendering](../../decisions/ADR-0013-cache-aware-append-only-context-rendering.md)
> Architecture: [Context Manager](../../architecture/context-manager.md)
> Related Plan: [Context Manager 1.0](context-manager-1-0.md)
> Technical Design: [Context Manager cache-aware rendering technical design](context-manager-cache-aware-rendering-technical-design.zh-CN.md)

---

## 1. Problem

Context Manager 1.0 is accepted as the LLM input governance boundary for the
fixed-route Default Agent path. The current implementation builds a full
structured execution context before each `llm.chat(...)` call:

```text
system
full regenerated task execution context
prior AgentLoop messages
```

This is architecturally correct but cache-hostile. Prompt caching is based on
maximum prefix matching. High-churn task ids, status facts, event ids,
observation ids, file refs, tool results, and trace refs appear before the
append-only execution transcript. In observed Product 1.0 usage, cached-token
hit rate can fall below 10%.

The previous unmanaged AgentLoop shape was naturally append-only:

```text
system
task
assistant/tool transcript appended step by step
```

That shape can achieve much higher prefix reuse because every later request
reuses the previous request as its prefix and appends only new messages.
Context Manager should preserve this property while still owning final LLM
input assembly.

---

## 2. Product Decision

This is Product 1.0 hardening, not Product 1.1 advanced context strategy.

Context Manager remains the single owner of LLM input assembly, but it should
govern an append-only transcript:

```text
stable start context
append-only execution transcript
minimal context deltas
periodic context checkpoints
```

The implementation should avoid semantic retrieval, compression, vector memory,
custom policies, MCP expansion, and multimodal packing. Those remain Product
1.1+ extension areas.

---

## 3. Goals

1. Preserve a byte-stable prefix for a Task run when stable facts do not
   change.
2. Keep assistant/tool messages append-only after the start context.
3. Append short context deltas only when new facts affect the next decision.
4. Append compact checkpoints at a low frequency, with a Product 1.0 default
   such as every five execution steps.
5. Keep OpenAI-style assistant/tool-call ordering valid.
6. Keep snapshots and traces complete even when prompt content omits volatile
   provenance.
7. Expose render-mode and prefix-hash metadata so cache behavior can be
   measured through provider metadata later.
8. Improve expected cached-token ratio for multi-step execution tasks to a
   materially useful range. The target for follow-up measurement is 70%+
   cached-token ratio on typical multi-step tasks that do not inject large new
   file snippets every turn.

---

## 4. Non-goals

- No semantic retrieval, vector index, or LLM-ranked context selection.
- No cross-session prompt-cache reuse.
- No provider-specific prompt-cache API dependency.
- No user-configurable context strategy UI.
- No custom Agent protocol or Agent Manager change.
- No MCP, skills, or multimodal context expansion.
- No large file-content late injection beyond the existing bounded file
  snippet policy.
- No use of LLM prompt content as the audit record.

---

## 5. Implementation Anchors

| Surface | Current Role | Required Change |
|---|---|---|
| `src/taskweavn/context/renderer.py` | Renders one full `RenderedLlmInput`. | Add start, delta, and checkpoint render modes or segment metadata. |
| `src/taskweavn/context/models.py` | Defines Context Manager request/result/snapshot models. | Add render-mode, segment, prefix-hash, and provider call-result contracts. |
| `src/taskweavn/context/agent_loop_provider.py` | Replaces loop-local first messages with full rendered context on each call. | Preserve run state and append delta/checkpoint messages instead of regenerating the front of every request. |
| `src/taskweavn/core/loop.py` | Owns local `messages` and calls `llm.chat(...)`. | Allow the provider to return both call messages and persisted loop messages before the chat call. |
| `tests/test_context_manager.py` | Covers Context Manager primitives. | Add stable-prefix, delta, checkpoint, and volatile-field tests. |
| `tests/test_loop.py` | Covers AgentLoop behavior. | Add protocol-order and provider-persisted-message tests. |

---

## 6. Implementation Slices

### C1. Contract And Docs

Current status: in progress.

Deliver:

- ADR-0013 for the cache-aware rendering decision;
- this feature plan;
- the detailed technical design;
- feature-plan index entry.

Acceptance:

- docs state why full regeneration is cache-hostile;
- docs state that Context Manager still owns final LLM input;
- docs define start context, delta context, and checkpoint context;
- docs define that delta/checkpoint messages must be persisted into the local
  AgentLoop transcript.

### C2. Context Model And Renderer Segments

Deliver:

- render-mode or segment-kind models for:
  - `start_context`;
  - `delta_context`;
  - `checkpoint_context`;
- stable prefix hash and segment hash helpers;
- renderer methods for start, delta, and checkpoint content;
- updated snapshot/trace metadata.

Acceptance:

- repeated start-context renders with unchanged stable facts produce the same
  prefix hash;
- volatile ids, trace ids, event ids, and observation ids are excluded from the
  stable start context unless required for behavior;
- delta/checkpoint messages are compact and explicitly marked as context
  messages.

### C3. Provider State And Append-Only Transcript

Deliver:

- per `agent_run_id` provider state;
- a provider call result that can return:
  - the exact messages for the current LLM call;
  - the messages that should persist back into AgentLoop state;
  - metadata for snapshot, trace, render mode, and prefix hash;
- start-context initialization on the first call;
- no-op behavior on ordinary steps when no delta/checkpoint is needed.

Acceptance:

- `AgentLoop` local `messages` is updated before `llm.chat(...)` when Context
  Manager appends context messages;
- previous assistant/tool messages are not reordered or rewritten;
- no-provider AgentLoop behavior remains unchanged.

### C4. Checkpoint And Delta Policy

Deliver:

- Product 1.0 default checkpoint interval, initially five execution steps;
- a minimal policy that can trigger deltas/checkpoints for:
  - retry begin;
  - interruption requested or resolved;
  - pending confirmation resolved;
  - repeated tool errors;
  - file-change threshold;
  - budget-pressure fallback;
- a compact checkpoint renderer that summarizes objective, completed facts,
  pending decisions, file changes, and recommended next step.

Acceptance:

- interval checkpoints append near the end of the transcript;
- checkpoint content is bounded and does not include full event/tool history;
- sparse normal steps can reuse the previous request prefix without adding a
  regenerated context block.

### C5. Tests, Metrics Hooks, And Docs Closure

Deliver:

- unit tests for stable-prefix and volatile-field behavior;
- loop integration tests proving persisted delta/checkpoint messages;
- tool-call protocol ordering tests;
- metadata hooks for cached-token ratio and prefill-latency measurement when
  provider metadata is available;
- docs closure updates after implementation.

Acceptance:

- `uv run pytest tests/test_context_manager.py tests/test_loop.py` passes;
- existing fixed-route Default Agent tests pass;
- `git diff --check` passes;
- Product 1.0 docs state cache-aware rendering as the Context Manager runtime
  shape after implementation.

---

## 7. Acceptance Criteria

The feature is accepted when:

1. Every Product 1.0 Default Agent `llm.chat(...)` call still goes through
   Context Manager.
2. The first call establishes a stable start context.
3. Later calls preserve the previous request as a prefix unless a bounded
   delta/checkpoint must be appended.
4. Delta/checkpoint messages are persisted in the local AgentLoop transcript,
   not only passed as temporary call messages.
5. Assistant/tool-call protocol ordering remains valid.
6. Snapshots and traces remain complete enough for diagnostics and audit.
7. Render metadata includes enough hashes/modes to measure cache behavior.
8. Tests prove structural cache-friendliness even before provider-level cache
   metrics are available.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Too-sparse deltas degrade model quality. | Keep start context complete, add periodic checkpoints, and test current-state facts after checkpoints. |
| Provider mutates AgentLoop messages incorrectly. | Return explicit persisted messages and test protocol ordering. |
| Stable prefix accidentally includes volatile ids. | Add stable-prefix equality and volatile-field exclusion tests. |
| Checkpoints become too large and reduce cache benefit. | Bound checkpoint content and treat file content as references unless explicitly needed. |
| Cache improvement is provider-dependent. | Verify structural prefix behavior first, then add provider metadata measurement where available. |

---

## 9. Later Expansion

Product 1.1+ may add:

- context delta deduplication;
- semantic retrieval;
- file snippet late injection;
- skill and MCP context sources;
- multimodal context packing;
- compression and compaction policies;
- user-configurable context strategies.

