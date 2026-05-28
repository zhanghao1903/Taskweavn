# Plato Canonical Status Model

> Status: canonical proposal for migration planning
> Last Updated: 2026-05-24
> Scope: Product, backend UI contract, frontend ViewModel, mock data, Audit Page, confirmation, permission, and task execution UI.
> Non-goal: this document does not migrate code, refactor MainPage, change runtime behavior, or redesign UI.

## 1. Purpose

Plato currently exposes flattened UI statuses such as `SessionStatus`,
`TaskTreeStatus`, and `TaskNodeStatus`. Those values are useful for the first
Main Page slice, but they now collapse distinct product facts:

- planning state;
- task readiness;
- execution status;
- confirmation status;
- permission and action availability;
- audit verdict.

Audit Page, confirmation UX, permission-aware controls, and reliable task
execution UI require these dimensions to be represented independently.

This document defines the canonical status dimensions, maps current flat
statuses to the target model, inventories current collapse points, and proposes
an incremental migration plan.

## 2. Source Inventory

### 2.1 Product and UX sources

| Source | Current role |
|---|---|
| `docs/product/plato-main-page-ux-flow.md` | Defines Main Page user flow from input to TaskTree, execution, confirmation, result, file changes, and Audit entry. |
| `docs/product/plato-audit-page-ux-flow.md` | Defines Audit Page as read-only Trust Plane with scope, filters, evidence records, detail, partial/failed/inconclusive states, config, and logs reservations. |
| `docs/ux/screen-state-spec.md` | Already states that planning, readiness, execution, confirmation, and audit verdict must not be collapsed into one status field. |
| `docs/frontend/ui-viewmodel-contract.md` | Draft target frontend contract with separated fields. |
| `docs/frontend/api-ui-mapping.md` | Draft backend-to-UI mapping and migration checklist. |

### 2.2 Current frontend transport types

Current frontend API types in `frontend/src/shared/api/types.ts` expose:

| Type | Current values | Issue |
|---|---|---|
| `SessionStatus` | `new`, `understanding`, `draft_ready`, `running`, `waiting_user`, `completed`, `failed` | Mixes planning, task execution, confirmation, and session lifecycle. |
| `TaskTreeStatus` | `draft`, `published`, `running`, `completed`, `failed` | Mixes tree readiness with execution rollup. |
| `TaskNodeStatus` | `draft`, `queued`, `running`, `waiting_user`, `done`, `failed`, `cancelled` | Mixes readiness, execution, confirmation, and UI label. |
| `ConfirmationActionView.status` | `pending`, `resolved`, `expired` | Correct backend fact, but frontend local `resolving` and `resolve_failed` are not modeled in the shared ViewModel. |
| `TaskNodePermissions` | `canEdit`, `canAppendGuidance`, `canResolveConfirmation`, `canPublish`, `canCancel`, `canRetry` | Good direction, but missing `readonlyReason` and action-level availability. |
| `AuditLinkView` | `label`, `href`, `severity` | Link-only; no canonical audit summary, verdict, evidence completeness, or record count. |

### 2.3 Current backend contract and projection sources

| Source | Current values | Issue |
|---|---|---|
| `src/taskweavn/task/authoring.py` `RawTaskStatus` | `created`, `assessing`, `awaiting_user`, `ready_to_plan`, `converted`, `rejected`, `cancelled` | Good source for planning, but not exposed as planning state in current transport snapshot. |
| `src/taskweavn/task/models.py` `DraftTaskStatus` | `draft`, `accepted`, `published`, `cancelled` | Good source for readiness. |
| `src/taskweavn/task/models.py` `TaskStatus` | `pending`, `running`, `done`, `failed` | Good source for execution. |
| `src/taskweavn/task/views.py` `TaskViewStatus` | `draft`, `pending`, `running`, `done`, `failed`, `cancelled` | Server-core projection still compresses readiness and execution into one task card status. |
| `src/taskweavn/task/views.py` `ConfirmationActionView.status` | `pending`, `resolved`, `expired` | Good source for confirmation. |
| `src/taskweavn/task/views.py` `TaskCardPermissions` | permission booleans plus `readonly_reason` | Backend has useful disabled-state reason, but current transport mapping drops it. |
| `src/taskweavn/task/views.py` `primary_actions` | action list with `disabled` and `reason` | Backend has action availability, but current transport mapping drops it. |
| `src/taskweavn/audit/agent.py` `AuditVerdict` | `pass`, `fail`, `inconclusive` | Needs product-level mapping to `passed`, `warning`, `failed`, `inconclusive`, `not_available`. |

