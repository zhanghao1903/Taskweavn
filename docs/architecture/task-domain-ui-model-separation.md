# Task Domain / UI Model Separation

> Status: fact-calibrated current architecture
>
> Last Updated: 2026-07-10
>
> Original preserved at:
> [task-domain-ui-model-separation.original.md](archive/original/task-domain-ui-model-separation.original.md)
>
> Fix log:
> [fix-log/task-domain-ui-model-separation.md](fix-log/task-domain-ui-model-separation.md)

## 1. Purpose

This document records the current separation between backend task facts, the
server UI contract, and frontend-only interaction state.

The important current fact is that Product 1.1 is no longer centered only on
`RawTask -> DraftTaskTree -> PublishedTask`. The current implementation has a
durable `Plan -> PlanTaskNode[]` product contract, with legacy `DraftTaskTree`
and published `TaskDomain` facts still present for compatibility and execution.

The architecture rule remains:

```text
domain facts are stored and mutated by backend services
projection models are read-only derived views
frontend state is local interaction state
```

UI components must not invent backend task facts, and backend domain models
must not absorb card layout, selected state, expanded state, local pending
flags, or other presentation-only details.

## 2. Current Source Of Truth Map

| Area | Current source of truth | Current projection / consumer |
|---|---|---|
| User intent authoring before planning | `RawTask` and `RawTaskAsk` in `task.authoring` | `PlanningView` in the Main Page snapshot |
| Legacy draft task authoring | `DraftTaskTree` and `DraftTaskNode` in `task.models` | server-core `task.views.TaskTreeView`, then UI-contract `TaskTreeView` |
| Product 1.1 plan contract | `Plan` and `PlanTaskNode` in `task.plan_models` | `PlanView` and `TaskNodeCardView` |
| Executable task state | `TaskDomain` in `task.models` | server-core task projection, Plan lifecycle sync, result/file/audit projections |
| Runtime input and command outcomes | Runtime Input Router, Contract Revision command services, `MessageStream` activity publishers | `RuntimeInputRouteResult`, `SessionMessageView`, `SessionActivityItemView` |
| ASK and confirmation state | ASK store/service and actionable messages | `AskRequestView`, `ConfirmationActionView`, Activity items |
| Results and file changes | task summary and file-change stores | `ResultCardView`, `FileChangeSummaryView` |
| Audit and diagnostics | audit providers, workspace evidence, diagnostic bundle exporters | Audit Page snapshot, Audit links, Activity refs |
| Main Page presentation state | React controller/view-model state | selected task, detail mode, pending command flags, overlays, input mode |

`TaskTreeView`, `TaskNodeCardView`, `PlanView`, `SessionActivityItemView`, and
the frontend Main Page view model are not authoritative storage. They are
derived contracts for rendering and user action routing.

## 3. Domain Facts

### 3.1 Execution Task

`TaskDomain` is the published execution fact used by TaskBus and agents. It
stores scheduling and execution state:

- identity: `task_id`, `session_id`, `parent_id`, `root_id`, `order_index`;
- work contract: `intent`, `summary`, `instructions`,
  `acceptance_criteria`, `required_capability`, dispatch constraints;
- execution: `pending`, `running`, `waiting_for_user`, `done`, `failed`;
- result and failure refs;
- user-wait linkage through ASK or confirmation ids;
- interrupt request metadata.

It intentionally does not contain UI card badges, selected state, expanded
state, unread counters, frontend overlays, or button layout.

### 3.2 Legacy Draft Authoring

`DraftTaskNode` and `DraftTaskTree` remain the legacy authoring facts. A draft
node records draft identity, task text, acceptance criteria, required
capability, constraints, status, version, and timestamps. A draft tree groups
root draft nodes for a session.

This path still matters because old sessions and some compatibility projections
continue to read draft trees. It is not the only product contract anymore.

### 3.3 Durable Plan And TaskNode

`Plan` and `PlanTaskNode` are the Product 1.1 durable planning contract. They
sit beside the legacy draft models.

`Plan` records plan identity, session identity, title, objective, summary,
status, task node ids, context policy, finalization state, optional outcome,
version, and archive time.

`PlanTaskNode` records stable Product 1.1 task-node identity, plan/session
identity, flat ordering, title, intent, summary, instructions, capability,
dependencies, constraints, acceptance criteria, readiness, execution,
draft/published refs, result/file/audit refs, version, and timestamps.

The first Product 1.1 implementation is flat:

```text
Session -> active Plan -> ordered PlanTaskNode list
```

Legacy tree hierarchy may still appear in compatibility `task_tree_projection`,
but `PlanView.task_nodes` is a flat list.

