# Release: Collaborator Agent And Task Authoring

> Status: done / server-core release candidate
> Date: 2026-05-15
> Accepted: 2026-05-15
> Work Stream: Phase 3C — Task Authoring Foundation
> Related Capability: [Task Authoring](../capabilities/task-authoring/)
> Related Plan: [Legacy Collaborator Agent](../archive/legacy-2026-05-18/plans/feature/collaborator-agent-task-authoring.md)
> Technical Design: [Legacy Collaborator Agent And Task Authoring](../archive/legacy-2026-05-18/architecture/collaborator-agent-task-authoring.md)
> Related Architecture: [Legacy Authoring Domain](../archive/legacy-2026-05-18/architecture/authoring-domain.md), [Legacy Authoring Command Protocol](../archive/legacy-2026-05-18/architecture/authoring-command-protocol.md), [Legacy Tool Capability Layer](../archive/legacy-2026-05-18/architecture/tool-capability-layer.md)
> Related ADR: [ADR-0008](../decisions/architecture/ADR-0008-authoring-domain-execution-boundary.md)

---

## 1. Summary

This release establishes the server-core authoring package behind TaskWeavn's Task-first interaction model.

It adds the Collaborator-facing authoring domain needed to turn natural language into editable Task Tree drafts before anything enters Execution TaskBus:

```text
user input
  -> RawTask + FeasibilityReport
  -> optional RawTaskAsk clarification
  -> DraftTaskTree / DraftTaskNode facts
  -> user edits and accepts draft nodes
  -> PublishDraftTaskTreeCommand
  -> TaskPublisher boundary
```

The important product boundary is now explicit: Collaborator explores and drafts Tasks with the user, while published execution Tasks remain a separate domain owned by TaskBus and future TaskPublisher implementations.

---

## 2. Shipped

### 2.1 Authoring Contracts

- `RawTask`, `RawTaskAsk`, `RawTaskAnswer`, and `FeasibilityReport`.
- `DraftTaskNodeProposal`, `DraftTaskTreeProposal`, and `DraftTaskPatchProposal`.
- `AuthoringContext` for session-scoped and selected-node Collaborator invocations.
- `CapabilityDescriptor`, `CapabilityCatalog`, and `StaticCapabilityCatalog`.
- `DraftTaskTreeValidator` with capability, tree shape, depth, node count, duplicate id/order, and publishable-state checks.

### 2.2 Authoring Command Protocol

- `AuthoringCommandBatch`.
- `MutateRawTaskCommand`.
- `MutateDraftTaskTreeCommand`.
- `PublishDraftTaskTreeCommand`.
- `AuthoringCommandResult`, errors, warnings, and message effects.
- Command-level idempotency fallback for single-command batches.
- All-or-nothing rollback for in-memory authoring stores.

### 2.3 Stores And Context

- `RawTaskStore` and `InMemoryRawTaskStore`.
- `DraftTaskStore` and `InMemoryDraftTaskStore`.
- Draft traversal, selected node lookup, accepted/published lifecycle methods, and draft-to-published lineage mapping.
- `DefaultAuthoringContextBuilder` that reconstructs session mode and task mode context from stores, MessageStream, and CapabilityCatalog.

### 2.4 Collaborator Service

- `CollaboratorAuthoringService` protocol.
- `DefaultCollaboratorAuthoringService` that maps structured LLM proposals into Authoring Commands.
- JSON-only prompt boundary for RawTask feasibility, DraftTaskTree creation, and selected-node patching.
- Invalid LLM proposals are returned as structured `AuthoringCommandResult` rejections instead of leaking exceptions.

### 2.5 Publish Boundary

- `PublishDraftTaskTreeCommand` handler.
- Accepted-state gate: only accepted draft trees can publish.
- Optional validator check before publisher handoff.
- `TaskPublisher.publish_draft_tree(...)` boundary.
- Draft-to-published mapping validation and persistence.
- Duplicate publish rejection.
- Publish trace message effect through the Session Message Stream.

### 2.6 System Template And API Adapter

- `CollaboratorAgentTemplate` metadata.
- `CollaboratorTemplateRegistry` and in-memory registry.
- Built-in template registration helper for session start.
- `DefaultCollaboratorApiAdapter` for future UI/API endpoints:
  - `start_session`;
  - `append_session_message`;
  - `answer_raw_task_ask`;
  - `generate_task_tree`;
  - `append_task_message`;
  - `publish_task_tree`.
- Adapter returns stable `CommandResult` objects and does not expose raw LLM proposal schemas to UI callers.
- Collaborator template has no workspace file/shell tool pools; it plans through read-only capabilities and mutates system state through command services.

---

## 3. Validation

Final validation for this release candidate:

- `uv run ruff check src/taskweavn/task tests/test_collaborator_api_adapter.py`
- `uv run pytest tests/test_collaborator_api_adapter.py tests/test_collaborator_authoring_service.py tests/test_authoring_command_service.py` — 26 passed, 1 warning
- `uv run mypy src/taskweavn/task tests/test_collaborator_api_adapter.py tests/test_collaborator_authoring_service.py tests/test_authoring_command_service.py`
- `uv run ruff check src tests`
- `uv run mypy src tests` — no issues in 130 source files
- `uv run pytest` — 572 passed, 1 warning
- `git diff --check`

The single warning is the existing OpenHands/Authlib deprecation warning from the test environment.

---

## 4. Acceptance Notes

- This release is a server-core package, not a visible UI release.
- Natural-language authoring is testable with mock LLM responses, but end-to-end user testing still needs the Task-first UI or a server API transport.
- `TaskPublisher` is still a protocol boundary in this package; concrete TaskBus-backed publishing is the next work package.
- Stores are in-memory implementations for the release candidate. SQLite/persistent authoring stores remain a follow-up.
- Collaborator prompt/proposal parsing is intentionally isolated because product behavior will likely keep changing while user testing clarifies the authoring experience.

---

## 5. Follow-ups

- Implement concrete `TaskPublisher` and TaskBus publish lifecycle.
- Add persistent authoring stores for RawTask, DraftTaskTree, publish mappings, and authoring history.
- Expose `CollaboratorApiAdapter` through the future server transport.
- Connect Task-first UI to the adapter and projection APIs.
- Add richer user-case tests once Task cards, task-scoped messages, confirmations, and publish flows are visible in UI.
- Decide whether typed authoring EventStream events are needed beyond MessageStream and store traceability.