## 3. Canonical Status Dimensions

Canonical fields should be backend/domain facts or backend-projected facts.
UI labels, icons, tones, badges, and screen names are presentation mappings.

### 3.1 Planning State

Planning state is session-level authoring state before and around Draft
TaskTree creation. It is not task execution state.

Target type:

```ts
type PlanningState =
  | "empty"
  | "capturing_input"
  | "assessing"
  | "awaiting_user"
  | "ready_to_plan"
  | "draft_ready"
  | "published"
  | "rejected"
  | "cancelled"
  | "unknown";
```

| Value | Semantics | Backend owner field | Frontend owner field | UI representation | Classification | Unknown/error handling |
|---|---|---|---|---|---|---|
| `empty` | Session has no meaningful goal or RawTask yet. | Absence of RawTask and DraftTaskTree. | `MainPageSnapshot.planning.state` | `New`, goal input enabled. | Stable until user input. | If snapshot lacks all authoring fields, default to `empty` only when session is otherwise valid. |
| `capturing_input` | User input was accepted and is being recorded/classified. | RawTask creation command accepted, RawTask may be `created`. | `planning.state` plus pending command overlay. | `Understanding`. | Transient. | If command accepted but snapshot has no RawTask after refresh, keep local pending state then resync or show command error. |
| `assessing` | System is checking feasibility, missing inputs, or safety. | `RawTask.status = assessing`. | `planning.state`. | `Understanding`, progress hint. | Transient. | Unexpected timeout becomes load/error or stale/resync, not `failed` execution. |
| `awaiting_user` | Planning needs clarification or permission before tree generation. | `RawTask.status = awaiting_user`, unanswered asks. | `planning.state`, `planning.asks[]`. | `Needs input`, clarification input mode. | Blocking, not terminal. | If asks are missing, show recoverable contract error and request resync. |
| `ready_to_plan` | RawTask can produce a Draft TaskTree. | `RawTask.status = ready_to_plan`. | `planning.state`. | `Ready to plan`, generate action. | Stable until command. | If tree exists too, map to `draft_ready` instead. |
| `draft_ready` | Draft TaskTree exists and can be reviewed. | DraftTaskTree exists and is not published/cancelled. | `planning.state`. | `Draft ready`, review/publish affordance. | Stable. | If tree has inconsistent nodes, show validation warnings and set affected readiness to `unknown`. |
| `published` | Draft lineage crossed into published task execution. | DraftTaskTree publication mapping or all relevant nodes published. | `planning.state`. | `Published`, execution UI visible. | Stable. | Do not infer individual node execution from this. |
| `rejected` | Request cannot be planned safely or usefully. | `RawTask.status = rejected`. | `planning.state`. | `Cannot proceed`, show reason and alternatives. | Terminal for current RawTask. | Do not map to task execution failure. |
| `cancelled` | Planning was intentionally stopped. | `RawTask.status = cancelled` or DraftTaskTree cancelled. | `planning.state`. | `Cancelled`, readonly/restart affordance. | Terminal for current planning attempt. | Preserve session context. |
| `unknown` | UI cannot safely determine planning state. | Missing/inconsistent authoring facts or unsupported status. | `planning.state`. | `Needs refresh`, readonly where needed. | Error/recoverable. | Enter stale/resync if visible state is affected. |

### 3.2 Task Readiness

Task readiness describes whether a task node is still an editable draft,
publishable, published, or cancelled. It does not describe execution.

Target node type:

```ts
type TaskNodeReadiness =
  | "draft"
  | "accepted"
  | "published"
  | "cancelled"
  | "unknown";
```

Target tree rollup type:

```ts
type TaskTreeReadiness =
  | "empty"
  | "draft"
  | "accepted"
  | "published"
  | "mixed"
  | "cancelled"
  | "unknown";
```

| Value | Semantics | Backend owner field | Frontend owner field | UI representation | Classification | Unknown/error handling |
|---|---|---|---|---|---|---|
| `draft` | Node is editable before publish. | `DraftTaskNode.status = draft`. | `TaskNodeCardView.readiness`. | Draft/editable if permissions allow. | Stable. | If `taskRef.kind` is `published`, do not show `draft`; mark `unknown`. |
| `accepted` | Node passed authoring validation and is publishable. | `DraftTaskNode.status = accepted`. | `readiness`. | Ready/publishable. | Stable. | If validation summary contradicts this, show validation warning and request resync. |
| `published` | Node has a published task identity. | `DraftTaskNode.status = published` plus mapping to `TaskDomain`. | `readiness`. | Published identity; execution status becomes primary. | Stable. | If mapping is missing, use `unknown` and disable risky actions. |
| `cancelled` | Node is intentionally removed from the publish path. | `DraftTaskNode.status = cancelled` or cancellation mapping. | `readiness`. | Cancelled/read-only. | Terminal for current node. | Keep visible for audit/history if relevant. |
| `unknown` | UI cannot determine draft/published relationship. | Missing mapping, unsupported status, inconsistent refs. | `readiness`. | Unknown, refresh/resync. | Error/recoverable. | Disable edit/publish/cancel until resynced. |

