# Plato Prototype State Map

> Status: minimal production-grade contract
> Last Updated: 2026-05-24
> Scope: State storyboard and transition contract required before interactive
> Figma prototype work and frontend architecture.
> Non-goals: no Figma prototype creation, no frontend implementation, no old
> Figma migration.

## 1. Purpose

This document maps approved Main Page and Audit Page screen states to
canonical product state dimensions, route context, backend/ViewModel sources,
and future Figma prototype frames.

It is the contract for turning static Figma frames into a dynamic prototype.
It does not create those frames or interactions.

## 2. Source Documents

| Source | Role |
|---|---|
| `docs/ux/screen-state-spec.md` | Canonical Main Page and Audit Page state list. |
| `docs/product/canonical-status-model.md` | Separate status dimensions and mapping rules. |
| `docs/frontend/ui-viewmodel-contract.md` | Main Page and Audit Page ViewModel shape. |
| `docs/frontend/event-reducer-contract.md` | Event/reducer behavior, unsupported events, stale snapshot handling. |
| `docs/frontend/api-ui-mapping.md` | Backend-to-UI source mapping. |
| `docs/engineering/audit-page-contract.md` | Audit Page snapshot, record, evidence, permissions, and events. |
| `docs/design/design-system.md` | Token contract. |
| `docs/design/component-spec.md` | Component inventory and code mapping. |
| `docs/design/component-state-matrix.md` | Component state coverage. |

## 3. Route Model

| Route | Prototype frame group | Required params | Optional query | Notes |
|---|---|---|---|---|
| `/projects/:projectId/workflows/:workflowId/sessions/:sessionId` | `06 - Main UX Flow`, `07 - Main Screen States` | project, workflow, session | `taskNodeId`, `messageId` | Main control plane. |
| `/sessions/:sessionId` | `06 - Main UX Flow`, `07 - Main Screen States` | session | `taskNodeId` | Recoverable fallback. |
| `/sessions/:sessionId/audit` | `08 - Audit UX Flow`, `09 - Audit Screen States` | session | `filter`, `recordId` | Session-scope Trust Plane. |
| `/sessions/:sessionId/tasks/:taskNodeId/audit` | `08 - Audit UX Flow`, `09 - Audit Screen States` | session, task node | `filter`, `recordId` | Task-scope Trust Plane. |

Audit routes are read-only. Prototype actions that mutate tasks must return to
Main Page before showing the mutation.

## 4. Main Page State Map

| State | Canonical conditions | Primary components | Figma page target | Backend/ViewModel source |
|---|---|---|---|---|
| `S1 Empty` | planning `empty`, no task tree | `PlanningStatusBanner`, `ContextInput`, empty task area | `07 - Main Screen States` | `MainPageSnapshot.planning`, no `taskTree` |
| `S2 Understanding` | planning `capturing_input` or `assessing` | progress banner, message stream skeleton | `07 - Main Screen States` | RawTask creation/assessment projection |
| `S3 Clarification Needed` | planning `awaiting_user`, pending planning ask | ask card, input mode `clarification_answer` | `07 - Main Screen States` | `PlanningView.asks[]` |
| `S4 Draft Ready` | planning `draft_ready`, tree nodes exist | `TaskTree`, publish/edit affordances | `07 - Main Screen States` | `TaskTreeView`, task readiness |
| `S5 Task Selected` | selected `taskNodeId` exists | task card selected, detail panel | `07 - Main Screen States` | selected `TaskNodeCardView` |
| `S6 Task Editing` | selected readiness `draft`, local edit active | task editor/detail panel | `07 - Main Screen States` | frontend local edit state plus permissions |
| `S7 Published/Pending` | readiness `published`, execution `pending` | queued task cards, disabled edit | `07 - Main Screen States` | task execution projection |
| `S8 Running` | any execution `running` | running card, live messages | `07 - Main Screen States` | TaskBus execution and events |
| `S9 Waiting Confirmation` | pending confirmation exists | `ConfirmationCard`, scoped input if needed | `07 - Main Screen States` | `ConfirmationActionView`, local command state |
| `S10 Completed` | relevant execution `done` | result, file summary, audit link | `07 - Main Screen States` | result/file/audit summary projections |
| `S11 Failed` | relevant execution `failed` | failure summary, retry if allowed | `07 - Main Screen States` | task failure projection and permissions |
| `S12 Stale/Resync` | cursor expired, resync required, or stale snapshot | readonly overlay, refresh state | `07 - Main Screen States` | event reducer/runtime state |
| `S13 Load Error` | initial query failed | error panel, retry, diagnostics link | `07 - Main Screen States` | query error envelope |