## 4. Projection Stack

### 4.1 Server-Core Task Views

`src/taskweavn/task/views.py` defines server-core read models such as
`TaskCardView`, `TaskTreeView`, `TaskDetailView`, `SessionMessageView`,
`ConfirmationActionView`, file summaries, and result summaries.

That module explicitly states that these are not backend task facts and not
transport-facing UI contracts. They are internal read models projected from
`TaskDomain`, `DraftTaskNode`, messages, confirmations, files, summaries, and
permission rules.

### 4.2 Task Projection Service

`DefaultTaskProjectionService` is read-only. It can project:

- legacy draft cards from `DraftTaskStore`;
- published execution cards from `TaskStore`;
- messages and pending actionable confirmations from `MessageStream`;
- recursive or direct file-change summaries;
- result summaries.

It exposes both `list_task_tree` and `list_plan_tree`. `list_plan_tree` projects
the Product 1.1 surface as a flat TaskNode list while preserving older storage
paths under the hood.

### 4.3 Transport UI Contract

`src/taskweavn/server/ui_contract/view_models.py` is the transport-facing
contract consumed by the frontend. The current Main Page contract includes:

- `MainPageSnapshot`;
- `PlanningView`;
- `PlanView`;
- compatibility `TaskTreeView`;
- `TaskNodeCardView`;
- `SessionMessageView`;
- `AskRequestView`;
- `ConfirmationActionView`;
- `ResultCardView`;
- `FileChangeSummaryView`;
- `SessionActivityItemView`.

`TaskNodeCardView` currently carries `status` and `execution`. The canonical
status-model direction separates planning, readiness, execution, confirmation,
permission, and audit verdict, but the backend transport model is still partly
in transition. The frontend TypeScript type reserves optional `readiness`,
`readonlyReason`, and `availableActions` fields, while the current Python
transport model does not consistently emit those task-node fields yet.

This means consumers must treat `TaskNodeStatus` as a compatibility display
status, not as the sole canonical task fact.

### 4.4 Plan Projection

`DefaultPlanProjectionService` has two current projection paths:

1. `project_stored_plan(plan, task_nodes)` projects durable `Plan` and
   `PlanTaskNode` rows into `PlanView`.
2. `project_legacy_task_tree(task_tree)` derives a synthetic `PlanView` from a
   legacy UI-contract `TaskTreeView`.

For stored plans, the projection maps:

- `Plan.status` to `PlanUiStatus`;
- `PlanTaskNode.readiness` and `PlanTaskNode.execution` into compatibility
  `TaskNodeCardView.status` and `execution`;
- intentional stop failures with `error_ref` prefixes such as `cancelled:` or
  `skipped:` into cancelled UI status/execution;
- node execution counts into `ExecutionRollupView`;
- finalization and outcome into `PlanFinalizationView` and `PlanOutcomeView`;
- task-node permissions from readiness and execution state.

For legacy task trees, `PlanView.task_nodes` is flattened and receives stable
task indexes. `PlanView.task_tree_projection` keeps the compatibility tree
shape for existing components.

### 4.5 Main Page Snapshot Read Path

The default snapshot query path is plan-aware:

1. Load the session.
2. Load the current legacy projection through `list_plan_tree` when available,
   falling back to `list_task_tree`.
3. Map the server-core tree into the UI-contract `TaskTreeView`.
4. Resolve the active stored plan from `PlanStore` and active authoring state.
5. Prefer the stored plan when available.
6. Fall back to a synthetic legacy plan when no stored plan exists.
7. Suppress active legacy fallback when the active stored plan is archived.
8. Add archived plan views.
9. Merge task-tree messages, session messages, and archived-plan messages.
10. Project confirmations, planning state, pending asks, active ASK, result,
    file-change summary, audit links, and cursor.

`MainPageSnapshot` also has a compatibility validator that derives
`active_plan` from `task_tree` if older callers provide only a legacy task tree.

## 5. Command And Mutation Boundary

Frontend actions must enter through command gateways or the Runtime Input
Router. They must not mutate backend domain facts directly.

The current command gateway includes implemented paths for:

- appending session input;
- generating task trees;
- updating task nodes;
- appending task input or guidance;
- publishing an active durable plan when available, with legacy draft-tree
  fallback;
- archiving durable and legacy plans;
- retrying and stopping published tasks;
- resolving confirmations;
- answering, deferring, and cancelling execution ASKs;
- answering raw-task authoring ASKs;
- repairing superseded authoring state.

The Runtime Input Router contract accepts a session/plan/task selection and
routes input as question, guidance, command, ASK answer, confirmation response,
execution request, clarification, or unsupported input. Route results include a
decision, an outcome, optional activity, optional command response, and optional
read-only inquiry result.