Tree readiness is a rollup and should not overwrite node readiness. For example,
a tree can be `mixed` while individual nodes remain `draft`, `accepted`, or
`published`.

### 3.3 Execution Status

Execution status is the backend TaskBus state for published tasks. Draft tasks
use `not_started`.

Target type:

```ts
type ExecutionStatus =
  | "not_started"
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "cancelled"
  | "unknown";
```

| Value | Semantics | Backend owner field | Frontend owner field | UI representation | Classification | Unknown/error handling |
|---|---|---|---|---|---|---|
| `not_started` | No published execution exists for this node. | No `TaskDomain` for the node. | `TaskNodeCardView.execution`. | Draft/not started. | Stable until publish. | Only valid with readiness `draft`, `accepted`, `cancelled`, or `unknown`. |
| `pending` | Published task is queued or eligible to run. | `TaskDomain.status = pending`. | `execution`. | Label `Queued`. | Transient. | `queued` must remain a label, not a canonical value. |
| `running` | Agent/tool execution is active. | `TaskDomain.status = running`. | `execution`. | Running/progress. | Transient. | If events stop, enter stale/resync rather than guessing completion. |
| `done` | Execution completed successfully. | `TaskDomain.status = done`. | `execution`. | Done/result available if present. | Terminal for current run. | Result may still be loading separately. |
| `failed` | Execution failed. | `TaskDomain.status = failed`. | `execution`. | Failed/retry if permitted. | Terminal for current run. | Failure reason belongs to result/detail, not the status enum. |
| `cancelled` | Execution was intentionally cancelled or skipped. | Cancellation command/result, or projected cancellation fact. | `execution`. | Cancelled/read-only or retry if permitted. | Terminal for current run. | Backend currently lacks canonical `TaskDomain.status = cancelled`; projection must own the mapping until domain supports it. |
| `unknown` | UI cannot determine execution state. | Missing published task, unsupported status, inconsistent mapping. | `execution`. | Unknown/refresh. | Error/recoverable. | Disable retry/cancel/confirmation actions until resync if risk is visible. |

Execution rollup should be represented separately:

```ts
type ExecutionRollupView = {
  total: number;
  notStarted: number;
  pending: number;
  running: number;
  done: number;
  failed: number;
  cancelled: number;
  unknown: number;
  blockedByConfirmation: number;
};
```

### 3.4 Confirmation Status

Confirmation status is independent of execution. A running or pending task can
also have a pending confirmation.

Backend confirmation type:

```ts
type ConfirmationStatus =
  | "pending"
  | "resolved"
  | "expired";
```

Frontend local overlay:

```ts
type LocalConfirmationStatus =
  | "idle"
  | "resolving"
  | "resolve_failed";
```

| Value | Semantics | Backend owner field | Frontend owner field | UI representation | Classification | Unknown/error handling |
|---|---|---|---|---|---|---|
| `pending` | User action is required. | `ConfirmationActionView.status = pending`. | `ConfirmationActionView.status`. | Confirmation card with actions. | Blocking, not terminal. | Must not overwrite execution with `waiting_user`. |
| `resolved` | User selected an option and backend recorded it. | `ConfirmationActionView.status = resolved`, `resolved_at`. | `ConfirmationActionView.status`. | Resolved/history. | Terminal for this confirmation. | Command accepted alone is not enough to mark resolved. |
| `expired` | Confirmation is no longer actionable. | `ConfirmationActionView.status = expired`. | `ConfirmationActionView.status`. | Expired/read-only. | Terminal. | If user tries to respond, show stale/resync or expired message. |
| `idle` | No local submit is in flight. | Frontend-only. | Reducer/local command state. | Normal buttons. | Local stable. | Does not alter backend status. |
| `resolving` | User submitted a response and command is in flight. | Frontend-only until query/event confirms. | Reducer/local command state keyed by confirmation id. | Disable duplicate submit/spinner. | Transient. | Timeout or command failure moves to `resolve_failed`; event/query can move backend status to `resolved` or `expired`. |
| `resolve_failed` | Respond command failed before backend resolution. | Frontend-only command failure. | Reducer/local command state. | Inline error, actions re-enabled if backend still pending. | Recoverable. | Resync if error is `version_conflict`, `resync_required`, `not_found`, or stale event. |