## 5. Audit Page State Map

| State | Canonical conditions | Primary components | Figma page target | Backend/ViewModel source |
|---|---|---|---|---|
| `A1 Task Audit Default` | task scope loaded, records exist | `AuditOverview`, filters, timeline | `09 - Audit Screen States` | `AuditPageSnapshot` task scope |
| `A2 Record Selected` | `recordId` present or selected | timeline plus detail panel | `09 - Audit Screen States` | `selectedRecord` / record detail endpoint |
| `A3 Session Audit Overview` | session scope, no task filter | grouped records and return target | `09 - Audit Screen States` | session audit snapshot |
| `A4 Filtered Records` | filter query set | filter list selected, filtered timeline | `09 - Audit Screen States` | `AuditFilterView[]`, `records[]` |
| `A5 Empty Audit` | no records and no summary | empty state | `09 - Audit Screen States` | `pageState.empty`, `overview.not_available` |
| `A6 Running/Partial` | completeness `running` or `partial` | partial overview, visible records retained | `09 - Audit Screen States` | `AuditOverview.completeness` |
| `A7 Failed To Load` | audit query failed | error panel, retry, return target | `09 - Audit Screen States` | query error envelope or `pageState.error` |
| `A8 Inconclusive` | verdict `inconclusive` | missing evidence explanation | `09 - Audit Screen States` | `AuditOverview.verdict` |
| `A9 Config Evidence` | effective config or config record exists | config summary and record detail | `09 - Audit Screen States` | `EffectiveConfigSummary`, config records |
| `A10 Related Logs Reserved` | logs link exists | diagnostics link, no embedded raw logs | `09 - Audit Screen States` | `RelatedLogsLink[]`, `AuditPermissions` |

## 6. Main Page Prototype Transitions

| Transition | Trigger | Source -> Destination | Data rule |
|---|---|---|---|
| Create session goal | user submits initial input | `S1 -> S2` | command pending is local; final state comes from snapshot/event |
| Need clarification | backend asks for more info | `S2 -> S3` | planning ask must be present |
| Generate draft tree | planning becomes draft ready | `S2/S3 -> S4` | tree exists and readiness is not execution |
| Select task | user selects task node | `S4 -> S5` | selected id persisted in query/local state |
| Edit draft task | user starts edit | `S5 -> S6` | requires readiness `draft` and permission |
| Publish tree/node | user publishes | `S4/S5 -> S7` | readiness becomes `published`; execution may be `pending` |
| Start execution | TaskBus starts | `S7 -> S8` | execution `running` |
| Ask confirmation | backend requires user confirmation | `S8 -> S9` | confirmation `pending`; execution is not overwritten |
| Resolve confirmation | user submits option | `S9 -> S8` or `S9 -> S10` | local `resolving` until backend status/event confirms |
| Complete execution | backend reports done | `S8 -> S10` | result/file/audit summaries may arrive separately |
| Fail execution | backend reports failed | `S8 -> S11` | retry depends on permission/action availability |
| Resync required | stale event/cursor/version conflict | `any -> S12` | keep visible data, disable risky controls |
| Load failed | initial query error | `initial -> S13` | show retry and preserve route context |

## 7. Audit Page Prototype Transitions