Contract Revision command skills now provide command-backed Plan/TaskNode patch,
create, delete, guidance, ASK/confirmation resolution, and execution handoff
behavior. These command paths are product-state mutations and must remain
auditable and idempotent.

## 6. Activity, Results, Files, Audit, And Diagnostics

Activity is currently projected from safe UI facts, not from raw domain tables.
`DefaultSessionActivityProjectionService` combines messages, active and
archived plans, task nodes, ASKs, confirmations, result cards, and file-change
summaries into `SessionActivityTimelineResult`.

Runtime Input and Contract Revision publishers also write durable messages that
can replay as Activity after reload. Activity items preserve scope, side effect,
related refs, source kind, source id, and disclosure level.

Result and file-change summaries prefer stored `PlanTaskNode` identity when a
stored plan exists. The read helpers fall back to legacy task refs only when
legacy fallback is allowed.

Audit selected-task reads also normalize legacy task ids back to `PlanTaskNode`
ids where possible while preserving legacy refs as provenance. Diagnostic bundle
and router-specific evidence surfaces are separate trust outputs, not task
domain fields.

## 7. Frontend Responsibilities

The frontend consumes `MainPageSnapshot` and builds local view models in
`frontend/src/pages/main-page/mainPageViewModel.ts`.

Frontend-owned state includes:

- selected task or plan;
- detail mode and override;
- pending command flags;
- command errors and recovery actions;
- event connection state;
- runtime input mode and notices;
- overlay state and transient activity items;
- local focus/scroll behavior.

The frontend may derive labels, tones, grouped panels, button visibility, and
disabled display. It must not invent persisted task, plan, ASK, confirmation,
audit, or execution facts.

When the frontend needs a mutation, it uses the adapter command functions or
`routeRuntimeInput`. When it needs fresh facts, it reloads the snapshot,
activity timeline, Audit Page, or diagnostics through the supported query
interfaces.

## 8. Current Compatibility And Known Limits

Current compatibility is intentional:

- `DraftTaskTree` remains for old sessions and legacy authoring.
- `TaskTreeView` remains in `MainPageSnapshot` for existing frontend
  components.
- `PlanView.task_tree_projection` keeps the compatibility task-tree shape.
- `PlanView.task_nodes` is the Product 1.1 flat ordered list.
- `DefaultUiCommandGateway.publish_task_tree` publishes durable plans first and
  falls back to legacy draft-tree publishing.

Known limits and migration boundaries:

- Backend transport `TaskNodeCardView` still exposes a flattened `status`
  alongside `execution`; readiness is a stored `PlanTaskNode` fact and a
  frontend type reservation, but not consistently emitted as a first-class
  Python transport field.
- Server-core task permissions include richer read-only reasons and action
  lists than the current transport `TaskNodePermissions` shape exposes.
- Some frontend components still consume compatibility `taskTree` directly.
- Legacy draft-tree compatibility should be removed only after all router,
  Activity, Audit, detail, and frontend paths target durable Plan/TaskNode
  identity.
- Activity is a projected, user-readable timeline. It is not a replacement for
  audit records or diagnostic evidence.

## 9. Acceptance Criteria For Future Changes

Any future change to task/domain/UI boundaries should preserve these criteria:

1. Backend domain models store product and execution facts only.
2. Projection models remain read-only derived views.
3. New Product 1.1 features target `Plan` and `PlanTaskNode` identity first.
4. Legacy `DraftTaskTree` paths remain compatibility-only unless a specific
   migration task says otherwise.
5. Frontend-only state stays in React/controller/view-model state.
6. Mutations enter through command gateways, Runtime Input Router, or dedicated
   backend services.
7. Snapshot, Activity, Audit, result, file, and diagnostic projections do not
   leak raw provider payloads, secrets, absolute local paths, or internal logs.
8. Status changes keep readiness, execution, confirmation, permission, and
   audit concepts separate even when compatibility fields still collapse them.

## 10. Verification References

Current behavior is covered by targeted tests including:

- `tests/test_task_views.py`;
- `tests/test_task_projection.py`;
- `tests/test_plan_view_contract.py`;
- `tests/test_plan_store.py`;
- `tests/test_plan_publisher.py`;
- `tests/test_plan_lifecycle.py`;
- `tests/test_ui_query_gateway.py`;
- `tests/test_ui_command_gateway.py`;
- `tests/test_session_activity_projection.py`;
- `tests/test_runtime_input_router.py`;
- `tests/test_contract_revision_commands.py`;
- frontend Main Page view-model, selector, runtime-input, workbench, and
  activity-overlay tests.
