# Authoring Command Protocol

> Status: fact-calibrated current implementation / high-change area
> Last Updated: 2026-07-10
> Original preserved as: `docs/architecture/authoring-command-protocol.original.md`
> Related Architecture:
> [Authoring Domain](authoring-domain.md),
> [Collaborator Agent](collaborator-agent-task-authoring.md),
> [Tool Capability Layer](tool-capability-layer.md),
> [Workspace Communication Protocol](workspace-communication-protocol.md)
> Related ADR: [ADR-0008](../decisions/ADR-0008-authoring-domain-execution-boundary.md)
> Related Plans:
> [RawTask And DraftTaskTree Persistence](../plans/feature/raw-task-draft-tree-persistence.md),
> [ASK Domain Unification And Batch Answer](../plans/feature/ask-domain-unification-batch-answer.md),
> [Plan / TaskNode Contract Migration](../plans/feature/plan-tasknode-contract-migration.md)

Fact calibration note:

- The authoring command protocol is implemented in
  `src/taskweavn/task/authoring.py` and
  `src/taskweavn/task/authoring_service.py`.
- Durable `Plan` / `PlanTaskNode` publishing is not an
  `AuthoringCommandBatch` command. It is implemented by
  `PublishPlanCommand` and `DefaultPlanPublisher`, and the UI command gateway
  prefers it when an active durable Plan exists.
- Legacy `PublishDraftTaskTreeCommand` remains implemented for DraftTaskTree
  compatibility sessions.
- `remove_node` and `reorder_siblings` are declared operation names, but the
  default command service does not currently implement them.
- `mark_ready` is handled as a no-op warning because persisted draft readiness
  is not modeled.
- Authoring command idempotency replays the first result for
  `(session_id, idempotency_key)`. Request-hash conflict detection exists at
  the HTTP UI command response idempotency layer, not inside
  `DefaultAuthoringCommandService`.
- Current all-or-nothing rollback snapshots RawTask and DraftTaskTree stores.
  It is not a single transaction across PlanStore, active authoring state,
  HTTP response idempotency, and all external stores.

---

## 1. Purpose

Authoring commands are the deterministic mutation boundary for TaskWeavn
authoring state.

The core rule remains:

```text
LLM / Collaborator proposes.
Code validates structured commands.
AuthoringCommandService persists RawTask and DraftTaskTree facts.
PlanPublisher publishes durable Plans.
TaskPublisher creates executable TaskBus facts only after publish.
```

This separates two classes of work:

| Change type | Current boundary |
|---|---|
| TaskWeavn authoring state | Authoring commands and Plan publisher commands |
| Execution TaskBus state | Task publish and execution services |
| Workspace or external world changes | Tool adapters / workspace request boundaries |

Authoring commands are not ordinary LLM-visible tools by default. They are
typed backend commands used by Collaborator services, UI command gateways, and
runtime routing code after user intent has been parsed into structured
operations.

---

## 2. Current Command Surfaces

Current implemented command surfaces are:

| Surface | Implementation | Scope |
|---|---|---|
| RawTask mutation | `MutateRawTaskCommand` | Create or mutate one RawTask. |
| DraftTaskTree mutation | `MutateDraftTaskTreeCommand` | Create or mutate one DraftTaskTree. |
| Legacy draft publish | `PublishDraftTaskTreeCommand` | Publish accepted DraftTaskTree nodes through the legacy TaskPublisher draft path. |
| Durable Plan publish | `PublishPlanCommand` | Publish durable Plan/TaskNode rows through `DefaultPlanPublisher`. |
| UI command response idempotency | `UiCommandResponseIdempotencyStore` | Replay or reject duplicate HTTP command responses. |

Only the first three command types are members of the current
`AuthoringCommand` union and can be submitted through
`AuthoringCommandBatch`.

`PublishPlanCommand` is a sibling command boundary in
`src/taskweavn/task/plan_publisher.py`. It is not submitted through
`DefaultAuthoringCommandService`.

---

## 3. Authoring Command Models

### 3.1 ActorRef

`ActorRef` identifies the actor that submitted a command.

Current fields:

- `actor_id`
- `kind`: `user`, `collaborator`, `agent`, `system`, or `api`
- optional `display_name`

Current command models require the command actor to match the batch actor.
The default command service does not currently implement a separate
authorization policy check beyond typed validation and store/domain rules.