Planning asks should use a sibling model:

```ts
type PlanningAskStatus = "pending" | "answered" | "expired";
```

Planning ask status can derive a `Needs input` screen state, but it must not
reuse task execution or confirmation status.

### 3.5 Permission And Action Availability

Permissions are facts about what the user may do. They are not status labels.
Action availability is the user-facing projection of permissions plus current
state constraints.

Target type:

```ts
type ActionAvailability =
  | "enabled"
  | "disabled_permission"
  | "disabled_state"
  | "disabled_stale"
  | "pending_command"
  | "hidden"
  | "unknown";
```

| Value | Semantics | Backend owner field | Frontend owner field | UI representation | Classification | Unknown/error handling |
|---|---|---|---|---|---|---|
| `enabled` | User can execute the action now. | `TaskCardPermissions.* = true`, `primary_actions[].disabled = false`. | `ActionAvailabilityView.availability`. | Enabled control. | Stable for snapshot. | Command may still be rejected by backend; show command error. |
| `disabled_permission` | User lacks permission or policy approval. | `TaskCardPermissions.* = false`, `readonly_reason`, command `permission_denied`. | `availability`, `disabledReason`. | Disabled control with reason. | Stable until permissions change. | Do not hide expected control if user needs explanation. |
| `disabled_state` | Current state does not support the action. | Projection action disabled reason or state/action rule. | `availability`, `disabledReason`. | Disabled or absent depending affordance. | Stable for snapshot. | Example: retry hidden unless execution `failed` and `canRetry`. |
| `disabled_stale` | Snapshot is stale or resyncing. | Event/reducer state, command `resync_required`, cursor expiration. | Reducer/runtime state. | Read-only overlay or disabled high-risk controls. | Transient. | Retry after resync. |
| `pending_command` | Command for this action is accepted/submitting. | Command response and local command state. | Reducer/local command state. | Spinner/disabled duplicate submit. | Transient. | Final status must come from event/query. |
| `hidden` | Action is not relevant in this context. | Projection action list or product rule. | `availableActions[]`. | No visible control. | Stable for snapshot. | Use disabled instead of hidden when absence would confuse user. |
| `unknown` | UI cannot determine availability safely. | Missing permission/action fields. | `availability`. | Disabled with refresh hint. | Error/recoverable. | Disable mutation actions and request resync. |

Target owner fields:

```ts
type TaskNodePermissions = {
  canEdit: boolean;
  canAppendGuidance: boolean;
  canResolveConfirmation: boolean;
  canPublish: boolean;
  canCancel: boolean;
  canRetry: boolean;
  readonlyReason?: string | null;
};

type ActionAvailabilityView = {
  action:
    | "edit"
    | "append_guidance"
    | "publish"
    | "cancel"
    | "retry"
    | "resolve_confirmation"
    | "open_audit";
  availability: ActionAvailability;
  reason?: string | null;
};
```

### 3.6 Audit Verdict

Audit verdict is a Trust Plane result. It is not execution status and it does
not mutate TaskBus state.

Target verdict type:

```ts
type AuditVerdict =
  | "not_available"
  | "passed"
  | "warning"
  | "failed"
  | "inconclusive"
  | "unknown";
```

Audit Page also needs evidence completeness, separate from verdict:

```ts
type AuditEvidenceStatus =
  | "not_started"
  | "running"
  | "partial"
  | "complete"
  | "failed"
  | "hidden"
  | "unknown";
```

