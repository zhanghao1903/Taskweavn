# Authoring Domain Architecture

> Status: fact-calibrated current implementation / Plan migration compatibility
> Last Updated: 2026-07-11
> Original preserved as: `docs/architecture/authoring-domain.original.md`
> Related ADR: [ADR-0008](../decisions/ADR-0008-authoring-domain-execution-boundary.md)
> Related Plans:
> [Collaborator Agent](../plans/feature/collaborator-agent-task-authoring.md),
> [RawTask And DraftTaskTree Persistence](../plans/feature/raw-task-draft-tree-persistence.md),
> [ASK Domain Unification And Batch Answer](../plans/feature/ask-domain-unification-batch-answer.md),
> [Plan / TaskNode Contract Migration](../plans/feature/plan-tasknode-contract-migration.md)
> Related Architecture:
> [Authoring Command Protocol](authoring-command-protocol.md),
> [Collaborator Agent And Task Authoring](collaborator-agent-task-authoring.md),
> [Task](task.md),
> [TaskBus](bus.md)

Fact calibration note:

- Authoring Domain is implemented. It is not only a conceptual boundary.
- Product 1.1 adds durable `Plan` / `PlanTaskNode` facts beside the legacy
  `DraftTaskTree` compatibility path.
- `RawTaskAsk` does not currently have its own persisted `status` or
  `superseded_by_draft_tree_id` field. Supersession is represented by command
  gateway behavior and UI projection.
- `DraftTaskTree` does not currently have a tree-level
  `validating -> ready_to_publish` lifecycle. Current draft node statuses are
  `draft`, `accepted`, `published`, and `cancelled`.
- Typed authoring EventStream events remain future direction. Current durable
  authoring state is stored in authoring stores, Plan stores, messages, command
  results, mappings, and projections.

---

## 1. Purpose

Authoring Domain is the product-state boundary that turns natural-language
intent into a user-visible work contract before execution.

Current implemented path:

```text
User input
  -> Runtime Input Router or UI command gateway
  -> Collaborator proposal layer
  -> AuthoringCommandService
  -> RawTask / DraftTaskTree / durable Plan facts
  -> user confirmation or publish command
  -> PlanPublisher or legacy TaskPublisher path
  -> PublishedTask facts in TaskBus
```

The core rule is still:

```text
Authoring objects do not enter Execution TaskBus.
Only published execution Tasks enter TaskBus.
```

Runtime Input Router sits in front of this boundary. It can route guidance,
ASK answers, confirmation responses, read-only questions, stop/retry commands,
and execution handoff. It is not itself the Authoring Domain store authority.

---

## 2. Current Domain Split

| Domain | Current Responsibility | Current Core Objects | Authority |
|---|---|---|---|
| Authoring Domain | Capture uncertain intent, ask planning questions, generate editable work contracts, and publish confirmed work. | `RawTask`, `FeasibilityReport`, `RawTaskAsk`, `RawTaskAnswer`, `DraftTaskTree`, `DraftTaskNode`, `Plan`, `PlanTaskNode`, authoring command results. | Authoring stores, Plan stores, command services, UI projections. |
| Execution Domain | Run confirmed executable tasks and produce results, file-change summaries, waits, retries, and failures. | `TaskDomain`, `TaskRunResult`, execution-plane `TaskExecution` / `TaskResult` / `TaskError`, execution `AskRequest`, result/file/audit records. | TaskBus, execution services, execution ASK store, result stores. |

Two publish paths currently coexist:

- Durable Plan publish: `DefaultPlanPublisher.publish_plan(...)` adapts flat
  `PlanTaskNode` rows to the existing `TaskPublisher` / `PublishRequest`
  boundary.
- Legacy DraftTaskTree publish: `PublishDraftTaskTreeCommand` publishes accepted
  draft nodes through `TaskPublisher.publish_draft_tree(...)`.

The UI command gateway prefers an active durable Plan when one exists and falls
back to legacy DraftTaskTree publish for old or compatibility sessions.

---

## 3. Current Authoring Objects

### 3.1 RawTask

`RawTask` is implemented in `src/taskweavn/task/authoring.py`.

Current fields include:

- `raw_task_id`
- `session_id`
- `source_message_id`
- `user_input`
- `status`
- `intent_summary`
- `feasibility`
- `asks`
- `answers`
- `constraints`
- `assumptions`
- `version`
- `created_by`
- timestamps

Current `RawTask.status` values:

- `created`
- `assessing`
- `awaiting_user`
- `ready_to_plan`
- `converted`
- `rejected`
- `cancelled`

Current validators enforce:

- `awaiting_user` requires at least one unanswered required ask.
- `ready_to_plan` requires feasibility with `ready` or `partially_feasible`.
- `rejected` with feasibility requires `not_supported` or `unsafe`.
- asks and answers must belong to the same RawTask.
- answers must reference existing asks.

