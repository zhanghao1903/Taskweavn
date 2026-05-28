# Backend To UI Mapping

> Status: draft
> Last Updated: 2026-05-24
> Scope: Mapping backend/domain facts to Plato frontend ViewModels.
> Related: `docs/frontend/ui-viewmodel-contract.md`, `docs/frontend/event-reducer-contract.md`, `docs/engineering/audit-page-contract.md`, `docs/ux/screen-state-spec.md`, `docs/architecture/task-domain-ui-model-separation.md`, `docs/architecture/ui-backend-communication.md`

## 1. Purpose

This document defines how backend/domain state maps into frontend UI ViewModels.

The mapping layer should live in the UI API gateway or frontend API adapter. Components should consume the mapped ViewModel and should not know backend storage details.

## 2. Mapping Principles

1. Prefer backend/domain state as canonical.
2. Keep UI labels separate from canonical state.
3. Keep planning, readiness, execution, confirmation, and audit verdict separate.
4. Do not infer permissions in visual components.
5. Do not expose raw logs, raw event payloads, SQLite ids, provider payloads, or stack traces in primary UI.
6. When mapping is ambiguous, return `unknown`, `not_available`, or request resync rather than inventing certainty.

## 3. Status Mapping

### 3.1 RawTask To Planning State

| Backend RawTask Status | UI Planning State | Notes |
|---|---|---|
| no RawTask | `empty` | No meaningful session goal yet. |
| `created` | `capturing_input` | Input has been captured. |
| `assessing` | `assessing` | Feasibility or intent analysis running. |
| `awaiting_user` | `awaiting_user` | Clarification or permission needed. |
| `ready_to_plan` | `ready_to_plan` | Can generate Draft TaskTree. |
| `converted` | `draft_ready` or `published` | Use DraftTaskTree presence and publication mapping to disambiguate. |
| `rejected` | `rejected` | Unsupported or unsafe. |
| `cancelled` | `cancelled` | User/system stopped planning. |

### 3.2 DraftTaskNode To Readiness

| Backend DraftTaskNode Status | UI Readiness | Notes |
|---|---|---|
| `draft` | `draft` | Editable if permissions allow. |
| `accepted` | `accepted` | Publishable. |
| `published` | `published` | Must have DraftToPublishedMapping where possible. |
| `cancelled` | `cancelled` | Read-only. |
| missing/unexpected | `unknown` | Trigger resync if visible. |

### 3.3 TaskDomain To Execution Status

| Backend TaskDomain Status | UI Execution Status | UI Label |
|---|---|---|
| no published task | `not_started` | Draft |
| `pending` | `pending` | Queued |
| `running` | `running` | Running |
| `done` | `done` | Done |
| `failed` | `failed` | Failed |
| cancellation fact | `cancelled` | Cancelled |
| unexpected value | `unknown` | Unknown |

The frontend should migrate away from canonical `queued`. `queued` is a label for backend `pending`.

### 3.4 Confirmation Mapping

| Backend Confirmation Status | UI Confirmation Status | Local Overlay Allowed |
|---|---|---|
| `pending` | `pending` | `idle`, `resolving`, `resolve_failed` |
| `resolved` | `resolved` | none |
| `expired` | `expired` | none |

If a task has pending confirmation, Main Page may derive a display state like `waiting_user`, but it must not overwrite execution status.

### 3.5 Audit Verdict Mapping

| Backend Source | UI Audit Verdict | Rule |
|---|---|---|
| no audit summary | `not_available` | Show audit pending/unavailable. |
| `AuditAgent.verdict = pass` | `passed` | No blocking risk findings. |
| `AuditAgent.verdict = fail` | `failed` | Evidence indicates failure or violation. |
| `AuditAgent.verdict = inconclusive` | `inconclusive` | Missing or insufficient evidence. |
| risk finding with non-blocking concern | `warning` | Task may be usable, but evidence has gaps. |
| partial audit still running | `inconclusive` or `not_available` with completeness `running` | Do not imply pass. |

`warning` is a product-level audit verdict. It may be derived from risk records, validation gaps, partial evidence, or policy warnings even if the current backend audit agent does not emit it directly.

## 4. Backend Projection To Frontend ViewModel

### 4.1 Task Card Mapping

| Backend Projection Field | Frontend Field | Notes |
|---|---|---|
| `task_ref` | `taskRef` | Preserve `draft` or `published`. |
| `parent_ref` | `parentId` via projection mapping | UI needs stable `TaskNodeId`. |
| `title` | `title` | User-facing. |
| `intent_preview` | `summary` | Keep concise. |
| `status = draft` | `readiness = draft`, `execution = not_started` | Draft status is readiness. |
| `status = pending` | `readiness = published`, `execution = pending` | Label as queued. |
| `status = running` | `readiness = published`, `execution = running` | Execution active. |
| `status = done` | `readiness = published`, `execution = done` | Completed. |
| `status = failed` | `readiness = published`, `execution = failed` | Retry may be available. |
| `status = cancelled` | `readiness = cancelled`, `execution = cancelled` | Read-only. |
| `badges.pending_confirmation_count` | `badges.pendingConfirmationCount` | Also derives confirmation display. |
| `permissions.*` | `permissions.*` | Do not re-infer in component. |
| `permissions.readonly_reason` | `readonlyReason` | Show when disabled control needs explanation. |
| `confirmation` | `confirmation` | Map separately from execution. |

