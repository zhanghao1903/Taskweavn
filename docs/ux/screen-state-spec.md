# Screen State Specification

> Status: draft
> Last Updated: 2026-06-04
> Scope: Plato Main Page and Audit Page screen states.
> Related: `docs/product/plato-mvp-prd.md`, `docs/product/plato-main-page-ux-flow.md`, `docs/product/plato-audit-page-ux-flow.md`, `docs/product/plato-audit-page-prd.md`, `docs/frontend/ui-viewmodel-contract.md`, `docs/ux/ask-ui-spec.md`, `docs/ux/confirmation-ui-spec.md`

## 1. Purpose

This document defines the canonical UX state model for Plato's Main Page and Audit Page.

The most important rule is that product state must not be collapsed into one overloaded `status` field. The UI must keep these dimensions separate:

1. Planning state: where the user's intent is in the authoring process.
2. Task node readiness: whether a task node is draft, accepted, published, or cancelled.
3. Execution status: the backend TaskBus execution state for published tasks.
4. Confirmation status: whether a user confirmation is pending, resolving, resolved, expired, or failed locally.
5. Audit verdict: whether evidence passed, warned, failed, is inconclusive, or is unavailable.

UI labels, badge colors, icons, and screen copy are presentation mappings over these canonical dimensions. They are not the canonical state.

## 2. Canonical State Dimensions

### 2.1 Planning State

Planning state describes the session-level authoring flow before and around a Draft TaskTree.

Prefer backend authoring concepts as the source:

| Planning State | Backend Source | Meaning | Primary UI Label |
|---|---|---|---|
| `empty` | no RawTask and no DraftTaskTree | New session has no meaningful input yet. | New |
| `capturing_input` | input command accepted, no RawTask result yet | User input is being recorded or classified. | Understanding |
| `assessing` | `RawTask.status = assessing` | System is evaluating feasibility and missing information. | Understanding |
| `awaiting_user` | `RawTask.status = awaiting_user` | System needs clarification or permission before planning. | Needs input |
| `ready_to_plan` | `RawTask.status = ready_to_plan` | Input can produce a Draft TaskTree. | Ready to plan |
| `draft_ready` | DraftTaskTree exists with editable nodes | User can review/edit the Draft TaskTree. | Draft ready |
| `published` | DraftTaskTree was published | Draft lineage has crossed into published tasks. | Published |
| `rejected` | `RawTask.status = rejected` | Request cannot be planned safely or usefully. | Cannot proceed |
| `cancelled` | RawTask or DraftTaskTree cancelled | Planning was intentionally stopped. | Cancelled |

Planning state is session-level. It must not be used as the execution status for a TaskNode.

### 2.2 Task Node Readiness

Task node readiness describes whether a task node is editable, publishable, published, or cancelled.

| Readiness | Backend Source | Meaning | Main Page Rule |
|---|---|---|---|
| `draft` | `DraftTaskNode.status = draft` | Node can still be edited. | Show edit affordances if permissions allow. |
| `accepted` | `DraftTaskNode.status = accepted` | Node passed authoring validation and is publishable. | Show ready/publishable state. |
| `published` | `DraftTaskNode.status = published` plus DraftToPublishedMapping | Node has a published Task identity. | Show published identity and switch execution display to TaskDomain. |
| `cancelled` | `DraftTaskNode.status = cancelled` | Node is intentionally removed from publish path. | Show cancelled/read-only, hide execution controls. |
| `unknown` | missing or inconsistent mapping | UI cannot determine readiness. | Show recoverable error and request resync. |

Readiness does not answer whether the published task is running or done. That belongs to execution status.

### 2.3 Execution Status

Execution status is the canonical backend TaskBus state for published tasks.

Prefer `TaskDomain.status`:

| Execution Status | Backend Source | Meaning | Main Page Label |
|---|---|---|---|
| `not_started` | no published task yet | No TaskBus execution exists for this node. | Draft |
| `pending` | `TaskDomain.status = pending` | Published task is queued or eligible to run. | Queued |
| `running` | `TaskDomain.status = running` | Agent/tool execution is active. | Running |
| `done` | `TaskDomain.status = done` | Execution completed successfully. | Done |
| `failed` | `TaskDomain.status = failed` | Execution failed and may support retry. | Failed |
| `cancelled` | cancellation command or readiness cancelled | User/system cancelled before completion. | Cancelled |
| `unknown` | unexpected backend value | UI cannot safely present execution state. | Unknown |

`queued` is a UI label for backend `pending`; it should not become a canonical domain status.

### 2.4 Confirmation Status

Confirmation status is independent of task execution.

Backend canonical values:

| Confirmation Status | Source | Meaning |
|---|---|---|
| `pending` | `ConfirmationActionView.status = pending` | User action is required. |
| `resolved` | `ConfirmationActionView.status = resolved` | User selected an option and backend recorded it. |
| `expired` | `ConfirmationActionView.status = expired` | Confirmation is no longer actionable. |

