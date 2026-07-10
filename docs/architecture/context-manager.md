# Context Manager Architecture

> Status: fact-calibrated current architecture
>
> Last verified: 2026-07-10
>
> Original document:
> [context-manager.original.md](context-manager.original.md)
>
> Verification record:
> [fix-log/context-manager.md](fix-log/context-manager.md)
>
> Accepted baselines:
> [Context Manager 1.0](../releases/context-manager-1-0.md),
> [cache-aware rendering](../releases/context-manager-cache-aware-rendering.md),
> and [ADR-0013](../decisions/ADR-0013-cache-aware-append-only-context-rendering.md)

## 1. Purpose

The current Context Manager is the Task execution message-context layer for the
fixed-route Default Agent. It reads selected TaskBus, EventStream, ASK,
guidance, control, and tool-availability facts; builds
`TaskExecutionContextV0`; renders OpenAI-compatible chat messages; and stores a
context snapshot and trace for each build.

Its precise ownership is the LLM `messages` list. AgentLoop still owns and
passes tool schemas and call metadata, while the LLM/provider layer owns model,
thinking, timeout, retry, and transport behavior.

Context Manager does not own Task or workspace truth. Its snapshots and traces
are derived execution artifacts under session metadata.

## 2. Current Runtime Path

The normal local sidecar execution path is:

```text
Published TaskDomain
  -> FixedRouteTaskExecutor
  -> AgentLoopResidentDefaultAgent preflight context build
  -> task-scoped AgentLoop
  -> SessionAgentLoopContextProvider before every llm.chat call
  -> _SessionContextBuilder
  -> SessionContextManager
  -> TaskExecutionContextV0 + rendered messages
  -> AgentLoop passes messages + its tool schemas + metadata to llm.chat
```

Two context builds occur before the first normal LLM call:

1. `AgentLoopResidentDefaultAgent.run` performs an `execution_start` full
   context build. This is a preflight/failure gate and persists a snapshot and
   trace. Its rendered user content becomes the initial `AgentLoop.run` task
   input.
2. The cache-aware provider then performs an `execution_step` start-context
   build before the first `llm.chat`. It replaces the loop-local initial system
   and task messages with the stable start prefix used by the actual call.

Generic AgentLoop callers may omit a context provider. The sidecar-built
resident Default Agent uses one when a TaskBus is supplied.

## 3. Package Boundary

The implementation lives under `src/taskweavn/context/`:

```text
models.py               immutable contracts
sources.py              TaskBus, EventStream, ASK, controls, guidance sources
policy.py               deterministic trimming and candidate helper
renderer.py             full/start/reuse/delta/checkpoint message rendering
manager.py              build, render, snapshot, and trace orchestration
store.py                ContextStore protocol and in-memory store
sqlite_store.py         session-local durable snapshot/trace store
agent_loop_provider.py  cache-aware AgentLoop adapter and run state
```

Related production adapters are:

- `server/main_page_agent.py` for sidecar source assembly;
- `task/execution.py` for the preflight build;
- `core/loop.py` for the per-call seam;
- `contract_revision/context_source.py` for typed guidance facts;
- `skills/context_source.py` for an implemented but not sidecar-wired skill
  source.

## 4. Core Contracts

### 4.1 Build request and budget

`ContextBuildRequest` includes:

```text
session_id task_id agent_id agent_run_id purpose render_mode render_reason
writer turn_index budget runtime_config_hash latest_user_instruction
prior_messages
```

Purposes are `execution_start`, `execution_step`, `recovery`, and
`read_only_review`. Production fixed-route execution currently uses only
`execution_start` and `execution_step`.

`writer` is present in the model and is set to true by current execution calls,
but `SessionContextManager` does not read it or enforce writer exclusivity.
Purpose is persisted in the snapshot but does not currently change source or
policy behavior.

`ContextBudget` contains:

```text
max_events=20
max_tool_results=10
max_file_snippets=6
max_file_snippet_chars=8000
max_rendered_chars=60000
```

The first four selection limits have partial implementation. The rendered-char
limit is modeled and supplied from Runtime Config but is not read by manager or
renderer.

### 4.2 Task execution context

`TaskExecutionContextV0` contains:

- task identity;
- execution state;
- execution facts;
- controls;
- guidance;
- snapshot/trace reference.

The current Task source populates:

- task, session, parent, and root ids;
- `TaskDomain.intent` as `original_target`;
- required capability;
- status, claimant, a synthetic current step, latest request instruction, and
  active interruption fields.