### 4.2 Message Mapping

| Backend Field | Frontend Field | Notes |
|---|---|---|
| `message_id` | `id` | Stable identity. |
| `session_id` | `sessionId` | Session boundary. |
| `task_ref` | `taskRef` | Optional. |
| projected task node id | `taskNodeId` | Derived by mapping `TaskRef` to current node. |
| `message_type = user` | `kind = response` or `informational` | Depends on context. |
| `message_type = agent` | `kind = informational` | User-readable summary. |
| `message_type = system` | `kind = informational` or `error` | Avoid internal copy. |
| `message_type = confirmation` | `kind = actionable` | Link confirmation id. |
| `message_type = result` | `kind = informational` | Result card is separate. |
| `content_summary` | `title/body` | Gateway may split title/body. |

### 4.3 Confirmation Mapping

| Backend Field | Frontend Field |
|---|---|
| `confirmation_id` | `id` |
| `task_ref` | `taskRef` |
| projected task node id | `taskNodeId` |
| `prompt` | `title` and/or `body` |
| `options` | `options` |
| `default_option_id` | `defaultOptionValue` after resolving option value |
| `risk_summary` | `riskLabel` |
| `status` | `status` |

### 4.4 File And Result Mapping

| Backend Field | Frontend Field | Notes |
|---|---|---|
| `TaskFileChangeSummary.path` | `changedFiles[].path` | Do not expose absolute private path by default if unsafe. |
| `change_type` | `changeType` | Map unknown to visible fallback only in Audit/Diagnostics. |
| `from_subtree` | `recursive` or item ownership | Parent summaries are backend-projected. |
| `TaskSummaryView.summary` | `ResultCardView.summary` | User-facing. |
| `failure_reason` | failure section or error state | Do not hide task failure. |
| `artifact_refs` | result sections/links | Safe links only. |

## 5. API Error To UI Mapping

| API Error Code | UI Behavior | Resync |
|---|---|---|
| `bad_request` | Inline validation or command error. | No |
| `not_found` | Context lost; show recoverable missing state. | Maybe |
| `version_conflict` | Show conflict message and resync. | Yes |
| `command_rejected` | Show user-facing rejection reason. | No unless suggested |
| `backend_busy` | Keep command available or retry after delay. | No |
| `resync_required` | Enter stale/resync flow. | Yes |
| `internal_error` | Show generic error and diagnostics link if available. | Maybe |
| network error | Show offline/retry state. | No until reconnect |
| cursor expired | Enter stale/resync flow. | Yes |

## 6. Query Mapping

| UI Need | Query | ViewModel |
|---|---|---|
| Main Page initial load | `GET /api/v1/sessions/{sessionId}/snapshot` | `MainPageSnapshot` |
| Resync | same as initial load | `MainPageSnapshot` |
| Task tree refresh | `GET /api/v1/sessions/{sessionId}/task-tree` | `TaskTreeView` |
| Selected task detail | `GET /api/v1/sessions/{sessionId}/tasks/{taskNodeId}` | task detail fragment |
| Pending confirmations | `GET /api/v1/sessions/{sessionId}/confirmations/pending` | `ConfirmationActionView[]` |
| Result refresh | `GET /api/v1/sessions/{sessionId}/result` | `ResultCardView` |
| File changes | `GET /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/file-changes?recursive=true` | `FileChangeSummaryView` |
| Audit session | `GET /api/v1/sessions/{sessionId}/audit` | `AuditPageSnapshot`; backend model exists, route pending. |
| Audit task | `GET /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/audit` | `AuditPageSnapshot`; backend model exists, route pending. |
| Audit records | `GET /api/v1/sessions/{sessionId}/audit/records` and task-scoped equivalent | `AuditRecord[]`; endpoint pending. |
| Audit record detail | `GET /api/v1/sessions/{sessionId}/audit/records/{recordId}` | `AuditRecordDetail`; endpoint pending. |
| Audit evidence | `GET /api/v1/sessions/{sessionId}/audit/evidence/{evidenceId}` | `EvidenceDetail`; endpoint pending. |
| Diagnostics logs | reserved | link only from Audit Page |

## 7. Command Mapping By Input Mode

| Input Mode | Command | Payload Notes |
|---|---|---|
| `create_session_goal` | `POST /api/v1/sessions` or session input | Includes project/workflow and initial input. |
| `generate_task_tree` | `POST /api/v1/sessions/{sessionId}/task-tree/generate` | Creates or updates Draft TaskTree. |
| `global_guidance` | `POST /api/v1/sessions/{sessionId}/input` | Session-level guidance. |
| `task_guidance` | `POST /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/input` | Task-scoped guidance. |
| `task_revision_request` | `PATCH /api/v1/sessions/{sessionId}/tasks/{taskNodeId}` or task input | Use patch for structured edits, input for natural language revision. |
| `clarification_answer` | ask/confirmation response endpoint | Target must be explicit. |
| `disabled_readonly` | none | Do not submit. |

