# Feature Plan: RawTask And DraftTaskTree Persistence Foundation

> Status: planned
> Type: backend persistence / authoring-domain reliability
> Last Updated: 2026-05-28
> Decision: [ADR-0009: Single Active Session Work Tree](../../decisions/ADR-0009-single-active-session-worktree.md)
> Architecture: [Authoring Domain](../../architecture/authoring-domain.md), [Authoring Command Protocol](../../architecture/authoring-command-protocol.md), [Task Domain/UI Model Separation](../../architecture/task-domain-ui-model-separation.md)
> Product/API: [Workflow, Session, And Task UX Model](../../product/workflow-session-task-ux-model.md), [Plato UI API Contract](../../product/plato-ui-api-contract.md)
> Technical Design: [中文详细技术方案](raw-task-draft-tree-persistence-technical-design.zh-CN.md)

---

## 1. Gate Decision

RawTask/DraftTaskTree persistence design can proceed now.

Required upstream dependencies are sufficiently satisfied:

- ADR-0008 separates Authoring Domain from Execution TaskBus.
- ADR-0009 accepts one active RawTask, one active DraftTaskTree, and one active
  work-tree projection per Session.
- `RawTaskStore` and `DraftTaskStore` protocols already exist.
- `InMemoryRawTaskStore` and `InMemoryDraftTaskStore` already prove service
  semantics and version checks.
- `DefaultAuthoringCommandService` already centralizes RawTask and draft-tree
  mutations.
- `DefaultTaskProjectionService` already reads draft and published task facts
  through store protocols.
- `SqliteTaskBus` and SQLite publish stores provide local-first persistence
  patterns.

Backend store implementation can start after this plan is accepted. Projection,
gateway, and UI-facing publish changes should wait until the API/product
contract updates reference ADR-0009's active-tree rule.

---

## 2. Problem

Current authoring state is process-local:

- RawTask facts are stored in `InMemoryRawTaskStore`.
- DraftTaskTree and DraftTaskNode facts are stored in `InMemoryDraftTaskStore`.
- A system restart loses unpublished RawTask and draft-tree state.
- A Session can show `status = draft_ready` while the backend no longer has the
  real DraftTaskTree object needed by publish.
- `TaskTreeView.id` may be a synthetic projection id, while publish requires the
  real `draft_tree_id`.

This breaks the product expectation that a user can close or restart Plato and
return to the last working Session without losing an unpublished draft plan.

---

## 3. Goals

1. Persist active RawTask and DraftTaskTree authoring facts across restart.
2. Enforce the ADR-0009 rule that a Session has only one active draft tree.
3. Preserve current store protocol semantics where possible.
4. Let snapshot/projection rebuild the active draft tree after restart.
5. Let publish resolve the real active `draft_tree_id` instead of relying on a
   synthetic `TaskTreeView.id`.
6. Keep RawTask exploratory history lightweight: persist current useful state,
   not every discarded user formulation.
7. Keep implementation local-first and SQLite-backed.

---

## 4. Non-goals

- Do not implement post-publish editing policy in this slice.
- Do not introduce a new full WorkTree domain.
- Do not build multi-active-tree Session UI.
- Do not normalize every RawTask ask/answer into many tables unless required by
  current queries.
- Do not implement distributed locks, multi-process leasing, or remote database
  storage.
- Do not rewrite TaskBus, TaskPublisher, or Main Page UI.
- Do not expose multi-agent orchestration controls.

---

## 5. Scope Summary

The persistence foundation uses a dedicated authoring database:

```text
<workspace>/.taskweavn/
  tasks.sqlite        # Execution Domain: published TaskBus facts
  publish.sqlite      # Publish control plane: idempotency, scheduler, publish audit
  authoring.sqlite    # Authoring Domain: RawTask, DraftTaskTree, active state
```

Implementation should add SQLite-backed stores for:

- RawTask snapshots;
- DraftTaskTree and DraftTaskNode facts;
- draft-to-published mappings;
- one active authoring/work-tree state per Session.

Detailed schema, store API, transaction rules, projection rules, and tests are
defined in the [technical design](raw-task-draft-tree-persistence-technical-design.zh-CN.md).

---

## 6. Implementation Phases

### P8.1 SQLite Authoring Store Foundation

Deliver:

- `SqliteRawTaskStore`
- `SqliteDraftTaskStore`
- `authoring.sqlite` schema
- tests mirroring current in-memory store behavior
- restart/reopen tests for RawTask, DraftTaskTree, nodes, and mappings

Acceptance:

- existing `RawTaskStore` and `DraftTaskStore` protocol tests pass against
  SQLite implementations;
- version conflicts survive reopen;
- published mappings survive reopen.

### P8.2 Active Authoring State

Deliver:

- `AuthoringStateStore`
- `SqliteAuthoringStateStore`
- active RawTask/DraftTaskTree selection rules
- tests for replacement/regeneration and restart recovery

Acceptance:

- one Session has one active draft tree;
- inactive trees do not appear in active projection;
- active state survives reopen.

### P8.3 Projection And Gateway Alignment

Deliver:

- active-tree-aware projection path;
- publish gateway resolution from session active draft tree;
- explicit error when publish identity is invalid;
- docs update to UI API contract.

Acceptance:

- Main Page snapshot for `draft_ready` session can be rebuilt after restart;
- publish command uses real `draft_tree_id`;
- synthetic `TaskTreeView.id` is not treated as domain truth.

### P8.4 Sidecar Assembly

Deliver:

- local sidecar service assembly uses SQLite authoring stores;
- `authoring.sqlite` path lives under workspace `.taskweavn`;
- smoke tests create draft tree, restart/reopen stores, query snapshot, publish.

Acceptance:

- a user can restart the backend and still see the current draft task tree;
- no production UI rewrite is required.

### P8.5 Durable Authoring Command Idempotency

Deliver:

- optional `SqliteAuthoringCommandIdempotencyStore`;
- command-result replay for idempotency keys across service restart;
- gateway propagation of generate/publish idempotency keys into authoring
  command batches;
- idempotent publish replay when the active draft tree has already moved to
  published state.

Decision:

- The first result for `(session_id, idempotency_key)` is authoritative.
- Reusing the same key replays the cached authoring command result rather than
  treating a changed generated command payload as a conflict. This preserves
  the previous in-memory behavior and prevents LLM retry variance from causing
  duplicate RawTask/DraftTaskTree writes or publish drift.

Acceptance:

- duplicate authoring commands do not create duplicate RawTasks or draft trees
  after retry/restart;
- duplicate publish commands do not create duplicate published tasks after
  retry/restart.

### P8.6 API Command Response Idempotency

Deliver:

- API-level command response idempotency store;
- final `CommandResponse` replay for repeated `idempotencyKey` requests;
- request hash conflict detection at the HTTP command boundary;
- sidecar persistence for command responses across backend restart.

Decision:

- `idempotencyKey` is generated by the frontend and represents one logical user
  action.
- API-level replay is authoritative before gateway/collaborator/LLM execution.
- The request hash excludes volatile `commandId` and includes route identity,
  path target, session id, expected version, and payload.
- Same `(session_id, idempotency_key)` with the same request hash replays the
  first HTTP command response.
- Same `(session_id, idempotency_key)` with a different request hash returns an
  `idempotency_conflict` transport error.
- P8.6 stores completed responses only. It does not yet implement an
  `in_progress` reservation or recovery state machine.

Acceptance:

- duplicate generate command retry/restart returns the cached API response
  without calling the LLM again;
- duplicate publish command retry/restart returns the cached API response;
- same key with changed command payload is rejected as an idempotency conflict;
- command-level P8.5 idempotency remains as a downstream safety net.

---

## 7. Acceptance Criteria

1. RawTask and DraftTaskTree facts survive backend restart.
2. A `draft_ready` Session can rebuild its current draft task tree from
   persistent stores.
3. One Session has one active draft tree in product projection.
4. Publish uses a real `draft_tree_id` or resolves the active draft tree.
5. Inactive draft trees are not shown as a forest on Main Page.
6. Store-level tests cover create, update, version conflict, publish mapping, and
   reopen behavior.
7. No Main Page UI rewrite is required for the first persistence slice.
8. Authoring command idempotency records survive restart and replay generate /
   publish command results without duplicate writes.
9. API command response idempotency records survive restart and replay command
   responses before gateway execution.

---

## 8. Workload Estimate

| Slice | Estimate | Notes |
|---|---:|---|
| P8.1 SQLite stores | 1-1.5 days | More schema/model mapping than algorithmic work. |
| P8.2 active state | 0.5 day | Small schema + selection rules. |
| P8.3 projection/gateway | 0.5-1 day | Includes publish identity fix. |
| P8.4 sidecar assembly | 0.5 day | Depends on current service factory shape. |
| P8.5 command idempotency | 0.5-1 day | Can defer if not needed for first recovery fix. |
| P8.6 API command response idempotency | 0.5-1 day | Required before broader user testing of retry/restart flows. |

Recommended first implementation batch: P8.1 + P8.2 only.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| SQLite batch rollback does not match in-memory service rollback. | Start with store-level tests, then add a small unit-of-work wrapper if batch semantics require it. |
| Projection still lists all draft trees. | Add active-state-aware projection tests before sidecar assembly. |
| Publish still receives synthetic tree id. | Update gateway to resolve active draft tree and add explicit tests. |
| RawTask asks/answers need queryable UI later. | Store compact JSON now; normalize later only when UX needs it. |
| Regeneration semantics become hidden edit history. | Keep only current active draft in UI; archived objects are trace/debug only. |

---

## 10. Recommended Next Prompt

```text
Use the product-workflow-gate skill first.

Task:
Implement P8.1 SQLite Authoring Store Foundation.

Context:
docs/plans/feature/raw-task-draft-tree-persistence.md and
docs/plans/feature/raw-task-draft-tree-persistence-technical-design.zh-CN.md
define the persistence plan. Start with SQLite-backed RawTaskStore and
DraftTaskStore only.

Do not change Main Page UI.
Do not implement post-publish editing.
Do not rewrite TaskBus or TaskPublisher.
Do not wire HTTP routes yet.

Required work:
1. Add `src/taskweavn/task/sqlite_authoring.py`.
2. Implement `SqliteRawTaskStore`.
3. Implement `SqliteDraftTaskStore`.
4. Add schema initialization for `authoring.sqlite`.
5. Add focused persistence/reopen tests mirroring in-memory store behavior.

Output:
- files changed
- stores implemented
- schema summary
- tests run
- remaining gaps
```