| Transition | Trigger | Source -> Destination | Data rule |
|---|---|---|---|
| Open task audit | user activates audit entry from task/result/file | `S10/S11 -> A1` | route preserves `sessionId` and optional `taskNodeId` |
| Open session audit | user activates session-level audit | Main Page -> `A3` | scope `session` |
| Select record | user selects timeline item | `A1/A3/A4 -> A2` | `recordId` query may be set |
| Change filter | user selects filter | `A1/A2/A3 -> A4` | counts remain visible, zero-count filter shows empty list |
| Empty result | selected filter has no records | `A4 -> A5` | page is not failed |
| Partial update | records arrive while audit incomplete | `A1/A3 -> A6` | visible records retained |
| Query failed | audit snapshot/detail request fails | `any audit -> A7` | do not imply trust verdict |
| Inconclusive verdict | audit cannot establish confidence | `A1/A2/A3 -> A8` | explain missing evidence |
| View config record | config record selected | `A1/A2/A4 -> A9` | read-only; settings link may exist |
| View related logs | logs link selected | `A2/A9 -> A10` | link to diagnostics; raw logs not embedded |
| Return to Main Page | user activates return target | `any audit -> Main Page` | route uses `MainPageReturnTarget` focus |

## 8. Prototype Event And Resync Rules

Interactive prototypes should model these reducer-level behaviors:

| Event/condition | Prototype representation |
|---|---|
| supported event updates visible object | update badge/list/detail while preserving selection |
| unsupported event type | show no visible mutation; dev handoff notes fallback to resync |
| event references unknown id | enter stale/resync state |
| cursor expired | enter stale/resync state |
| command accepted | show `pending_command`; do not jump to terminal success |
| command rejected | show local error; state remains from last snapshot |
| audit snapshot stale | show stale audit state and retry/resync affordance |
| hidden/redacted evidence | show disclosure state, not raw payload |

## 9. Mock Scenario Coverage

| Scenario | Required state coverage |
|---|---|
| `empty-session` | `S1` |
| `understanding` | `S2` |
| `clarification-needed` | `S3` |
| `draft-ready` | `S4` |
| `task-selected` | `S5` |
| `task-editing` | `S6` |
| `published-pending` | `S7` |
| `running-with-messages` | `S8` |
| `waiting-confirmation` | `S9` |
| `confirmation-resolving-failed` | `S9` local error |
| `completed-with-result-file-audit` | `S10`, audit entry to `A1` |
| `failed-retryable` | `S11` |
| `stale-resync-required` | `S12` |
| `load-error` | `S13` |
| `audit-task-default` | `A1` |
| `audit-record-selected` | `A2` |
| `audit-session-overview` | `A3` |
| `audit-filtered-records` | `A4` |
| `audit-empty` | `A5` |
| `audit-running-partial` | `A6` |
| `audit-load-error` | `A7` |
| `audit-inconclusive` | `A8` |
| `audit-config-evidence` | `A9` |
| `audit-related-logs-reserved` | `A10` |

## 10. Figma Prototype Readiness Criteria

Actual Figma prototype work is ready only when:

1. destination frames exist for each state used by a transition;
2. components used by the frame are listed in `docs/design/component-spec.md`;
3. required component states exist in
   `docs/design/component-state-matrix.md`;
4. route parameters and selected object persistence are represented in Dev
   Handoff notes;
5. audit transitions remain read-only;
6. stale/resync, empty, loading, error, permission, and partial states are
   included;
7. old Figma files are used only as reference input.

## 11. Acceptance Criteria

- Main Page and Audit Page state names map to canonical status dimensions.
- Prototype transitions identify source state, destination state, trigger, and
  data rule.
- Audit Page entry and return context are explicit.
- Mock scenario coverage is sufficient for future frontend and Figma work.
- This document unblocks production Figma prototype planning, but not dev
  handoff until actual Figma frames, components, and interactions are created.