### 3.2 MutateRawTaskCommand

`MutateRawTaskCommand` can create or mutate one RawTask.

Current fields include:

- `command_id`
- `session_id`
- optional `raw_task_id`
- `actor`
- optional `causation_message_id`
- optional `expected_version`
- optional `idempotency_key`
- `operations`

Current model rule:

- non-create commands require `raw_task_id`;
- create commands may omit `raw_task_id` and let the payload or service
  generate one.

Current implemented RawTask operations:

| Operation | Current behavior |
|---|---|
| `create` | Builds a new RawTask from `source_message_id`, `user_input`, optional ids, summary, constraints, and assumptions. |
| `set_intent_summary` | Replaces `intent_summary`. |
| `record_feasibility` | Validates `FeasibilityReport` and derives RawTask status unless payload overrides it. |
| `add_clarification_ask` | Appends a `RawTaskAsk` and sets status to `awaiting_user`. |
| `apply_answer` | Appends one `RawTaskAnswer`, rejects unknown or already answered asks, and sets status to `awaiting_user` or `assessing` unless payload overrides it. |
| `update_constraints` | Adds/removes constraint strings. |
| `update_assumptions` | Adds/removes assumption strings. |
| `set_status` | Replaces RawTask status and relies on RawTask model validators for legal shape. |

RawTask create also updates active authoring state when an
`AuthoringStateStore` is configured.

### 3.3 MutateDraftTaskTreeCommand

`MutateDraftTaskTreeCommand` can create or mutate one DraftTaskTree.

Current fields include:

- `command_id`
- `session_id`
- optional `draft_tree_id`
- optional `raw_task_id`
- `actor`
- optional `causation_message_id`
- optional `expected_version`
- optional `idempotency_key`
- `operations`

Current model rule:

- non-create commands require `draft_tree_id`;
- create commands may omit `draft_tree_id` because the store creates the tree.

Current implemented DraftTaskTree operations:

| Operation | Current behavior |
|---|---|
| `create_tree` | Creates a DraftTaskTree with roots and recursive children. If a PlanStore is configured, creates a durable Plan from the draft tree and records the active Plan id in active authoring state. |
| `patch_node` | Applies `TaskNodePatch` to one draft node with version checking. |
| `add_node` | Adds a node to an existing draft tree with tree-version checking. |
| `attach_options` | Produces an actionable `AuthoringMessageEffect`; it does not persist a draft-node option model. |
| `mark_accepted` | Marks the tree accepted through the draft store. |
| `mark_ready` | Returns a `mark_ready_noop` warning. |

Declared but not currently implemented by `DefaultAuthoringCommandService`:

- `remove_node`
- `reorder_siblings`

Submitting those operations to the default service currently returns a
structured invalid-command result.

### 3.4 PublishDraftTaskTreeCommand

`PublishDraftTaskTreeCommand` publishes the legacy DraftTaskTree path.

Current fields:

- `command_id`
- `session_id`
- `draft_tree_id`
- `actor`
- optional `expected_version`
- required `idempotency_key`
- `publish_options`

Current model rule:

- `idempotency_key` is required and must not be blank.

Current service behavior:

- requires `task_publisher` to be configured;
- loads the DraftTaskTree and all nodes;
- rejects empty trees;
- rejects already-published or cancelled nodes;
- rejects nodes that are not `accepted`;
- rejects partial root publish when requested roots differ from all root ids;
- checks `expected_version` when provided;
- optionally runs `DraftTaskTreeValidator`;
- calls `TaskPublisher.publish_draft_tree(session_id, draft_tree_id)`;
- validates publisher mappings for every draft node;
- marks draft nodes published and stores draft-to-published mappings;
- marks active authoring state published when an `AuthoringStateStore` is
  configured;
- emits an informational message effect after successful publish.

`PublishOptions.start_immediately` is currently included in the publish message
context for the legacy draft path. The legacy `publish_draft_tree(...)` call
does not receive that flag as a separate argument.

### 3.5 AuthoringCommandBatch

`AuthoringCommandBatch` groups one or more authoring commands.

Current fields:

- `batch_id`
- `session_id`
- `actor`
- optional `causation_message_id`
- optional `idempotency_key`
- `mode`: `all_or_nothing` or `best_effort`
- `commands`

Current model rules:

- every command must match the batch `session_id`;
- every command must match the batch `actor`;
- `best_effort` batches cannot include `PublishDraftTaskTreeCommand`;
- publish batches must use `all_or_nothing`.

The original recommendation to prefer coarse object-scoped commands is still
consistent with implementation, but the current service supports multiple
commands in one batch only when rollback prerequisites are available.

### 3.6 AuthoringCommandResult

`AuthoringCommandResult` is the backend result shape returned by
`AuthoringCommandService`.

Current fields:

- `ok`
- optional `batch_id`
- `applied_command_ids`
- `object_refs`
- `message_effects`
- `emitted_message_ids`
- `errors`
- `warnings`

Current model rules:

- accepted results must not include errors;
- rejected results must include at least one error;
- `accepted` and `status` are convenience properties derived from `ok`.

### 3.7 AuthoringMessageEffect

`AuthoringMessageEffect` is a requested message side effect.

Current fields:

- `message_type`: `informational` or `actionable`
- `content`
- optional `task_id`
- `context`
- `action_options`
- `requires_response`

Current model rules:

- `requires_response=True` requires `message_type="actionable"`;
- actionable response effects require at least one action option.

`DefaultAuthoringCommandService` converts message effects to `AgentMessage`
only after commands have been applied and only when a `MessageBus` is
configured.

---

## 4. DefaultAuthoringCommandService Behavior

Current submit flow:

```text
AuthoringCommandBatch
  -> resolve idempotency key
  -> replay cached result if present
  -> snapshot RawTask/DraftTask stores for all_or_nothing mode
  -> apply commands in order
  -> restore snapshots on all_or_nothing failure
  -> publish message effects
  -> cache terminal result when idempotency key is present
  -> return AuthoringCommandResult
```

### 4.1 Idempotency Key Resolution

The command service uses this effective idempotency key:

1. `batch.idempotency_key`, if present.
2. The single command's `idempotency_key`, if the batch has exactly one
   command.
3. No authoring command idempotency key for multi-command batches without a
   batch key.

### 4.2 Error Mapping

Exceptions are converted to structured `AuthoringCommandError` objects:

| Exception kind | Current error code |
|---|---|
| `LookupError` | `not_found` |
| `ValidationError`, `ValueError`, `TypeError` | `invalid_command` |
| `NotImplementedError` | `not_implemented` |
| `TaskStoreError` | `store_error` |
| other exceptions | `authoring_error` |

Unsupported declared DraftTaskTree operations currently raise `ValueError` and
therefore surface as `invalid_command`, not `not_implemented`.

### 4.3 Transaction And Rollback Limits

Current rollback is narrower than a full product transaction.

`DefaultAuthoringCommandService._snapshot(...)` snapshots only:

- `RawTaskStore`
- `DraftTaskStore`

when those stores expose `_snapshot` / `_restore`.

If an all-or-nothing multi-command batch cannot snapshot both stores, the
service rejects the batch with `transaction_unavailable`.

Current rollback does not snapshot or restore:

- `PlanStore`
- `AuthoringStateStore`
- `MessageBus`
- HTTP UI command response idempotency records
- publish control-plane stores outside this service

Message effects are published after command application, so failed
all-or-nothing command application does not publish those effects. However,
Plan creation and active-state changes performed during a command are not
covered by the RawTask/DraftTask snapshot mechanism.

---

## 5. Idempotency Layers

There are two separate idempotency layers and they intentionally have different
semantics.

### 5.1 Authoring Command Result Idempotency

Implemented by:

- `AuthoringCommandIdempotencyRecord`
- `InMemoryAuthoringCommandIdempotencyStore`
- `SqliteAuthoringCommandIdempotencyStore`

Current rule:

```text
The first result for (session_id, idempotency_key) is authoritative.
Reusing the key replays the cached AuthoringCommandResult.
```

The record stores a `request_hash`, but `DefaultAuthoringCommandService`
currently checks for an existing record by key and returns the cached result
without comparing the stored hash to the new request hash.

This behavior is documented by the RawTask/DraftTaskTree persistence plan and
covered by tests that replay idempotent authoring results across service
instances and SQLite reopen.

### 5.2 HTTP UI Command Response Idempotency

Implemented by:

- `UiCommandResponseIdempotencyRecord`
- `InMemoryUiCommandResponseIdempotencyStore`
- `SqliteUiCommandResponseIdempotencyStore`
- UI HTTP transport command route handling