`RawTask` is not executable. It has no execution `required_capability`, cannot
be claimed by execution Agents, and does not use execution statuses such as
`pending`, `running`, `waiting_for_user`, `done`, or `failed`.

### 3.2 FeasibilityReport

`FeasibilityReport` is implemented as a structured planning assessment.

Current statuses:

- `ready`
- `needs_clarification`
- `needs_user_permission`
- `partially_feasible`
- `not_supported`
- `unsafe`

Current next actions:

- `generate_task_tree`
- `ask_user`
- `offer_alternatives`
- `decline`

Defaults are derived from status when `suggested_next_action` is omitted.
Validation requires clarification or permission statuses to carry missing input
or permission context.

### 3.3 RawTaskAsk And RawTaskAnswer

`RawTaskAsk` and `RawTaskAnswer` are embedded authoring facts on `RawTask`.

Current `RawTaskAsk` fields:

- `ask_id`
- `raw_task_id`
- `question`
- `options`
- `required`
- `reason`
- `created_by`
- `created_at`

Current `RawTaskAnswer` fields:

- `answer_id`
- `raw_task_id`
- `ask_id`
- `value`
- `source_message_id`
- `created_at`

Important correction:

```text
RawTaskAsk does not currently persist status, expired/cancelled state,
or superseded_by_draft_tree_id.
```

Authoring ASK state is derived from RawTask answers and projections:

- unanswered required asks make a RawTask `awaiting_user`;
- answered asks are detected by matching answer `ask_id`;
- when a task tree exists, planning projection marks authoring asks as
  `superseded`;
- the UI command gateway rejects authoring ask answers when the authoring
  context was superseded by an active TaskTree or published work.

Execution ASK remains separate. It uses `AskRequest` / `AskStore` and blocks
published execution tasks, not RawTask planning.

---

## 4. Draft Compatibility And Plan Contract

### 4.1 DraftTaskTree And DraftTaskNode

Legacy draft authoring facts are implemented in `src/taskweavn/task/models.py`.

`DraftTaskTree` fields include:

- `draft_tree_id`
- `session_id`
- `title`
- `summary`
- `root_nodes`
- `created_by`
- `version`
- timestamps

`DraftTaskNode` fields include:

- `draft_task_id`
- `session_id`
- `draft_tree_id`
- optional `parent_draft_task_id`
- `order_index`
- title, intent, summary, instructions, acceptance criteria
- `required_capability`
- constraints and rationale
- `status`
- `version`
- timestamps

Current `DraftTaskNode.status` values:

- `draft`
- `accepted`
- `published`
- `cancelled`

There is no current tree-level `validating` or `ready_to_publish` status.
Validation is represented by `DraftTaskTreeValidator` results and command
responses, not by a persisted DraftTaskTree lifecycle state.

### 4.2 Durable Plan And PlanTaskNode

Product 1.1 adds durable Plan facts in `src/taskweavn/task/plan_models.py`.

`Plan` carries:

- `plan_id`
- `session_id`
- optional `source_raw_task_id`
- optional `source_draft_tree_id`
- title, objective, summary
- `status`
- `task_node_ids`
- context policy
- finalization state
- optional outcome
- archive metadata

`PlanTaskNode` carries:

- `task_node_id`
- `plan_id`
- `session_id`
- flat `task_index`
- order, title, intent, summary, instructions
- optional `required_capability`
- dependencies, constraints, acceptance criteria
- readiness and execution status
- optional `draft_ref` and `published_ref`
- result, error, file summary, and audit refs

Current Product 1.1 shape is:

```text
Session
  -> active Plan
      -> flat TaskNode list
```

Legacy DraftTaskTree facts remain compatibility storage and projection data.
New Product 1.1 contract work can target durable `Plan` / `PlanTaskNode`
identity.

### 4.3 Draft-To-Plan Adapter

`build_plan_from_draft_tree(...)` converts legacy draft output into durable Plan
facts.

Current behavior:

- creates one `Plan` from a `DraftTaskTree`;
- flattens draft nodes in preorder;
- reuses `DraftTaskNode.draft_task_id` as `PlanTaskNode.task_node_id`;
- records `source_raw_task_id` and `source_draft_tree_id`;
- maps draft node status to PlanTaskNode readiness;
- stores `draft_ref` links for identity continuity.

`DefaultAuthoringCommandService` calls this adapter during `create_tree` when a
`PlanStore` is configured, then records the created `plan_id` in active
authoring state.

---

## 5. Active Authoring State

`ActiveAuthoringState` is implemented in `src/taskweavn/task/stores.py`.

Current fields:

- `session_id`
- `active_raw_task_id`
- `active_draft_tree_id`
- `active_plan_id`
- `active_state`
- `updated_at`

Current `active_state` values:

- `none`
- `raw_task`
- `draft_tree`
- `published`
- `cancelled`

`AuthoringStateStore` currently supports:

- `get_active`
- `set_active_raw_task`
- `set_active_draft_tree`
- `mark_published`
- `cancel_active`

SQLite authoring state is implemented by `SqliteAuthoringStateStore` and
persists `active_plan_id`.

Current projection rules:

- active RawTask is selected from `AuthoringStateStore` when available;
- otherwise the latest RawTask for the session is used;
- when a task tree exists, planning asks from RawTask are projected as
  `superseded`;
- dirty active RawTask plus existing task tree yields a planning diagnostic;
- cancelled authoring state remains visible as traceable planning context.

Current command gateway safety rules:

- authoring ask batch answer rejects stale authoring context once an active
  draft tree, published state, cancelled state, or published task tree
  supersedes the RawTask;
- repair closes a dirty raw authoring flow by calling `cancel_active` when an
  existing TaskTree proves that planning moved on.

---

## 6. Stores And Persistence

### 6.1 Authoring Stores

Implemented protocols:

- `RawTaskStore`
- `DraftTaskStore`
- `AuthoringStateStore`
- `AuthoringCommandIdempotencyStore`

Implemented in-memory stores:

- `InMemoryRawTaskStore`
- `InMemoryDraftTaskStore`
- `InMemoryAuthoringCommandIdempotencyStore`

Implemented SQLite stores:

- `SqliteRawTaskStore`
- `SqliteDraftTaskStore`
- `SqliteAuthoringStateStore`
- `SqliteAuthoringCommandIdempotencyStore`

The main sidecar runtime uses SQLite authoring stores by default when no test
or caller dependency overrides them. These stores live in the workspace
authoring database.

### 6.2 Plan Store

Implemented Plan store protocol:

- `PlanStore`
- `PlanTaskNodeStore`

Implemented SQLite store:

- `SqlitePlanStore`

`SqlitePlanStore` creates additive tables in the same authoring database:

- `plan_schema_meta`
- `plans`
- `plan_task_nodes`

It leaves legacy DraftTaskTree tables and reads untouched.

### 6.3 Idempotency And Transaction Behavior

Authoring command idempotency is implemented by session and idempotency key.
The first stored result is authoritative and is replayed on retry.

`DefaultAuthoringCommandService` also supports all-or-nothing rollback for
multi-command batches when stores expose snapshot/restore support. Publish
batches cannot use best-effort mode.

---

## 7. Command Boundary

Authoring Domain mutations go through
[Authoring Command Protocol](authoring-command-protocol.md).

Current stable rule:

```text
LLM or UI proposes.
Code validates and normalizes.
AuthoringCommandService applies typed commands.
Stores/messages/publish boundaries mutate only after command validation.
```

Current RawTask operations handled by `DefaultAuthoringCommandService`:

- `create`
- `set_intent_summary`
- `record_feasibility`
- `add_clarification_ask`
- `apply_answer`
- `update_constraints`
- `update_assumptions`
- `set_status`

Current DraftTaskTree operations handled:

- `create_tree`
- `patch_node`
- `add_node`
- `attach_options`
- `mark_accepted`

Partial operation facts:

- `mark_ready` is handled as a no-op warning.
- `remove_node` is declared but not implemented by the command service.
- `reorder_siblings` is declared but not implemented by the command service.

`PublishDraftTaskTreeCommand` currently:

- requires all nodes to be `accepted`;
- rejects empty trees, already-published nodes, cancelled nodes, and partial
  root publish;
- optionally runs `DraftTaskTreeValidator`;
- calls `TaskPublisher.publish_draft_tree(...)`;
- requires publisher mappings for every draft node;
- marks draft nodes published and updates active authoring state.

---

## 8. Publish Boundary

### 8.1 Plan Publish

`DefaultPlanPublisher` is the current Product 1.1 publish adapter.

It:

- loads durable Plan and TaskNodes from `PlanStore`;
- skips plans with no TaskNodes;
- skips cancelled or archived plans;
- rejects partial existing lineage;
- maps each flat TaskNode to a root `NormalizedTaskNode`;
- calls the existing `TaskPublisher.publish(...)`;
- writes `published_ref`, readiness `published`, execution `pending`, and Plan
  status `published` back to the Plan store;
- replays complete existing lineage without creating duplicate TaskBus rows.

### 8.2 Legacy DraftTaskTree Publish

Legacy DraftTaskTree publish remains supported for compatibility:

```text
PublishDraftTaskTreeCommand
  -> DefaultAuthoringCommandService
  -> TaskPublisher.publish_draft_tree(...)
  -> DraftToPublishedMapping
  -> TaskBus PublishedTasks
```

This path remains necessary for older sessions and compatibility projections.

---

## 9. Collaborator And Runtime Input Boundaries