Frontend local-only overlays:

| Local State | Meaning | Rule |
|---|---|---|
| `resolving` | User selected an option and command is in flight. | Disable duplicate submit for that confirmation. |
| `resolve_failed` | Respond command failed before backend resolution. | Re-enable actions if backend status is still `pending`. |

`waiting_user` is a derived UI state: there is at least one pending confirmation or unanswered planning ask. It is not a TaskDomain execution status.

### 2.5 Audit Verdict

Audit verdict is a trust-plane result, not an execution state.

| Audit Verdict | Meaning | Main Page Label | Audit Page Label |
|---|---|---|---|
| `not_available` | No audit summary exists yet. | Audit pending | Not available |
| `passed` | Evidence supports the task/result. | Audit passed | Passed |
| `warning` | Task completed, but evidence has gaps, policy warnings, or unresolved risks. | Warning | Warning |
| `failed` | Evidence shows a failure, violation, or untrusted result. | Audit failed | Failed |
| `inconclusive` | Audit could not establish confidence. | Inconclusive | Inconclusive |

Current backend `AuditAgent` values such as `pass`, `fail`, and `inconclusive` must be mapped to this UI verdict model. `warning` can be derived from risk findings, partial evidence, policy warnings, or validation gaps.

## 3. Route Model

Routes must preserve user context.

| Route | Page | Required Params | Optional Params | Purpose |
|---|---|---|---|---|
| `/projects/:projectId/workflows/:workflowId/sessions/:sessionId` | Main Page | project, workflow, session | `taskNodeId`, `messageId` | Control plane. |
| `/sessions/:sessionId` | Main Page fallback | session | `taskNodeId` | Recoverable deep link when project/workflow is inferred. |
| `/sessions/:sessionId/audit` | Audit Page | session | `filter`, `recordId` | Session-scope trust plane. |
| `/sessions/:sessionId/tasks/:taskNodeId/audit` | Audit Page | session, task node | `filter`, `recordId` | Task-scope trust plane. |
| `/sessions/:sessionId/diagnostics/logs` | Diagnostics | session | `taskNodeId`, `recordId`, `category` | Reserved logs deep link. |
| `/settings` | Settings | none | `sessionId`, `taskNodeId` | Reserved configuration surface. |

Audit Page must be read-only. Any execution, retry, edit, or confirmation action must return to Main Page with the original session/task context.

## 4. Input Modes

The bottom input is one surface with multiple modes. The mode must be explicit in the ViewModel or local UI state.

| Input Mode | Scope | Command | Enabled When | Placeholder Intent |
|---|---|---|---|---|
| `create_session_goal` | session | create session or append initial input | no active session goal | Describe what you want to accomplish. |
| `generate_task_tree` | session | generate Draft TaskTree | planning state is `empty`, `ready_to_plan`, or no tree exists | Turn this goal into tasks. |
| `global_guidance` | session | append session input | session exists | Add guidance for this session. |
| `task_guidance` | selected task | append task input | task selected and `canAppendGuidance` | Add guidance to this task. |
| `task_revision_request` | selected draft/pending task | update or append task input | selected node editable | Ask for a task revision. |
| `clarification_answer` | planning ask or confirmation | respond to ask/confirmation | actionable item selected | Answer the request. |
| `disabled_readonly` | none | none | session archived, audit page, permission denied, stale snapshot | Explain why input is disabled. |

The UI must not infer mode only from placeholder text. Mode determines command payload and validation.

## 5. Main Page Screen States

These are derived screen states for layout and copy. They are computed from the canonical dimensions above.

| State | Required Conditions | Primary Components | Required Empty/Loading/Error Handling |
|---|---|---|---|
| `S1 Empty` | planning `empty`, no task tree | onboarding workspace, input | empty copy, create goal mode |
| `S2 Understanding` | planning `capturing_input` or `assessing` | progress hint, message stream | loading skeleton, cancel optional |
| `S3 Clarification Needed` | planning `awaiting_user` | actionable ask attached to context | answer mode, expired/error handling |
| `S4 Draft Ready` | planning `draft_ready`, nodes exist | TaskTree, edit/publish affordances | validation warnings visible |
| `S5 Task Selected` | selected task exists | Task detail panel | missing selected task triggers reselection/resync |
| `S6 Task Editing` | selected node readiness `draft`, local edit active | edit controls | save/cancel, conflict error |
| `S7 Published/Pending` | readiness `published`, execution `pending` | queued task cards | explain waiting state |
| `S8 Running` | any execution `running` | progress, live messages | streaming/loading states |
| `S9 Waiting Confirmation` | pending confirmation exists | confirmation attached to task | resolving/failed/expired states |
| `S10 Completed` | relevant execution `done` | result, file summary, audit link | success state, audit available/pending |
| `S11 Failed` | relevant execution `failed` | failure summary, retry if allowed | error copy, audit link if available |
| `S12 Stale/Resync` | cursor expired, resync required, or snapshot stale | readonly overlay plus refresh | disable high-risk commands |
| `S13 Load Error` | initial query failed | error panel | retry, diagnostics link for technical users |