| Value | Semantics | Backend owner field | Frontend owner field | UI representation | Classification | Unknown/error handling |
|---|---|---|---|---|---|---|
| `not_available` | No audit summary exists yet. | No audit observation/summary for scope. | `AuditSummaryView.verdict`, `TaskNodeCardView.auditVerdict`. | Audit pending/unavailable. | Stable until evidence arrives. | Must not imply pass. |
| `passed` | Evidence supports the result/action. | `AuditAgent.verdict = pass` with no warning findings. | `auditVerdict`. | Audit passed. | Stable for snapshot. | New evidence may revise verdict; show generated time. |
| `warning` | Evidence exists but has non-blocking risk, gaps, partial validation, or policy warnings. | Risk records, partial evidence, non-blocking concerns, or product-level audit summary. | `auditVerdict`. | Warning/needs review. | Stable for snapshot. | Backend AuditAgent does not emit this directly yet; summary mapper owns derivation. |
| `failed` | Evidence shows failure, violation, or untrusted result. | `AuditAgent.verdict = fail`, failed audit record, blocking risk. | `auditVerdict`. | Audit failed. | Stable for snapshot. | Provide evidence details and return path. |
| `inconclusive` | Audit could not establish confidence. | `AuditAgent.verdict = inconclusive`, missing evidence, failed parser. | `auditVerdict`. | Inconclusive. | Stable for snapshot. | Explain missing evidence. |
| `unknown` | UI cannot determine audit verdict safely. | Unsupported value, inconsistent summary. | `auditVerdict`. | Unknown/refresh. | Error/recoverable. | Do not treat as passed; query Audit Page snapshot. |

`AuditEvidenceStatus` values should drive Audit Page loading, partial, failed,
hidden, and complete states. They should not be merged into `AuditVerdict`.

## 4. Mapping Current Flat Statuses To Canonical Model

### 4.1 Current frontend/backend `SessionStatus`

| Current flat status | Proposed canonical mapping | Notes |
|---|---|---|
| `new` | `planning = empty`; no implied task readiness/execution. | If messages exist, current backend may choose `understanding`; target should use RawTask/planning facts. |
| `understanding` | `planning = capturing_input` or `assessing`. | Current status loses distinction between command accepted, RawTask created, and feasibility assessment. |
| `draft_ready` | `planning = draft_ready`; tree readiness derived per node. | Do not imply execution. |
| `running` | Usually `planning = published`; at least one node execution `pending` or `running`, or rollup active. | Current value may also represent tree `published` with no active work. |
| `waiting_user` | Either `planning = awaiting_user` or `confirmation.status = pending`. | This is the most important split. It currently conflates planning ask and task confirmation. |
| `completed` | `planning = published`; execution rollup all terminal success, or session lifecycle finished. | Result/file/audit may still be loading. |
| `failed` | `planning = rejected` or execution rollup failed, depending source. | Current session status cannot tell planning rejection from task execution failure. |

### 4.2 Current `TaskTreeStatus`

| Current flat status | Proposed canonical mapping | Notes |
|---|---|---|
| `draft` | `tree.readiness = draft` or `mixed`; execution rollup all `not_started`. | Current tree status is good enough only before publication. |
| `published` | `tree.readiness = published` or `mixed`; execution rollup may include `pending`, `done`, or `not_started`. | Needs execution rollup to be useful. |
| `running` | `tree.readiness = published`; execution rollup includes `running` or `blockedByConfirmation > 0`. | Confirmation should not be represented as tree running. |
| `completed` | `tree.readiness = published`; execution rollup all `done` or terminal. | Audit/result completeness separate. |
| `failed` | `tree.readiness = published` or `mixed`; execution rollup includes `failed`. | Retry availability comes from permissions/actions. |

### 4.3 Current `TaskNodeStatus`

| Current flat status | Proposed canonical mapping | Notes |
|---|---|---|
| `draft` | `readiness = draft`; `execution = not_started`; `confirmation = null`. | Editable only if permissions allow. |
| `queued` | `readiness = published`; `execution = pending`; `confirmation = null` unless separate confirmation exists. | `queued` becomes UI label for `pending`. |
| `running` | `readiness = published`; `execution = running`; `confirmation = null` unless separate confirmation exists. | Do not use this for planning activity. |
| `waiting_user` | `confirmation = pending` or planning ask pending; execution remains the backend value if known, else `unknown`. | Current mapping discards whether task was pending or running when confirmation appeared. |
| `done` | `readiness = published`; `execution = done`; confirmation separate. | Result/file/audit may still be unavailable. |
| `failed` | `readiness = published`; `execution = failed`. | Retry/action availability separate. |
| `cancelled` | `readiness = cancelled` for draft cancellation, or `execution = cancelled` for published cancellation. | Current value cannot distinguish draft cancellation from execution cancellation. |

### 4.4 Backend authoring and task statuses

