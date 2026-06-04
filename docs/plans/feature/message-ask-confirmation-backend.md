# Feature Plan: Message, ASK, And Confirmation Backend

> Status: in progress
> Type: Product 1.0 interaction backend closure
> Last Updated: 2026-06-03
> Decisions: [ADR-0014 Interaction Control Taxonomy For Product 1.0](../../decisions/ADR-0014-interaction-control-taxonomy-for-product-1-0.md)
> Architecture: [Interaction Layer](../../architecture/interaction-layer.md), [UI / Backend Communication](../../architecture/ui-backend-communication.md), [Task](../../architecture/task.md), [TaskBus](../../architecture/bus.md), [Context Manager](../../architecture/context-manager.md)
> Related Contracts: [ASK Lifecycle Contract](../../engineering/ask-lifecycle-contract.md), [ASK User Interaction](../../interaction-model/ask-user-interaction.md), [Confirmation UI Spec](../../ux/confirmation-ui-spec.md), [UI API Interfaces](../ui/ui-api-interfaces.md), [UI ViewModel Contract](../../frontend/ui-viewmodel-contract.md)
> Technical Design: [Message, ASK, and confirmation backend technical design](message-ask-confirmation-backend-technical-design.zh-CN.md)

---

## 1. Problem

Product 1.0 already has a durable MessageStream and a minimal confirmation
path based on actionable messages:

```text
AgentMessage(actionable)
  -> MessageBus / MessageStream
  -> pending confirmation projection
  -> resolve_confirmation
  -> AgentMessage(response)
```

That is enough for authorization prompts, but it is not enough for execution
ASK.

ASK is different from confirmation. Confirmation means the Agent already knows
the intended action and needs authorization. ASK means the Agent lacks required
user-owned information and must wait for user input before continuing the task.

Without a dedicated Product 1.0 backend slice:

- an Agent must guess instead of asking when task information is missing;
- MessageStream risks becoming the hidden state authority for unrelated
  interaction types;
- Main Page cannot show pending/active ASK facts directly;
- answer commands cannot guarantee durable persistence before resume;
- the dispatcher cannot know how to continue a task after an answer;
- confirmation duplicate responses and ASK/confirmation naming drift remain
  under-specified.

---

## 2. Product Decisions

Product 1.0 keeps Message, ASK, and confirmation separate:

| Mechanism | Purpose | Source Of Truth |
|---|---|---|
| Message | User-facing history and passive process communication. | MessageStream |
| Confirmation | User authorizes or declines a known action. | Actionable message plus response message |
| ASK | Agent requests missing user-owned information. | Durable ASK store |

Confirmed Product 1.0 backend decisions:

1. ASK adds a TaskBus `waiting_for_user` state.
2. ASK uses a separate durable store for `AskRequest` and `AskAnswer`.
3. The frontend guarantees that the answer command was accepted/written before
   it clears local pending state.
4. The backend guarantees correct behavior after the answer is durably written.
5. Answer commands are idempotent by idempotency key.
6. Duplicate answers for an already answered ASK are rejected unless they are
   the same idempotent command replay.
7. Existing misleading ASK/confirmation semantics in comments, names, or docs
   should be corrected during implementation.

`waiting_for_user` is a published Task execution state, not a UI-only label.
It means the current task cannot continue until its active blocking ASK is
answered, cancelled, expired, or otherwise resolved by backend policy.

---

## 3. Goals

1. Preserve MessageStream as the user-facing message history substrate.
2. Harden the existing confirmation backend path without turning it into ASK.
3. Add durable execution ASK request and answer storage.
4. Add TaskBus `waiting_for_user` transitions for blocking ASK.
5. Add answer/defer/cancel backend commands and query projection.
6. Ensure answer persistence happens before task resume.
7. Trigger or enable dispatcher resume after a blocking ASK is answered.
8. Include pending/answered ASK facts in Context Manager inputs.
9. Expose Main Page snapshot/query fields for pending and active ASK.
10. Keep Product 1.0 single-agent, local-first, and minimal.