It does not currently populate interpreted goal, success criteria, or non-goals
from richer TaskDomain fields.

### 4.3 Snapshot, trace, and rendered input

Each build produces:

- `RenderedLlmInput`: message list, system/user content, hashes, mode, and
  segment metadata;
- `ContextSnapshot`: structured context, ids, versions, render metadata, and
  final message-list hash;
- `ContextTrace`: policy/renderer ids, render metadata, segment hashes, runtime
  config hash, and optional Skill governance metadata.

The store persists snapshot and trace, not `RenderedLlmInput.messages`.
Therefore `context.sqlite` alone does not preserve the exact final message list
or prior AgentLoop transcript. It stores enough to identify a build and verify
its hash, but not to replay the complete LLM request independently.

## 5. Production Sources

### 5.1 Task source

`TaskContextSource` reads the requested `TaskDomain` from TaskBus. Missing Task
identity raises `ContextSourceError`. It maps active interrupt intent into
`InterruptionContext`.

### 5.2 Event source

The sidecar uses the session `SqliteEventStream` and task-filtered iteration.
For each event, the source builds a compact JSON summary that removes direct
`content`, `stdout`, and `stderr` values and records their character counts.

Every observation also becomes a `ToolResultSummary`. Web search observations
receive a special external-evidence summary with provider, query, result count,
retrieval metadata, and up to five URLs.

`FileContentObservation` additionally becomes a `FileSnippet`. Its content is
bounded before selection, hashed, marked as evidence rather than instruction,
and linked to the raw event.

### 5.3 ASK source

`AskContextSource` reads task-scoped ASKs whose status is pending or answered
and attaches the stored answer where present. Deferred, cancelled, and expired
statuses are representable by `AskFact` but are not selected by the current
source query.

ASK facts have no dedicated ContextBudget count or character limit.

### 5.4 Workspace evidence

`WorkspaceEvidenceContextSource` is implemented as a static tuple adapter. The
sidecar `_SessionContextBuilder` does not pass one, so the default production
workspace refs and extra file snippets are empty.

The current execution context does not automatically read Workspace Inspection
records, token-usage summaries, read-only Inquiry results, Agent LLM profile
metadata, or a workspace-wide index.

### 5.5 Controls

The sidecar supplies a static allowed-tool tuple based on assembled
capabilities: workspace file/search/edit tools, command execution, and optional
web search/fetch, computer use, ASK, and confirmation tools.

Current control facts do not read dynamic gate state. Denied tools,
`requires_approval`, pending approval, and file scopes are empty in the default
assembly. `AgentLoopContextRequest.tool_names` is collected by AgentLoop but is
not propagated into `ContextBuildRequest` or reconciled with the static control
source.

Actual tool schemas remain owned by AgentLoop and are passed separately to
`llm.chat`.

### 5.6 Guidance

Default guidance is generated when confirmation, web search/fetch, or computer
use is available. When a Contract Revision guidance store is configured, up to
20 task/session-scoped typed guidance facts are merged into project rules or
output requirements.

`SkillContextSource`, Skill segments, permission merge, and trace fields are
implemented and tested as library components. The current sidecar
`_SessionContextBuilder` does not supply a Skill source, so active Skill fields
are empty in normal fixed-route execution.

### 5.7 Unpopulated execution facts

The current sidecar source set does not populate:

- `changed_artifacts`;
- arbitrary `workspace_refs`;
- pending approval;
- structured `latest_user_instruction` in the fixed-route provider;
- interpreted goal, success criteria, or non-goals;
- active Skill segments.

Their presence in the schema is an extension seam, not evidence of current
runtime population.

## 6. Deterministic Policy

The manager uses `DeterministicContextPolicy` to keep the newest:

- `max_events` event summaries;
- `max_tool_results` tool-result summaries;
- `max_file_snippets` file snippets within a shared
  `max_file_snippet_chars` total.

The file source also truncates each explicit read observation to
`max_file_snippet_chars` before policy selection.

The policy contains a generic priority/token candidate selector, but
`SessionContextManager.build` does not call it. Current trace fields
`candidates_seen`, `candidates_selected`, and `candidates_excluded` are always
empty for manager builds.

Token estimates use a deterministic character approximation. They annotate
tool results/snippets and the unused generic candidate selector; there is no
aggregate LLM token budget enforcement.

## 7. Rendering Modes

### 7.1 Full context

The compatibility full renderer creates:

```text
system: AgentLoop system prompt + Context Manager contract
user:   full structured task execution context
prior messages
```

The preflight `execution_start` build uses this mode. The fallback
`build_for_llm_call` API also uses it and applies `_prior_messages`, which drops
the loop-local first two messages and caps the remainder.

### 7.2 Stable start context

The cache-aware first call emits two stable-prefix messages:

```text
system: AgentLoop system prompt + Context Manager contract
user:   stable task brief, controls, guidance, ASK facts, evidence rules
```

Volatile task/session/trace/event ids and runtime status are excluded from the
start user content. The provider records a hash of the two-message prefix.

### 7.3 Ordinary reuse

On an ordinary later turn, the provider still performs a full source build and
stores a new snapshot/trace. If no trigger fires, the renderer returns the
existing AgentLoop messages unchanged. It does not append a context message.

The existing transcript already contains assistant messages and complete tool
observation JSON produced by AgentLoop. This reused transcript is not trimmed
by the structured fact budgets.

### 7.4 Delta

A delta is a new system message appended to the transcript. Current production
delta triggering is limited to a newly observed interruption request during an
ordinary reuse check. Additional trigger evaluators are an injectable seam;
the pending-decision example exists only in tests.

Delta content can include latest instruction, interruption, pending approval,
pending/answered ASK facts, changed artifacts, and failed tool summaries. Only
facts populated by current sources can appear.

### 7.5 Checkpoint

At the configured interval, the provider appends one checkpoint system message.
The default interval is five AgentLoop steps; non-positive values disable the
interval trigger.

Checkpoint content includes objective/status, current step, bounded recent tool
summaries, ASK facts, file/workspace refs, changed-artifact refs, and pending
approval. It references selected files without embedding snippet content.

A checkpoint does not compact, replace, summarize away, or truncate the
existing transcript. It only appends a compact current-state message.

## 8. Transcript and Budget Reality

The cache-aware production path calls `prepare_llm_call`. After the start call,
that method passes `request.loop_messages` directly to reuse, delta, and
checkpoint renderers.

`max_prior_messages` is applied only by the compatibility
`build_for_llm_call` path. It is not applied by the cache-aware
`prepare_llm_call` path used by AgentLoop. The runtime configuration value is
therefore present in `SessionAgentLoopContextProvider` but does not bound the
normal sidecar transcript.

`max_rendered_chars` is likewise present in `ContextBudget` and Runtime Config
but has no enforcement call site.

Current effective limits are consequently:

- recent structured event/tool/snippet facts are bounded;
- each AgentLoop run is bounded by `max_steps`;
- the append-only message transcript is not independently compacted or capped
  by Context Manager;
- a checkpoint adds content but does not reduce accumulated content.

## 9. Cache-Aware Run State

`SessionAgentLoopContextProvider` keeps `CacheAwareRunState` in an in-memory
dictionary keyed by `agent_run_id`. It records start initialization, stable
prefix hash, last checkpoint step, appended context count, last delta hash,
pending-decision count, and interruption signature.

That run state is not persisted in `context.sqlite` and is not reconstructed
from snapshots after process restart. A new AgentLoop/provider begins new run
state.

The implementation is structurally cache-friendly through prefix preservation.
It does not send provider-specific cache directives. `cache_policy_version` is
modeled on the trace but is not populated by current manager builds.

Context ids, render mode, hashes, append counts, reasons, and Runtime Config
hash are attached to AgentLoop LLM metadata. Provider usage may later report
cache hit/miss tokens, but cache effectiveness is measured outside Context
Manager.

## 10. Storage and Disclosure

The sidecar store path is:

```text
<workspace>/.plato/sessions/<session-id>/context.sqlite
```

`SqliteContextStore` persists snapshot and trace JSON in WAL-mode SQLite. It
supports get-by-id and ordered snapshot listing by session/task and optional
agent run.

Snapshots can contain selected file snippet content, ASK questions/answers,
guidance, controls, and other execution facts. The context store does not apply
redaction before persistence. It is protected local session metadata and must
not be treated as a shareable artifact.

There is no current UI query, HTTP route, or Audit projection for full context
snapshots/traces. Diagnostic export reads trace rows only to derive a sanitized
Skill governance summary; it does not include full context snapshots.

## 11. Failure Behavior

- A missing Task or source/store error fails the build.
- Preflight `execution_start` failure returns a TaskRunResult with a
  `context_build_failed` error reference and does not start AgentLoop.