| Backend source | Current value | Canonical mapping |
|---|---|---|
| no RawTask | none | `planning = empty`. |
| `RawTask.status` | `created` | `planning = capturing_input`. |
| `RawTask.status` | `assessing` | `planning = assessing`. |
| `RawTask.status` | `awaiting_user` | `planning = awaiting_user`; asks become `PlanningAskView[]`. |
| `RawTask.status` | `ready_to_plan` | `planning = ready_to_plan`. |
| `RawTask.status` | `converted` | `planning = draft_ready` or `published`, disambiguated by DraftTaskTree/publication mapping. |
| `RawTask.status` | `rejected` | `planning = rejected`. |
| `RawTask.status` | `cancelled` | `planning = cancelled`. |
| `DraftTaskNode.status` | `draft` | `readiness = draft`. |
| `DraftTaskNode.status` | `accepted` | `readiness = accepted`. |
| `DraftTaskNode.status` | `published` | `readiness = published`. |
| `DraftTaskNode.status` | `cancelled` | `readiness = cancelled`. |
| `TaskDomain.status` | `pending` | `execution = pending`, label `Queued`. |
| `TaskDomain.status` | `running` | `execution = running`. |
| `TaskDomain.status` | `done` | `execution = done`. |
| `TaskDomain.status` | `failed` | `execution = failed`. |
| cancellation projection | not currently a domain value | `execution = cancelled` when cancellation applies to published execution. |
| `AuditAgent.verdict` | `pass` | `auditVerdict = passed`, unless warning findings exist. |
| `AuditAgent.verdict` | `fail` | `auditVerdict = failed`. |
| `AuditAgent.verdict` | `inconclusive` | `auditVerdict = inconclusive`. |

## 5. Current Collapse Points

These locations should be treated as migration targets. They should not be
changed by this documentation task.

| Location | Collapse |
|---|---|
| `src/taskweavn/server/ui_contract/view_models.py` `SessionStatus` | One enum mixes planning, confirmation, execution, and session lifecycle. |
| `src/taskweavn/server/ui_contract/view_models.py` `TaskTreeStatus` | One enum mixes tree readiness and execution rollup. |
| `src/taskweavn/server/ui_contract/view_models.py` `TaskNodeStatus` | One enum mixes readiness, execution, confirmation, cancellation, and UI label `queued`. |
| `src/taskweavn/server/ui_contract/mapping.py` `map_task_node_status` | Pending confirmation overwrites task status with `waiting_user`; backend `pending` becomes canonical-looking `queued`. |
| `src/taskweavn/server/ui_contract/mapping.py` `derive_task_tree_status` | Rollup uses flattened node statuses; `waiting_user` makes tree `running`. |
| `src/taskweavn/server/ui_contract/gateways.py` `_derive_session_status` | Pending confirmations take priority over all other facts and become session `waiting_user`; `messages` can imply `understanding`. |
| `src/taskweavn/server/ui_contract/mapping.py` `map_task_permissions` | Drops `readonly_reason`, so frontend cannot explain disabled states. |
| `src/taskweavn/server/ui_contract/mapping.py` `map_task_node_card` | Drops `primary_actions`, `confirmation` summary, `progress`, `risk_level`, and separate execution/readiness dimensions. |
| `frontend/src/shared/api/types.ts` | Mirrors flattened transport statuses and lacks canonical separated fields. |
| `frontend/src/pages/main-page/MainPage.tsx` | `canPublishTaskTree = snapshot.taskTree?.status === "draft"` uses tree status instead of permission/action availability. |
| `frontend/src/pages/main-page/TaskTreePanel.tsx` | Task card labels and tones are derived from one flat `status`. |
| `frontend/src/pages/main-page/runtime/metadata.ts` | Selection/detail priority and status presentation rely on flat statuses. |
| `frontend/src/pages/main-page/fixtures.ts` | Mock scenarios encode S1-S9 with flat status values, not canonical state manifests. |
| `frontend/src/entities/audit/model.ts` | Audit model is link-only and cannot express verdict, completeness, records, or selected detail. |
| `src/taskweavn/audit/agent.py` | Audit verdict has backend values but no product-level warning/not-available mapping. |

## 6. Target ViewModel Shape

The exact transport schema can be finalized in API contract work, but the target
shape should preserve these fields.