Collaborator is the primary natural-language proposal layer for authoring.

Current Collaborator facts:

- default template is metadata and has no LLM-visible execution tool pools;
- `DefaultCollaboratorAuthoringService` maps LLM/profile outputs to authoring
  commands;
- workspace-informed authoring can read/search bounded workspace context, but
  cannot write files or run commands;
- raw proposal payloads are not exposed as the stable UI/API surface.

Runtime Input Router is a front-door router:

- active execution ASK answers route to execution ASK commands;
- confirmation responses route to confirmation commands;
- guidance can route to contract revision command services;
- questions can route to read-only inquiry;
- workspace change requests can route to execution handoff.

Those routes may touch authoring-adjacent product state, but Runtime Input
Router is not the source of truth for RawTask, DraftTaskTree, Plan, or
PublishedTask facts.

---

## 10. ASK Domain Split

Current Product 1.0/1.1 has two ASK-like mechanisms.

| Area | Authoring ASK | Execution ASK |
|---|---|---|
| Source of truth | `RawTask.asks` and `RawTask.answers` | `AskStore` / `AskRequest` |
| Scope | RawTask planning | PublishedTask execution |
| UI projection | `PlanningAskView` inside planning state | `AskRequestView` / active ASK |
| Answer command | authoring ask batch answer through Collaborator API adapter and AuthoringCommandService | execution ASK answer through TaskAskCommandService |
| After answer | may generate a draft tree/Plan when all required asks are answered | resumes or dispatches a waiting execution task |
| Supersession | command gateway/projection behavior | ASK lifecycle statuses in AskStore |

Authoring and execution ASK can share UI primitives, but they must not share a
backend authority.

---

## 11. Event And Audit Facts

The previous architecture listed possible typed authoring events such as
`RawTaskCreated`, `RawTaskAskSuperseded`, and `DraftTaskTreePublished`.

Current implementation does not define a dedicated typed authoring EventStream
for those events.

Current traceability comes from:

- RawTask and DraftTaskTree store snapshots;
- Plan and PlanTaskNode rows;
- command result ids and affected refs;
- MessageStream user/collaborator/system messages;
- DraftToPublishedMapping and PlanTaskPublishMapping;
- publish idempotency/audit records in publish control-plane stores;
- runtime input activity/audit projections for router-driven flows.

Future typed authoring events may still be useful, but should be documented as
future work until implemented.

---

## 12. Current Test Coverage

Direct tests cover:

- RawTask, FeasibilityReport, RawTaskAsk, RawTaskAnswer, command, proposal, and
  validator contracts;
- PlanProposal flat task contract, ordering, dependencies, and hierarchy
  rejection;
- AuthoringCommandService mutation, rollback, idempotency, Plan creation, and
  publish behavior;
- in-memory and SQLite RawTask/DraftTaskTree stores;
- SQLite active authoring state, `active_plan_id`, publish marking, cancel, and
  migration behavior;
- SQLite Plan store persistence, task node uniqueness, dependencies, archive,
  and legacy DraftTaskTree read compatibility;
- Plan publisher mapping, lineage replay, partial lineage rejection, and legacy
  DraftTaskTree compatibility;
- UI command gateway authoring ask batch answers, stale ask rejection, dirty
  state repair, Plan publish preference, and legacy publish fallback;
- UI query gateway planning ask projection, superseded authoring ask projection,
  active stored Plan preference, and Plan/TaskNode read routing;
- ASK projection rules for execution ASK active selection.

---

## 13. Future Work

Future work should stay explicit:

1. Remove legacy DraftTaskTree compatibility only after frontend, router,
   projection, and audit paths no longer depend on it.
2. Decide whether `RawTask.status="converted"` should be actively written, or
   whether active state plus DraftTaskTree/Plan lineage is enough.
3. Decide whether `RawTaskAsk` needs persisted lifecycle status fields.
4. Implement or remove declared-but-unhandled DraftTaskTree operations
   `remove_node` and `reorder_siblings`.
5. Add typed authoring EventStream events only when a consumer needs them.
6. Complete Contract Revision commands for Plan/TaskNode create, patch,
   reorder, and delete.
7. Define Outcome Review and follow-up Plan cycle scopes.

---

## 14. Summary

The current Authoring Domain is:

```text
RawTask / Feasibility / RawTaskAsk
  + DraftTaskTree compatibility path
  + durable Plan / PlanTaskNode Product 1.1 path
  + command-backed mutation
  + active authoring state
  + PlanPublisher or legacy TaskPublisher publish
  -> Execution TaskBus only after publish
```

This preserves the original boundary goal while reflecting the current
implementation: Product 1.1 is no longer only RawTask -> DraftTaskTree ->
PublishedTask. Durable Plan / TaskNode identity is now part of the authoring
facts and should be treated as the primary current contract for new work.