ASK-specific component placement and state tables live in
`docs/ux/ask-ui-spec.md`. Product 1.0 uses Main Work Area placement for
Authoring ASK and Detail Panel placement for Execution ASK.

Confirmation-specific component placement and state tables live in
`docs/ux/confirmation-ui-spec.md`. Product 1.0 uses Detail Panel placement for
pending confirmation actions; TaskTree and MessageStream provide signals and
navigation only.

## 6. Audit Page Screen States

Audit Page is a trust plane. It displays evidence and navigation back to Main Page, not controls that mutate tasks.

| State | Required Conditions | Required Behavior |
|---|---|---|
| `A1 Task Audit Default` | task scope loaded, records exist | show overview, filters, timeline, no selected detail by default or select first important record. |
| `A2 Record Selected` | `recordId` present or user selected record | keep timeline context visible, show detail drawer/panel. |
| `A3 Session Audit Overview` | session scope, no task filter | group records by task/session and show scope switch. |
| `A4 Filtered Records` | filter set | keep counts visible, show filtered empty state when count zero. |
| `A5 Empty Audit` | no records, no audit summary | explain no audit evidence is available yet. |
| `A6 Running/Partial` | audit job running or evidence still arriving | show partial records and clear incomplete label. |
| `A7 Failed To Load` | audit query failed | retry, return to Main Page, do not imply trust verdict. |
| `A8 Inconclusive` | verdict `inconclusive` | explain what is missing and what can be checked. |
| `A9 Config Evidence` | effective config or config change record exists | show summary and link to Settings, no editing. |
| `A10 Related Logs Reserved` | record has log deep link | show link to diagnostics, do not embed raw logs by default. |

## 7. Permission States

Permissions are separate from status. A task can be `pending` but not editable if the backend says so.

| Permission | UI Rule |
|---|---|
| `canEdit` | show edit affordance only for editable readiness/execution combinations. |
| `canAppendGuidance` | enable task-scoped input. |
| `canResolveConfirmation` | enable confirmation actions. |
| `canPublish` | enable publish button for valid Draft TaskTree. |
| `canCancel` | enable cancel only for draft or not-yet-running work. |
| `canRetry` | enable retry only for failed work when retry is supported. |
| `readonlyReason` | show when an expected control is disabled. |

## 8. Stale Snapshot And Resync UX

The UI enters stale/resync mode when:

- SSE cursor expires.
- A `session.resync_required` event arrives.
- An event references unknown ids that cannot be patched.
- A command returns `resync_required` or `version_conflict`.
- Snapshot age exceeds the configured freshness window while connected events are unavailable.

Required UX behavior:

1. Keep the current screen visible.
2. Mark high-risk controls readonly while resync is in progress.
3. Re-query the session snapshot.
4. Restart events from the returned cursor.
5. Restore selection by `taskNodeId` when possible.
6. If selected item no longer exists, select the nearest parent or show a non-blocking context lost message.
7. If resync fails, keep read-only stale data and show retry.

## 9. Mock Scenarios

The frontend mock layer must include at least:

| Scenario | Purpose |
|---|---|
| `empty-session` | new session with no task tree. |
| `understanding` | input accepted, planning in progress. |
| `clarification-needed` | RawTask awaiting user answer. |
| `draft-ready` | editable Draft TaskTree. |
| `task-selected` | detail panel with selected draft task. |
| `running-with-messages` | published tasks running with live stream. |
| `waiting-confirmation` | pending confirmation attached to a task. |
| `confirmation-resolving-failed` | local command failure while backend remains pending. |
| `completed-with-result-file-audit` | result, file summary, audit link. |
| `failed-retryable` | failed task with retry permission. |
| `audit-task-default` | task audit records loaded. |
| `audit-session-overview` | session-level audit loaded. |
| `audit-empty` | no records. |
| `audit-running-partial` | partial records and incomplete verdict. |
| `audit-load-error` | query error. |
| `stale-resync-required` | cursor expired or resync event. |
| `permission-denied-readonly` | controls disabled with reason. |

## 10. Acceptance Criteria

- Planning state, task node readiness, execution status, confirmation status, and audit verdict are represented as separate model fields.
- Backend/domain status values remain canonical; UI labels are derived mappings.
- Every Main Page Figma state maps to a derived screen state in this document.
- Every Audit Page Figma state maps to a derived screen state in this document.
- Loading, empty, error, partial, success, permission, and stale/resync states have named scenarios.
- Input mode is explicit and maps to a command.
- Audit Page has task-scope and session-scope routes.
- Audit Page remains read-only and preserves return-to-Main context.
- Mock fixtures cover the required scenarios before real backend integration.
- Existing frontend migration can proceed without refactoring MainPage in the same step.