```ts
type MainPageSnapshot = {
  schemaVersion: "plato.main.v1";
  project: ProjectSummary;
  workflows: WorkflowSummary[];
  workflow: WorkflowSummary;
  sessions: SessionSummary[];
  session: SessionSummary;
  planning: PlanningView;
  taskTree: TaskTreeView | null;
  messages: SessionMessageView[];
  pendingConfirmations: ConfirmationActionView[];
  result: ResultCardView | null;
  fileChangeSummary: FileChangeSummaryView | null;
  auditSummary: AuditSummaryView | null;
  auditLinks: AuditLinkView[];
  permissions: SessionPermissions;
  cursor: EventCursor | null;
  generatedAt: string;
};

type TaskTreeView = {
  id: string;
  sessionId: string;
  title: string;
  readiness: TaskTreeReadiness;
  executionRollup: ExecutionRollupView;
  nodes: TaskNodeCardView[];
  version: number;
};

type TaskNodeCardView = {
  id: string;
  taskRef?: TaskRef | null;
  parentId: string | null;
  title: string;
  summary: string;
  readiness: TaskNodeReadiness;
  execution: ExecutionStatus;
  confirmation: ConfirmationStatus | null;
  auditVerdict: AuditVerdict;
  badges: TaskNodeBadges;
  permissions: TaskNodePermissions;
  actions: ActionAvailabilityView[];
  readonlyReason?: string | null;
  version: number;
};
```

Compatibility fields may remain during migration:

```ts
type LegacyStatusCompatibility = {
  legacySessionStatus?: SessionStatus;
  legacyTaskTreeStatus?: TaskTreeStatus;
  legacyTaskNodeStatus?: TaskNodeStatus;
};
```

Compatibility fields must be marked deprecated and must not be the owner of new
UI behavior.

## 7. Migration Plan

### Phase 0 - Docs only

Goal: align product, UX, frontend, and backend vocabulary before code changes.

Deliverables:

- Create this canonical status model document.
- Keep `docs/ux/screen-state-spec.md`, `docs/frontend/ui-viewmodel-contract.md`, and `docs/frontend/api-ui-mapping.md` aligned with this document.
- Identify current collapse points and blockers.

Acceptance criteria:

- The team can point to one canonical status document.
- No UI/runtime behavior changes.
- No MainPage refactor.

### Phase 1 - Backend contract

Goal: extend transport models without removing legacy fields.

Checkpoint:

- Audit Page additive backend contract models now exist for
  `AuditPageSnapshot`, audit records, record detail, evidence, scope, entry
  context, return target, permissions, and page states.
- Audit Page record/evidence/stale event builders now exist for
  `audit.records_changed`, `audit.record_updated`, `audit.evidence_hidden`, and
  `audit.snapshot_stale`.
- Main Page canonical status fields such as `PlanningView`, separated task
  readiness/execution, `AuditSummaryView`, and action availability still need a
  later additive contract migration.

Deliverables:

- Add backend UI contract types for `PlanningView`, `TaskNodeReadiness`,
  `TaskTreeReadiness`, `ExecutionStatus`, `ExecutionRollupView`,
  `AuditSummaryView`, and `ActionAvailabilityView`.
- Add `readonly_reason` to transport `TaskNodePermissions`.
- Preserve legacy `status` fields temporarily.
- Add mapper functions from backend sources to separated dimensions.
- Add backend contract tests for mapping edge cases.

Acceptance criteria:

- Existing frontend remains compatible.
- New fields are populated in snapshots.
- `queued` is only emitted as a presentation label or legacy compatibility value.

### Phase 2 - Frontend types

Goal: let frontend consume separated fields without changing visible UI yet.

Deliverables:

- Add frontend API types matching Phase 1.
- Add adapter selectors that prefer new fields but can fall back to legacy status.
- Add central status presentation mapping.
- Add local `LocalConfirmationStatus` and action availability types.

Acceptance criteria:

- Type tests or unit tests cover new mapping.
- No visual redesign or MainPage refactor required.

### Phase 3 - Mock fixtures

Goal: make scenarios prove the new model before component migration.

Deliverables:

- Add mock scenario manifest with canonical dimensions.
- Cover happy path, planning asks, pending/running/done/failed/cancelled,
  confirmation pending/resolving/resolved/expired/failed, permission denied,
  audit empty/partial/inconclusive/failed, and stale/resync.
- Keep existing S1-S9 fixtures as legacy visual scenarios until components migrate.

Acceptance criteria:

- Each mock declares canonical states and expected enabled/disabled actions.
- Audit Page mock data exists before Audit Page UI implementation.

### Phase 4 - Components

Goal: migrate UI components incrementally to canonical fields.

Deliverables:

- Update `TaskNodeCard`/`TaskTreePanel` to use readiness, execution,
  confirmation, audit verdict, and permissions separately.
- Update `ContextInput` to use explicit input mode and disabled reason.
- Update confirmation UI to use backend status plus local overlay.
- Add Audit Page components only after `AuditPageSnapshot` is served by a
  mock-backed query gateway/route and frontend types match the backend
  contract.

Acceptance criteria:

- No component infers permission from status alone.
- No component treats `waiting_user` as execution.
- Audit components remain read-only.

### Phase 5 - Tests