Command response `accepted` should create pending command state only. Final UI status changes must come from events or queries.

## 8. Event Mapping

| Backend/UI Event | Mapping Behavior |
|---|---|
| `session.status_changed` | Update session summary or query snapshot. |
| `session.resync_required` | Full snapshot resync. |
| `task.tree.changed` | Query TaskTreeView or snapshot. |
| `task.node.changed` | Query/patch affected TaskNodeCardView and selected detail. |
| `message.appended` | Append full message or query messages. |
| `confirmation.created` | Add pending confirmation and update task badge. |
| `confirmation.resolved` | Update confirmation status, message stream, task badge. |
| `result.updated` | Query or patch result card. |
| `file_changes.updated` | Query file summary. |
| `audit.summary_updated` | Query/patch audit summary and audit links. |
| `audit.records_changed` | Query AuditPageSnapshot or scoped records. |
| `audit.record_updated` | Query selected audit record detail or current AuditPageSnapshot. |
| `audit.evidence_hidden` | Query selected audit record detail or evidence detail; do not reconstruct hidden evidence client-side. |
| `audit.snapshot_stale` | Enter Audit Page stale/resync flow and query AuditPageSnapshot. |
| `command.completed` | Mark pending command complete. |
| `command.failed` | Mark pending command failed, show local error, and query current MainPageSnapshot for compatibility with the existing Main Page event router. |

Unsupported events follow `docs/frontend/event-reducer-contract.md`: log, ignore if harmless, resync if visible state may be affected.

## 9. Mock Scenarios

Mock scenarios should be named by product state, not component screenshot names.

Required mock groups:

- Main happy path: empty -> understanding -> draft ready -> running -> confirmation -> done.
- Planning asks: awaiting user, answered, rejected.
- Task execution: pending, running, done, failed, cancelled.
- Confirmation: pending, resolving, resolved, expired, resolve failed.
- Audit: session overview, task detail, filtered records, empty, partial, inconclusive, load error.
- API errors: bad request, command rejected, version conflict, backend busy, internal error.
- Event stream: duplicate event, unsupported event, malformed event, cursor expired, resync required.
- Permission: readonly session, non-editable task, cannot resolve confirmation.

Each mock must declare:

```ts
type MockScenarioManifest = {
  id: string;
  page: "main" | "audit";
  title: string;
  canonicalStates: {
    planning?: PlanningState;
    readiness?: TaskNodeReadiness;
    execution?: ExecutionStatus;
    confirmation?: ConfirmationStatus;
    auditVerdict?: AuditVerdict;
  };
  expectedRoute: string;
  expectedPrimaryActions: string[];
  expectedDisabledActions: string[];
};
```

## 10. Migration Checklist For Existing Frontend Code

This checklist is intentionally incremental. It does not require refactoring MainPage immediately.

1. Add frontend types for `PlanningState`, `TaskNodeReadiness`, `ExecutionStatus`, `ConfirmationStatus`, `LocalConfirmationStatus`, and `AuditVerdict`.
2. Keep current `TaskNodeStatus` temporarily, but introduce adapter mapping from `TaskNodeStatus` to separate readiness/execution fields.
3. Rename canonical use of frontend `queued` to `execution = pending` plus label `Queued`.
4. Remove canonical use of frontend `waiting_user`; derive it from pending confirmation or planning ask.
5. Extend mock fixtures to include the required mock scenario manifest.
6. Add `InputView.mode` before changing command behavior.
7. Add route constants for Main session, Audit session, and Audit task.
8. Add frontend Audit Page ViewModel types matching the additive backend
   contract before implementing the Audit Page component.
9. Update event reducer coverage for all declared events before connecting real SSE broadly.
10. Move visible dev-only state picker behind a dev flag.
11. Introduce status presentation mapping in one place before changing CSS or visual design.
12. Add API adapter tests for backend `pending` -> UI execution `pending` -> label `Queued`.
13. Add tests for confirmation lifecycle: pending -> resolving -> resolved and pending -> resolving -> resolve_failed.
14. Add resync tests for `session.resync_required`, cursor expired, unknown visible id, and version conflict.
15. Only after these mappings are tested, refactor MainPage internals into hooks/components.

## 11. Acceptance Criteria

- Backend/domain statuses are mapped into separate UI dimensions.
- UI labels such as `Queued` and `Needs input` are presentation mappings.
- Main Page and Audit Page API needs are covered by query mappings.
- Every input mode maps to exactly one command path or explicit disabled state.
- Event handling maps to reducer behavior and resync fallback.
- Mock scenarios cover success, loading, empty, error, permission, confirmation, audit, and resync states.
- Existing frontend can migrate incrementally without changing CSS or refactoring MainPage in the same step.