- A per-call provider failure becomes an `AgentErrorObservation` with
  `context_build_error`, publishes a user-readable loop error when a MessageBus
  is present, and stops the loop with `context_error`.
- There is no silent fallback to the unmanaged prompt on the normal sidecar
  path.

## 12. Runtime Configuration

Sidecar assembly resolves these keys into `RuntimeContextSettings`:

```text
context_manager.checkpoint_interval_steps
context_manager.max_prior_messages
context_manager.budget.max_events
context_manager.budget.max_tool_results
context_manager.budget.max_file_snippets
context_manager.budget.max_file_snippet_chars
context_manager.budget.max_rendered_chars
```

The resolved config hash is copied into request, rendered input, snapshot,
trace, and LLM metadata.

The settings object is constructed from the effective config during workspace
runtime assembly and then passed to each new AgentLoop provider. There is no
Context Manager ConfigBus consumer that updates an already assembled runtime.
The catalog's mutability labels do not by themselves make later patches live in
the existing provider.

## 13. Relationship to Authorities

- TaskBus remains TaskDomain lifecycle and interrupt authority.
- EventStream remains ordered Action/Observation authority.
- AskStore remains ASK lifecycle and answer authority.
- Contract Revision store remains typed guidance authority.
- Workspace files remain workspace truth; snippets are selected evidence.
- AgentLoop remains transcript, tool-schema, call-metadata, and tool-protocol
  owner.
- Context snapshots/traces remain derived diagnostics.

The accepted
[ADR-0017](../decisions/ADR-0017-session-and-workspace-context-management-foundation.md)
defines future WorkspaceContext and SessionContext layers and explicitly marks
them not implemented. The current class name `SessionContextManager` refers to
session-scoped sources/storage; its output is still task execution context.

## 14. Current Limits

1. Context Manager governs LLM messages, not the complete provider request.
2. Schema fields are broader than current source population.
3. `writer` and read-only purpose do not enforce different behavior.
4. Generic candidate selection is not wired; candidate trace fields are empty.
5. `max_rendered_chars` is not enforced.
6. `max_prior_messages` is not applied in the cache-aware production path.
7. Checkpoints append and do not compact the transcript.
8. Full AgentLoop tool observations remain in the reused transcript outside
   structured fact budgets.
9. ASK facts and Contract guidance have separate/no ContextBudget accounting.
10. No production SkillContextSource is wired.
11. No WorkspaceContext, SessionContext, workspace inspection, read-only
    inquiry, token usage, Agent profile, MCP, multimodal, semantic retrieval, or
    long-term memory source is wired.
12. Run state is in memory and has no restart recovery.
13. Exact rendered messages are not persisted in context.sqlite.
14. Stored snapshots are not redacted and are not exposed through UI/Audit.
15. Runtime Context settings are assembly-time values, not live-updated
    provider state.
16. Context Manager itself does not enforce the single-writer execution lane.

## 15. Source Map

Primary implementation:

- `src/taskweavn/context/models.py`
- `src/taskweavn/context/sources.py`
- `src/taskweavn/context/policy.py`
- `src/taskweavn/context/renderer.py`
- `src/taskweavn/context/manager.py`
- `src/taskweavn/context/store.py`
- `src/taskweavn/context/sqlite_store.py`
- `src/taskweavn/context/agent_loop_provider.py`
- `src/taskweavn/core/loop.py`
- `src/taskweavn/task/execution.py`
- `src/taskweavn/server/main_page_agent.py`
- `src/taskweavn/server/runtime_config_consumers.py`
- `src/taskweavn/contract_revision/context_source.py`

Primary verification:

- `tests/test_context_manager.py`
- `tests/test_loop.py`
- `tests/test_fixed_route_task_executor.py`
- `tests/test_main_page_sidecar_app.py`
- `tests/test_runtime_config.py`
- `tests/test_skill_governance.py`
- `tests/test_contract_revision_commands.py`
- `tests/test_task_commands.py`

## 16. Summary

The current Context Manager successfully governs fixed-route Default Agent
message assembly, preserves an append-only cache-friendly prefix, appends
interval checkpoints and interruption deltas, persists structured snapshots
and traces, and integrates Task, EventStream, ASK, controls, and guidance facts.
It is not yet a general workspace/session memory system or a full token-window
manager: transcript compaction, rendered-size enforcement, live config,
candidate trace selection, exact replay, broader sources, and UI disclosure are
not implemented.