Goal: lock migration behavior before removing legacy fields.

Deliverables:

- Backend contract tests for status mapping.
- Frontend selector tests for legacy fallback and new fields.
- Confirmation lifecycle tests.
- Permission/action availability tests.
- Audit verdict and evidence completeness tests.
- Resync/stale snapshot tests.

Acceptance criteria:

- Tests prove command accepted does not mutate final canonical status.
- Tests prove pending confirmation does not overwrite execution.
- Tests prove `pending` maps to label `Queued`, not canonical `queued`.

### Phase 6 - Remove legacy status ownership

Goal: stop using flattened statuses as behavior owners.

Deliverables:

- Deprecate or remove behavioral reads of `SessionStatus`, `TaskTreeStatus`, and
  `TaskNodeStatus`.
- Keep optional presentation rollups only if still useful.
- Remove legacy fallback after frontend and backend are both migrated.

Acceptance criteria:

- No production component or runtime rule depends on legacy flat status for
  mutation availability, Audit Page rendering, confirmation lifecycle, or task
  execution state.

## 8. Blockers And Open Decisions

| Blocker | Impact | Proposed next decision |
|---|---|---|
| Backend transport lacks `PlanningView`. | Main Page cannot reliably distinguish understanding, awaiting user, ready to plan, and draft ready. | Add backend contract fields in Phase 1. |
| Backend transport lacks separated task readiness/execution. | Task cards cannot represent pending confirmation without losing execution state. | Add `readiness`, `execution`, and `confirmation` fields. |
| Backend transport drops `readonly_reason` and `primary_actions`. | Frontend cannot explain disabled controls or action availability. | Preserve these fields in transport contract. |
| Audit Page route/gateway/data aggregation is missing. | `AuditPageSnapshot` exists as an additive backend contract model, but no API route or query gateway serves it yet. | Add mock-backed audit query gateway and HTTP route shell before frontend UI. |
| Audit `warning` derivation is product-level, not emitted by current AuditAgent. | UI cannot show warning verdict consistently. | Define summary mapper rules for risk records, partial evidence, and validation gaps. |
| Published cancellation is not a `TaskDomain.status` value. | `execution = cancelled` needs a projection rule. | Decide whether to add domain cancellation or keep projection-only cancellation. |
| Current mocks are state-frame driven, not canonical-state driven. | Tests can pass while model is still ambiguous. | Add scenario manifest in Phase 3. |
| Event payloads do not yet carry full canonical fragments. | Frontend reducer must refetch/resync instead of patching confidently. | Keep refetch-first, then add canonical payloads later. |

## 9. Implementation Guardrails

- Do not implement Audit Page UI until `AuditPageSnapshot` is served by a query
  gateway/route and audit verdict mapping has mock or real data behind it.
- Do not refactor MainPage as part of the first backend contract change.
- Do not remove legacy flat fields until both backend and frontend have tests for
  separated fields.
- Do not let `queued` become canonical. It is a label for execution `pending`.
- Do not let `waiting_user` become canonical. It is a derived display state from
  either planning ask or pending confirmation.
- Do not let command response `accepted` mutate final status. Events or queries
  own final canonical state.
- Do not infer permissions in visual components.
- Do not treat missing audit evidence as passed.

## 10. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Extend the backend UI contract with additive canonical status fields only.

Context:
docs/product/canonical-status-model.md defines the canonical dimensions. The
current transport ViewModel still exposes legacy flat statuses. We need additive
backend contract fields and mapper tests before frontend migration.

Do not remove legacy status fields.
Do not refactor MainPage.
Do not implement Audit Page UI.
Do not change runtime behavior except populating new snapshot fields.

Required work:
1. Read docs/product/canonical-status-model.md.
2. Add backend UI contract models for PlanningView, TaskNodeReadiness,
   TaskTreeReadiness, ExecutionStatus, ExecutionRollupView,
   ActionAvailabilityView, and AuditSummaryView placeholder.
3. Populate new fields in MainPageSnapshot mapping while preserving legacy
   fields.
4. Preserve readonly_reason and primary action availability in transport.
5. Add focused backend contract tests proving:
   - TaskDomain pending -> execution pending and label remains presentation.
   - Pending confirmation does not overwrite execution.
   - RawTask awaiting_user maps to planning awaiting_user.
   - DraftTaskNode accepted maps to readiness accepted.
   - Missing/inconsistent refs map to unknown or trigger safe fallback.

Output:
- files changed
- contract fields added
- mapping behavior
- tests run
- remaining frontend migration tasks
```