---

## 4. Non-goals

- No frontend ASK Dock implementation in this backend slice.
- No multi-Agent negotiation over one ASK.
- No file attachments or multimodal ASK answers.
- No editing historical ASK answers.
- No replacing confirmation with ASK.
- No treating ordinary chat questions as durable ASK objects.
- No Product 1.1 Agent Manager, Router, skills, MCP, or custom Agent protocol.
- No hard cancellation or rollback of partially completed tool effects.
- No complex recovery policy beyond durable pending/answered facts and
  idempotent resume triggers.

---

## 5. Product 1.0 Scope

### In Scope

- `AskRequest` and `AskAnswer` domain models.
- Durable ASK store with SQLite and in-memory implementations.
- TaskBus status expansion:

  ```text
  pending -> running -> waiting_for_user -> pending -> running -> done / failed
  ```

- Blocking ASK creation from the execution runtime.
- ASK answer persistence and duplicate-answer protection.
- Minimal ASK commands:
  - answer;
  - defer;
  - cancel.
- Minimal ASK queries:
  - list session asks;
  - get one ask;
  - Main Page snapshot fields for pending/active asks.
- UI event/refetch hints for ASK created/answered/deferred/cancelled/expired.
- Context Manager ASK facts before the next LLM call after resume.
- Confirmation backend hardening:
  - explicit duplicate response behavior;
  - resolved/pending projection clarity;
  - terminology cleanup.

### Out Of Scope

- Rich frontend ASK Dock interactions.
- Long-lived background expiration scheduler.
- Server-side multi-client conflict UI.
- Complex recovery after process death while an LLM request is in flight.
- Cross-workspace or cloud synchronization.

---

## 6. Backend Semantics

### 6.1 Message

MessageStream remains append-only user-facing history. It may record:

- ASK created informational history;
- ASK answered informational or response-like history;
- confirmation actionable prompts;
- confirmation user responses;
- task execution process messages.

MessageStream must not be the source of truth for ASK status.

### 6.2 Confirmation

Confirmation remains based on actionable messages:

```text
AgentMessage(message_type="actionable", requires_response=true)
  -> pending confirmation
  -> resolve_confirmation(value)
  -> AgentMessage(message_type="response", parent_message_id=confirmation_id)
```

Product 1.0 confirmation hardening should enforce:

- only actionable messages can be resolved;
- confirmation session must match command session;
- empty values are rejected;
- duplicate responses are rejected unless the same idempotent command is
  replayed;
- `ConfirmationActionView.status` is derived from actionable plus response
  facts.

### 6.3 ASK

ASK is a durable backend object:

```text
AskRequest
  -> pending / deferred / answered / cancelled / expired
AskAnswer
  -> one canonical answer per AskRequest
```

A blocking ASK moves its owning task from `running` to `waiting_for_user`.
After the answer is durably written, the backend resumes the task by moving it
back toward execution and ensuring the dispatcher can continue.

---

## 7. Implementation Slices

### C1. Contract And Planning

Current status: done by this plan.

Deliver:

- feature plan;
- detailed Chinese technical design;
- explicit Product 1.0 decisions for `waiting_for_user`, ASK store, answer
  semantics, idempotency, duplicate-answer rejection, and terminology cleanup.

Acceptance:

- docs distinguish Message, ASK, and confirmation;
- docs define the TaskBus state addition;
- docs define the durable ASK store boundary;
- docs define answer-before-resume ordering.

### C2. Confirmation Backend Hardening

Current status: done.

Deliver:

- command-layer idempotency behavior for `resolve_confirmation`;
- duplicate response rejection for non-idempotent repeats;
- tests for resolved/pending projection after response;
- terminology cleanup where current code comments conflate pending actionable
  with `ask_user`.

Acceptance:

- resolving a confirmation twice with different command identity is rejected;
- replaying the same idempotent command returns the same command result;
- pending confirmation disappears after canonical response exists;
- MessageStream remains the storage authority for confirmation history.

Implementation note:

- Product 1.0 uses the existing UI command response idempotency layer for
  idempotent HTTP command replay. The task command service rejects a second
  non-idempotent confirmation resolve once `MessageStream.response_for(...)`
  reports a canonical response.

### C3. ASK Domain And Durable Store

Current status: done.

Deliver:

- `AskRequest`, `AskAnswer`, and `AskStatus` models;
- `AskStore` protocol;
- in-memory and SQLite implementations;
- one canonical answer per ASK;
- idempotency record support for answer/defer/cancel commands.

Acceptance:

- pending ASK survives process restart;
- answered ASK returns its answer history;
- duplicate answer is rejected unless it is idempotent replay;
- session/task-scoped list queries are deterministic.

Implementation note:

- `taskweavn.interaction.ask` defines the Product 1.0 ASK domain models,
  `AskStore` protocol, and in-memory store. `SqliteAskStore` provides durable
  request/answer/idempotency persistence without wiring ASK into TaskBus,
  HTTP, UI projection, or AgentLoop yet.

### C4. TaskBus Waiting State

Current status: done.

Deliver:

- `TaskStatus` adds `waiting_for_user`;
- TaskBus transitions:
  - `running -> waiting_for_user`;
  - `waiting_for_user -> pending` for Product 1.0 fixed-route redispatch;
  - `waiting_for_user -> failed`;
- retry clears active ASK linkage according to backend policy;
- projection maps `waiting_for_user` distinctly from confirmation pending.

Acceptance:

- `claim_next` does not claim `waiting_for_user` tasks;
- child tasks do not unlock until parent reaches `done`;
- Main Page can distinguish execution waiting on ASK from confirmation pending;
- existing pending/running/done/failed behavior remains compatible.

Implementation note:

- `TaskDomain` now carries active ASK linkage with `waiting_for_ask_id` and
  `waiting_for_user_since`.
- `TaskBus.wait_for_user(...)` moves a running task into
  `waiting_for_user`.
- `TaskBus.resume_after_user(...)` requires the same ASK id and returns the
  same task identity to unclaimed `pending` for Product 1.0 redispatch.
- The SQLite TaskBus continues to persist full `TaskDomain` facts in the JSON
  payload and mirrors the canonical status column for existing query paths; no
  extra ASK index column is introduced in Product 1.0 C4.
- UI contract mapping exposes node `status="waiting_user"` while preserving
  `execution="waiting_for_user"`, so ASK waiting can be distinguished from
  confirmation-pending running tasks.

### C5. ASK Commands, Queries, And Snapshot Projection

Current status: done.

Deliver:

- command payloads and HTTP routes:
  - `POST /api/v1/sessions/{sessionId}/asks/{askId}/answer`;
  - `POST /api/v1/sessions/{sessionId}/asks/{askId}/defer`;
  - `POST /api/v1/sessions/{sessionId}/asks/{askId}/cancel`;
- query routes:
  - `GET /api/v1/sessions/{sessionId}/asks`;
  - `GET /api/v1/sessions/{sessionId}/asks/{askId}`;
- `AskRequestView` and snapshot fields:
  - `pending_asks`;
  - `active_ask`;
- UI event constructors for ASK invalidation/refetch.

Acceptance:

- answer command response follows existing command response conventions;
- accepted answer command does not require frontend to infer state from
  message text;
- Main Page snapshot exposes active ASK directly;
- stale or incomplete ASK events can trigger targeted refetch.

Implementation note:

- `DefaultTaskAskCommandService` writes answer/defer/cancel through `AskStore`
  before applying Product 1.0 TaskBus policy.
- Accepted answer commands call `TaskBus.resume_after_user(...)` for the same
  blocking ASK and then request fixed-route dispatch with
  `reason="ask_answer_resume"`.
