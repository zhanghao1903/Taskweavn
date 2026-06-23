# Release: Message, ASK, And Confirmation Backend

> Status: done / accepted for Product 1.0 backend closure
> Date: 2026-06-03
> Work Stream: Product 1.0 interaction backend / P9 closure
> Related Plan: [Message, ASK, And Confirmation Backend](../plans/feature/message-ask-confirmation-backend.md)
> Technical Design: [Message / ASK / Confirmation 后端详细技术方案](../plans/feature/message-ask-confirmation-backend-technical-design.zh-CN.md)
> Architecture: [Interaction Layer](../architecture/interaction-layer.md), [Context Manager](../architecture/context-manager.md), [UI/backend Communication](../architecture/ui-backend-communication.md)
> Implementation Commits: `8136eae`, `c0c4605`, `20a74c8`, `a8d393b`, `5edb2d4`

---

## 1. Summary

This release closes the Product 1.0 backend slice for execution-time ASK,
confirmation hardening, and Main Page backend projections.

ASK is now a durable execution object, separate from confirmation/actionable
messages. A blocking runtime ASK can pause the owning published Task in
`waiting_for_user`, the answer is persisted before resume, and the resumed
Default Agent call receives answered ASK facts through Context Manager.

Frontend ASK Dock and confirmation UI integration remain separate follow-up
work.

Update 2026-06-19: execution-time confirmations can now use the same
`waiting_for_user` Task lifecycle as ASK. The confirmation remains an
actionable MessageStream object, but the owning published Task carries
`waiting_for_confirmation_id` until the user resolves it.

---

## 2. Release Scope

### 2.1 Confirmation Hardening

- Confirmation remains an authorization/actionable-message lifecycle.
- Duplicate non-idempotent resolve attempts are rejected.
- Idempotent replay returns the accepted prior command result.
- ASK terminology is kept separate from confirmation terminology.
- Added `request_confirmation` as an execution Agent tool for known
  authorization decisions.
- Resolving a matching published-task confirmation resumes the waiting Task
  back to `pending` for fixed-route redispatch.

### 2.2 Durable ASK Domain

- Added durable ASK request/answer models and store protocol.
- Added SQLite and in-memory ASK stores.
- Persisted ASK state under workspace-scoped `asks.sqlite`.
- Kept MessageStream as projection/history only, not ASK state authority.

### 2.3 TaskBus Waiting State

- Added `waiting_for_user` as a published Task execution state.
- Added active ASK linkage through `waiting_for_ask_id` and
  `waiting_for_user_since`.
- Added active confirmation linkage through `waiting_for_confirmation_id`.
- `claim_next` ignores waiting Tasks.
- `resume_after_user(...)` moves a matching waiting Task back to `pending`.
- `resume_after_confirmation(...)` moves a matching confirmation-waiting Task
  back to `pending`.
- `fail(...)` can terminally fail a waiting Task.

### 2.4 ASK Commands, Queries, And Projection

- Added answer/defer/cancel command behavior for ASK.
- Answer writes to `AskStore` before TaskBus resume.
- Main Page backend exposes ASK list/detail routes.
- Session snapshots include `pending_asks` and `active_ask`.
- Active ASK projection prefers the currently waiting Task when available.

### 2.5 Runtime ASK Creation And Resume Context

- Added `ask_user` action/tool/observation for AgentLoop execution.
- The tool persists a blocking `AskRequest` before moving TaskBus to
  `waiting_for_user`.
- AgentLoop stops the current run after a successful blocking ASK observation.
- FixedRouteTaskExecutor treats `waiting_for_user` as a neutral dispatch stop,
  not completion or failure.
- Context Manager includes pending/answered ASK facts in full, start, delta,
  and checkpoint context render modes.
- Main Page default Agent wires the workspace ASK store into both the runtime
  tool list and Context Manager source.

---

## 3. Validation

Release validation included:

- `git diff --check`
  - passed
- `uv run ruff check src/taskweavn tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_context_manager.py tests/test_main_page_sidecar_app.py`
  - passed
- `uv run mypy src/taskweavn`
  - passed
- `uv run pytest tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_context_manager.py tests/test_task_ask_service.py tests/test_ask_store.py tests/test_ask_projection.py tests/test_main_page_sidecar_app.py`
  - 98 passed, 1 dependency warning

Covered behavior:

- durable ASK store create/answer/replay/reject behavior;
- TaskBus `running -> waiting_for_user -> pending` and failure paths;
- answer-before-resume command ordering;
- Main Page snapshot pending/active ASK projection;
- runtime `ask_user` creation from AgentLoop;
- fixed-route dispatch stopping on `waiting_for_user`;
- resumed AgentLoop context containing the answered ASK fact.

---

## 4. Follow-ups After Acceptance

- Build Main Page ASK Dock / answer UI on top of the existing backend query and
  command contract.
- Finish confirmation UI integration and copy cleanup without merging
  confirmation semantics into ASK.
- Add event/refetch polish for ASK changes if snapshot polling is not enough.
- Keep non-text ASK attachments, pause/cancel PublishedTask statuses, complex
  recovery, and multi-Agent ASK routing out of Product 1.0.
