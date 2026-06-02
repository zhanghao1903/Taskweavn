# Release: Context Manager Cache-Aware Rendering

> Status: done / accepted for Product 1.0 Context Manager hardening
> Date: 2026-06-02
> Work Stream: Product 1.0 execution context performance and latency hardening / P9 closure
> Related Plan: [Context Manager Cache-Aware Rendering](../plans/feature/context-manager-cache-aware-rendering.md)
> Technical Design: [Context Manager Cache-Aware Rendering 详细技术方案](../plans/feature/context-manager-cache-aware-rendering-technical-design.zh-CN.md)
> Architecture: [Context Manager](../architecture/context-manager.md), [Architecture Overview](../architecture/overview.md)
> Decision: [ADR-0013](../decisions/ADR-0013-cache-aware-append-only-context-rendering.md)
> Implementation Commit: `2dcfe3f`

---

## 1. Summary

This release closes the Product 1.0 cache-aware rendering hardening slice for
Context Manager.

Context Manager remains the only owner of final LLM input assembly. The runtime
shape now preserves append-only AgentLoop execution:

```text
stable start context
append-only assistant/tool transcript
bounded context delta messages
periodic context checkpoint messages
```

The goal is structural prompt-cache friendliness: later `llm.chat(...)` calls
preserve the previous request as the prefix whenever ordinary execution only
appends assistant/tool/context messages. DeepSeek official provider usage now
parses cache hit/miss tokens when the API returns them; cross-provider cache
aggregation and prefill-latency reporting remain follow-ups.

---

## 2. Release Scope

### 2.1 Renderer And Models

- Added `start_context`, `delta_context`, and `checkpoint_context` render modes.
- Added stable prefix and segment hash metadata.
- Added compact delta and checkpoint renderers.
- Kept volatile provenance out of the stable start context while preserving
  snapshot and trace records.

### 2.2 Provider And AgentLoop Integration

- Added cache-aware provider run state per `agent_run_id`.
- Added `AgentLoopContextCallResult` so the Context Manager provider can return:
  - exact messages for the current LLM call;
  - messages that must persist back into AgentLoop state;
  - render mode, prefix hash, delta/checkpoint reason, and appended message
    count metadata.
- Updated `AgentLoop` to persist provider-returned messages before
  `llm.chat(...)`.
- Preserved no-provider AgentLoop behavior for tests and non-sidecar callers.

### 2.3 Checkpoint And Delta Policy

- Implemented Product 1.0 interval checkpoints with default
  `checkpoint_interval_steps = 5`.
- Added a trigger evaluator interface for later delta/checkpoint triggers.
- Kept retry, interruption, repeated tool errors, file-change thresholds, and
  budget pressure as follow-up trigger integrations.

### 2.4 Observability Hooks

Each context-governed LLM call can now carry:

- `context_render_mode`;
- `context_stable_prefix_hash`;
- `context_rendered_input_hash`;
- `context_appended_message_count`;
- `context_checkpoint_reason`;
- `context_delta_reason`;
- context snapshot and trace ids.

These hooks allow later provider metadata to be correlated with Context Manager
rendering strategy.

### 2.5 DeepSeek Cache Usage Parsing

The OpenAI-compatible response parser now reads DeepSeek's official usage
fields when present:

- `prompt_cache_hit_tokens`;
- `prompt_cache_miss_tokens`.

It maps them into provider-neutral usage fields:

- `cache_hit_tokens`;
- `cache_miss_tokens`;
- `cache_hit_ratio`;
- `cached_tokens` as the existing compatibility alias for hit tokens.

---

## 3. Validation

Release validation included:

- `git diff --check`
  - passed
- `uv run ruff check tests/test_loop.py tests/test_context_manager.py src/taskweavn/context src/taskweavn/core/loop.py`
  - passed
- `uv run ruff format --check src/taskweavn/context/__init__.py src/taskweavn/context/agent_loop_provider.py src/taskweavn/context/manager.py src/taskweavn/context/models.py src/taskweavn/context/renderer.py src/taskweavn/core/loop.py tests/test_context_manager.py tests/test_loop.py`
  - passed
- `uv run mypy src/taskweavn/context src/taskweavn/core/loop.py tests/test_context_manager.py tests/test_loop.py`
  - passed
- `uv run pytest tests/test_context_manager.py tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_main_page_sidecar_app.py`
  - 72 passed, 1 dependency warning
- `uv run pytest tests/test_llm_providers.py`
  - passed

Covered behavior:

- stable start-context prefix hash remains stable when volatile ids change;
- volatile trace/event/observation ids are excluded from stable prompt prefix;
- delta and checkpoint messages are compact and explicitly marked;
- interval checkpoint messages append to the existing transcript;
- trigger evaluator interface can append future delta messages;
- AgentLoop persists provider-returned context messages before `llm.chat(...)`;
- a loop-level observation test proves start -> checkpoint -> ordinary reuse
  preserves the previous request as the next request prefix.
- DeepSeek official `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`
  usage fields are parsed into provider-neutral cache hit/miss metrics.

---

## 4. Follow-ups After Acceptance

- Add cross-provider cache metric aggregation and prefill-latency logging when
  available.
- Connect interruption, retry, confirmation, repeated tool error, file-change,
  and budget-pressure triggers through the trigger evaluator interface.
- Validate the cache-aware path through a normal sidecar/browser smoke once the
  broader Product 1.0 QA pass runs.
- Keep semantic retrieval, compression, skill context, MCP context, multimodal
  packing, user-configurable policies, and multi-Agent context merging in
  Product 1.1+.