Current rule:

```text
Same session + same idempotency key + same request hash:
  replay the first HTTP command response.

Same session + same idempotency key + different request hash:
  return idempotency_conflict at the HTTP command boundary.
```

This layer wraps UI command gateway routes such as generate task tree, answer
authoring asks, repair authoring state, publish task tree, archive plan, and
other command routes.

### 5.3 Child Idempotency Keys

The UI command gateway derives child keys for compound operations:

- prompt-based task-tree generation may use `:raw` and `:tree` child keys;
- authoring ask batch answer may generate a tree with the `:tree` child key
  after all asks are answered.

This keeps one user-facing command idempotent while allowing subordinate
authoring operations to be independently replayable.

---

## 6. Validation Model

Current validation happens in several layers:

| Layer | Current implementation |
|---|---|
| Schema validation | Pydantic command, operation, result, and message-effect models. |
| Batch validation | Session and actor equality; no best-effort publish batches. |
| Version validation | Expected RawTask, DraftTaskNode, DraftTaskTree, and publish versions where commands provide them. |
| Domain validation | RawTask model validators, duplicate answer rejection, DraftTask publish preconditions. |
| Capability validation | Optional `DraftTaskTreeValidator` during legacy draft publish. |
| Publish validation | Accepted nodes, full-root publish only, mapping completeness, publisher root consistency. |
| UI gateway validation | RawTask readiness before generation, stale authoring ask rejection, active draft identity resolution. |
| HTTP route validation | Command request parsing and HTTP idempotency conflict detection. |

Current limitations:

- There is no separate authorization/policy engine in
  `DefaultAuthoringCommandService`.
- Draft capability validation is optional and publish-time for the legacy draft
  path.
- `remove_node` and `reorder_siblings` have no default service handlers.
- Durable Plan patch/create/delete contract revision commands are future work.

---

## 7. Collaborator And UI Entry Points

### 7.1 Collaborator API Adapter

`DefaultCollaboratorApiAdapter` converts product actions into authoring
commands and stable `CommandResult` objects.

Current examples:

- `append_session_message(...)` publishes a user message and asks the
  Collaborator authoring service to create a RawTask.
- `answer_raw_task_ask(...)` and `answer_raw_task_asks(...)` submit
  `MutateRawTaskCommand` operations with `apply_answer`.
- `generate_task_tree(...)` delegates to the Collaborator authoring service.
- `append_task_message(...)` supports draft task refinement only.
- `publish_task_tree(...)` first submits `mark_accepted`, then submits
  `PublishDraftTaskTreeCommand` for the legacy DraftTaskTree path.

### 7.2 UI Command Gateway

`DefaultUiCommandGateway` is the UI-facing command boundary.

Current authoring-relevant behavior:

- `generate_task_tree` rejects a supplied RawTask that is not ready for
  planning.
- prompt-based `generate_task_tree` can create a RawTask and then create a
  task tree when the RawTask is ready.
- `answer_authoring_ask_batch` rejects stale authoring context when an active
  DraftTaskTree, published state, cancelled state, or existing task tree has
  superseded the RawTask.
- `answer_authoring_ask_batch` submits multiple RawTask answers and then
  triggers task-tree generation when all required asks are answered.
- `repair_authoring_state` can cancel a dirty active RawTask flow when an
  existing TaskTree proves authoring moved on.
- `publish_task_tree` publishes an active durable Plan first when a PlanStore
  and PlanPublisher are available; otherwise it falls back to legacy
  DraftTaskTree publish.
- if active Plan publish rejects, the gateway does not fall back to legacy
  draft publish for that request.

### 7.3 Runtime Input Router

Runtime Input Router sits in front of authoring and execution commands. It can
route guidance, ASK answers, confirmations, stop/retry commands, read-only
inquiry, and execution handoff.

It is not the source of truth for RawTask, DraftTaskTree, Plan, or TaskBus
facts. It delegates mutations to command services and gateways.

---

## 8. Publish Boundaries

### 8.1 Durable Plan Publish

Product 1.1 durable Plan publish is implemented by:

- `PublishPlanCommand`
- `PublishPlanResult`
- `PlanTaskPublishMapping`
- `DefaultPlanPublisher`

Current behavior:

- loads Plan and TaskNodes from `PlanStore`;
- skips empty, cancelled, or archived Plans;
- rejects partial published lineage as unsafe;
- replays complete existing lineage without duplicate TaskBus writes;
- maps each flat TaskNode to a root `NormalizedTaskNode`;
- calls `TaskPublisher.publish(...)`;
- writes `published_ref`, readiness `published`, execution `pending`, and Plan
  status `published` back to the Plan store.

The UI publish command prefers this path when an active durable Plan exists.

### 8.2 Legacy DraftTaskTree Publish

Legacy DraftTaskTree publish remains implemented for compatibility:

```text
PublishDraftTaskTreeCommand
  -> DefaultAuthoringCommandService
  -> TaskPublisher.publish_draft_tree(...)
  -> DraftToPublishedMapping
  -> TaskBus PublishedTasks
```

This path is still used by `DefaultCollaboratorApiAdapter.publish_task_tree`
and by the UI command gateway when no active durable Plan publish path is
available.

---

## 9. Audit And Traceability

Current traceability is distributed across durable facts rather than one typed
authoring event stream.

Current sources:

- RawTask snapshots and versions;
- DraftTaskTree and DraftTaskNode facts;
- durable Plan and PlanTaskNode rows;
- authoring command results and object refs;
- idempotency records;
- MessageStream entries emitted from validated message effects or adapter
  methods;
- DraftToPublishedMapping and PlanTaskPublishMapping;
- publish control-plane idempotency and audit records;
- UI command response records;
- query projections and diagnostics.

Typed authoring events such as `RawTaskCreated`,
`RawTaskAskAnswered`, or `DraftTaskTreePublished` are not currently
implemented as a dedicated EventStream.

---

## 10. Current Test Coverage

Direct tests cover:

- authoring command model validation;
- command batch session and actor validation;
- best-effort publish rejection;
- message-effect shape validation;
- command result shape validation;
- RawTask create, clarification, answer, duplicate-answer, and status flows;
- DraftTaskTree create, recursive child creation, patch, add, attach options,
  accept, and no-op readiness;
- durable Plan creation from draft output and active Plan identity;
- authoring command idempotency replay across service instances;
- SQLite authoring command idempotency reopen and replay;
- legacy DraftTaskTree publish validation, idempotency replay, mapping checks,
  duplicate publish rejection, and publisher rejection behavior;
- Collaborator API adapter answer, batch answer, generate tree, and publish
  behavior;
- UI command gateway RawTask readiness, stale authoring ask rejection,
  auto-generation after batch answers, repair authoring state, Plan publish
  preference, legacy fallback, and no fallback after Plan publish rejection;
- HTTP UI command response idempotency replay and conflict behavior;
- Plan publisher mapping, existing lineage replay, partial lineage rejection,
  and Plan status/writeback behavior.

---

## 11. Future Work

Future work should stay explicit:

1. Add durable Contract Revision commands for Plan/TaskNode patch, create,
   reorder, and delete.
2. Decide whether `remove_node` and `reorder_siblings` should be implemented
   for legacy DraftTaskTree or only for durable Plan/TaskNode.
3. Replace `mark_ready` no-op semantics if persisted readiness becomes a real
   domain state.
4. Decide whether all-or-nothing batches must become a true transaction across
   RawTaskStore, DraftTaskStore, PlanStore, active authoring state, and command
   idempotency.
5. Add explicit actor permission policy if product roles require it.
6. Add typed authoring EventStream events only when a consumer needs durable
   event replay rather than state snapshots and idempotency records.
7. Remove legacy DraftTaskTree publish only after frontend, router, projection,
   and audit paths no longer depend on it.

---

## 12. Summary

The current command protocol is:

```text
Collaborator / UI / runtime router
  -> typed command or publisher command
  -> deterministic backend service
  -> authoring stores / Plan stores / messages / publish boundary
  -> TaskBus only after publish
```

The stable product rule remains:

```text
Tools change the outside world.
Commands change TaskWeavn state.
LLM proposes.
Code validates and commits.
RawTask authoring is exploratory.
PublishedTask execution is strongly validated and audited.
```

The current implementation is more concrete than the original proposal:
RawTask/DraftTaskTree commands, authoring idempotency, SQLite stores, UI
command response idempotency, durable Plan publish, and legacy draft publish
all exist. The remaining risks are mostly around legacy operation gaps,
transaction boundaries, and future Plan/TaskNode contract revision commands.