- Defer/cancel commands resolve the pending ASK and fail the waiting task with
  an `ask_deferred:` or `ask_cancelled:` error reference so the task does not
  remain stuck in `waiting_for_user`.
- Main Page sidecar now creates a workspace-scoped `asks.sqlite`, injects ASK
  command/projection services, exposes ASK list/detail routes, and projects
  `pending_asks` plus `active_ask` into `MainPageSnapshot`.
- C5 tests cover command service ordering, idempotent answer replay, duplicate
  rejection, ASK active projection, UI gateway wrapping, HTTP routes, and the
  sidecar answer -> resume path.

### C6. Runtime And Resume Integration

Current status: implemented.

Deliver:

- execution runtime `ask_user` tool or equivalent boundary;
- blocking ASK creation persists `AskRequest` before yielding;
- TaskBus moves task to `waiting_for_user`;
- Context Manager includes ASK facts on resume.

Acceptance:

- Agent can ask instead of guessing;
- task stops executing after blocking ASK creation;
- answer survives restart before resume;
- resumed LLM input contains the answer fact.

Implementation notes:

- AgentLoop exposes an `ask_user` execution tool for blocking ASK creation.
- FixedRouteTaskExecutor treats `waiting_for_user` as a neutral drain stop, not
  completion or failure.
- Context Manager renders pending/answered ASK facts into full, start, delta,
  and checkpoint context inputs.

### C7. Tests And Docs Closure

Current status: implemented.

Deliver:

- unit tests for ASK store and command idempotency;
- TaskBus transition tests;
- gateway/HTTP route tests;
- runtime integration tests for ask -> waiting -> answer -> resume;
- docs closure updates in gaps/roadmap/release after implementation.

Acceptance:

- Product 1.0 backend ASK loop passes without frontend-specific assumptions;
- confirmation regression tests pass;
- docs accurately state implemented scope and remaining frontend work.

Validation:

- `uv run pytest tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_context_manager.py tests/test_task_ask_service.py tests/test_ask_store.py tests/test_ask_projection.py tests/test_main_page_sidecar_app.py`
  - 98 passed, 1 dependency warning
- `uv run ruff check src/taskweavn tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_context_manager.py tests/test_main_page_sidecar_app.py`
  - passed
- `uv run mypy src/taskweavn`
  - passed

Release record:

- [Message, ASK, And Confirmation Backend](../../releases/message-ask-confirmation-backend.md)

---

## 8. Dependencies And Risks

Dependencies:

- cooperative task interruption branch should be merged or this work should be
  treated as a stacked branch;
- Context Manager 1.0 and cache-aware rendering are needed for ASK resume facts;
- UI/backend contract baseline is needed for command/query conventions.

Risks:

- Adding `waiting_for_user` touches TaskBus, projection, dispatcher, and tests.
- If answer persistence and resume trigger are coupled too tightly, recovery
  becomes hard to reason about.
- Confirmation and ASK UI may share components later, but backend semantics
  must remain separate.
- Existing comments and session-status derivation contain legacy wording that
  can mislead future implementation.

Mitigation:

- implement C2-C6 as separate commits/slices;
- keep stores and command services explicit;
- make answer-before-resume ordering testable;
- avoid using MessageStream as ASK state authority.

---

## 9. Acceptance Criteria

The backend plan is complete when:

1. confirmation remains a message/actionable lifecycle and rejects duplicate
   non-idempotent resolutions;
2. execution ASK has durable request and answer storage;
3. blocking ASK moves its task into `waiting_for_user`;
4. answering an ASK is durable before any resume behavior;
5. duplicate ASK answers are rejected except idempotent replay;
6. Main Page backend snapshot can expose pending and active ASK facts directly;
7. Context Manager can include ASK facts for the resumed Agent call;
8. terminology no longer conflates ASK with confirmation/actionable messages;
9. tests cover store, command, TaskBus, projection, and runtime resume paths.
