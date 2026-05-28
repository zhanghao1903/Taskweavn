# Plato Component State Matrix

> Status: minimal production-grade contract
> Last Updated: 2026-05-24
> Scope: Required component states, variants, and canonical status mappings
> before production Figma component work and frontend architecture.
> Non-goals: no frontend implementation, no high-fidelity Figma variants, no
> old Figma migration.

## 1. Purpose

This matrix defines the minimum state and variant coverage required for Plato
components. It exists to prevent Figma components and frontend components from
shipping with only the happy path.

Sources:

- `docs/design/design-system.md`
- `docs/design/component-spec.md`
- `docs/product/canonical-status-model.md`
- `docs/engineering/audit-page-contract.md`
- `docs/frontend/event-reducer-contract.md`
- `docs/ux/screen-state-spec.md`

## 2. Standard State Vocabulary

| State | Meaning | Required for |
|---|---|---|
| `default` | Resting state. | all components |
| `hover` | Pointer hover affordance. | clickable controls/cards |
| `focus_visible` | Keyboard focus ring. | all focusable components |
| `active` | Pressed or currently acting state. | buttons, list items, tabs |
| `selected` | User-selected item or active tab/filter. | navigation, cards, filters |
| `disabled` | User sees control but cannot use it. | expected unavailable actions |
| `hidden` | Control should not be rendered. | irrelevant actions |
| `loading` | Initial or command loading. | data-driven and command components |
| `pending_command` | Command submitted; final state not confirmed. | mutation controls |
| `error` | Recoverable component-level error. | forms, query panels, command controls |
| `empty` | Data loaded with no records/items. | lists, panels, pages |
| `partial` | Some data available, some incomplete. | audit, timeline, streaming regions |
| `stale` | Visible data is outdated or resyncing. | data-driven pages/components |
| `readonly` | Data visible, mutations unavailable. | audit page, permission-limited views |
| `redacted` | Safe summary visible, sensitive content withheld. | audit/evidence/log components |

## 3. Tone Vocabulary

Tones are presentation only. They must not become canonical product status.

| Tone | Use |
|---|---|
| `neutral` | Normal, unavailable, inactive, not started. |
| `info` | In progress, selected, explanatory, inconclusive. |
| `success` | Passed, done, resolved, complete. |
| `warning` | User attention, pending confirmation, partial evidence. |
| `danger` | Failed, denied, rejected, command error. |

## 4. Canonical Status To Visual Mapping

### 4.1 Planning State

| Planning state | Primary tone | Component states |
|---|---|---|
| `empty` | neutral | input default, task area empty |
| `capturing_input` | info | input loading, progress visible |
| `assessing` | info | planning banner loading |
| `awaiting_user` | warning | ask selected, input mode `clarification_answer` |
| `ready_to_plan` | info | generate action enabled |
| `draft_ready` | success | task tree visible, edit/publish affordances |
| `published` | success | execution views become primary |
| `rejected` | danger | readonly with reason |
| `cancelled` | neutral | readonly terminal |
| `unknown` | danger | stale/error-safe state |

### 4.2 Task Readiness

| Readiness | Primary tone | Component states |
|---|---|---|
| `draft` | neutral | editable if permission allows |
| `accepted` | info | publishable |
| `published` | success | execution badge visible |
| `cancelled` | neutral | readonly terminal |
| `unknown` | danger | disabled actions, resync hint |

### 4.3 Execution Status

| Execution status | Primary tone | Component states |
|---|---|---|
| `not_started` | neutral | no execution controls except valid publish/edit actions |
| `pending` | info | queued/loading presentation |
| `running` | warning | progress/live message state |
| `done` | success | result/audit entry discoverable |
| `failed` | danger | retry if available, error summary |
| `cancelled` | neutral | readonly terminal |
| `unknown` | danger | stale/error-safe state |

### 4.4 Confirmation Status

| Backend/local state | Primary tone | Component states |
|---|---|---|
| `pending` | warning | action buttons enabled if permission allows |
| `resolved` | success | readonly history |
| `expired` | neutral | disabled with expired reason |
| `resolving` | warning | pending command, duplicate submit disabled |
| `resolve_failed` | danger | inline error, retry enabled if backend still pending |

### 4.5 Audit Verdict

| Audit verdict | Primary tone | Component states |
|---|---|---|
| `not_available` | neutral | empty/not started |
| `passed` | success | trusted but inspectable |
| `warning` | warning | needs review |
| `failed` | danger | failed evidence |
| `inconclusive` | info | missing or insufficient evidence |

## 5. Base Component Matrix

| Component | Variants | Required states | Notes |
|---|---|---|---|
| `Base/Button` | primary, secondary, ghost, danger; sm, md | default, hover, focus_visible, active, disabled, loading | `loading` disables duplicate submit. |
| `Base/IconButton` | neutral, primary, danger; sm, md | default, hover, focus_visible, active, disabled, loading | Must always have accessible label. |
| `Base/Badge` | neutral, info, success, warning, danger; sm, md | default, selected, disabled | Represents presentation tone only. |
| `Base/Panel` | surface, muted, selected, warning, danger | default, loading, error, stale, readonly | Panel does not own business state. |
| `Base/Card` | surface, selected, warning, danger | default, hover, focus_visible, selected, disabled | Use for repeated item surfaces only. |
| `Base/List` | plain, selectable | loading, empty, error, selected | List owns collection state, not item business status. |
| `Base/Text` | eyebrow, heading, subheading, body, muted, label | default | No viewport-scaled type. |
| `Base/Input` | text, command | default, hover, focus_visible, disabled, readonly, error, loading | Error state must reserve space for message. |
| `Base/TextArea` | compact, expanded | default, focus_visible, disabled, readonly, error, auto-grow | Must avoid overlapping text on wrap. |
| `Base/Tabs` | horizontal, segmented | default, selected, hover, focus_visible, disabled, overflow | Selected state cannot rely on color only. |
| `Base/Tooltip` | plain | default, delayed-open | Use for unfamiliar icon buttons. |
| `Base/Dialog` | normal, destructive | default, loading, error | Focus trap required in implementation. |
| `Base/Drawer` | deferred placeholder | deferred | Not required for next Domain Components or Main/Audit Screen States; do not use until drawer behavior is specified. |
| `Base/Skeleton` | text, block, card, timeline-row | loading | Only used for real data wait/generation. |
| `Base/Toast` | info, success, warning, danger | default, action, dismissing | Non-blocking status feedback. |
| `Base/EmptyState` | neutral, action-required, error | empty, error | Must include next action when available. |
| `Base/ErrorState` | page, panel, inline | default, retryable, non_retryable, retrying | Generic error surface; owning component supplies query, command, permission, or stale/resync error facts. |

## 6. Layout Component Matrix

| Component | Variants | Required states | Responsive requirements |
|---|---|---|---|
| `Layout/AppShell` | main, audit | loading, ready, error, stale | desktop full workbench; tablet condensed; mobile stacked |
| `Layout/TopBar` | main, audit | default, readonly, stale | product mark, context, return/action area must not overlap |
| `Layout/WorkflowSidebar` | expanded, collapsed | default, selected, empty, loading | collapses before content truncates |
| `Layout/WorkbenchGrid` | two-column, three-column | loading, ready, error | stable panel widths, no content overlap |
| `Layout/DetailPanel` | session, task, result, audit | empty, selected, loading, error, stale | scroll body independent from shell |
| `Layout/BottomInputDock` | session, task, clarification, readonly | default, focus_visible, disabled, loading, error | fixed/sticky behavior must preserve visible input |
| `Layout/AuditShell` | session, task, record-selected | loading, ready, empty, partial, permission_denied, error, stale | audit is read-only; return target always visible |
| `Layout/AuditTimeline` | list, grouped | loading, empty, selected, partial, stale | selected record remains visible when possible |
| `Layout/AuditDetailPanel` | empty, detail | loading, empty, hidden, redacted, error | detail content scrolls without hiding timeline |

## 7. Domain Component Matrix

| Component | Canonical state source | Required states |
|---|---|---|
| `Domain/PlanningStatusBanner` | `PlanningView.state` | empty, loading, awaiting_user, draft_ready, rejected, cancelled, unknown |
| `Domain/TaskTree` | `TaskTreeView.readiness`, execution rollup | empty, loading, draft, published, mixed, error, stale |
| `Domain/TaskNodeCard` | `readiness`, `execution`, `confirmation`, `auditVerdict`, permissions | default, hover, focus_visible, selected, disabled, running, failed, waiting_confirmation, stale |
| `Domain/TaskNodeInspector` | selected `TaskNodeCardView` | empty, selected, loading, permission_denied, stale |
| `Domain/SessionMessageRow` | `SessionMessageView` | user, agent, system, streaming, error |
| `Domain/ConfirmationCard` | backend confirmation plus local overlay | pending, resolving, resolve_failed, resolved, expired, permission_denied |
| `Domain/ResultCard` | `ResultCardView` | loading, available, empty, error |
| `Domain/FileChangeSummary` | `FileChangeSummaryView` | empty, available, partial, error |
| `Domain/AuditSummaryLink` | `AuditSummaryView` or `AuditLinkView` | not_available, passed, warning, failed, inconclusive |
| `Domain/ContextInput` | input mode and action availability | default, task-scoped, clarification, disabled_readonly, loading, error |
| `Domain/AuditOverview` | `AuditOverview` | not_started, running, partial, complete, failed, hidden |
| `Domain/AuditFilterList` | `AuditFilterView[]` | selected, enabled, disabled, zero_count |
| `Domain/AuditRecordCard` | `AuditRecord` | default, hover, focus_visible, selected, partial, hidden, redacted, stale |
| `Domain/AuditRecordDetail` | `AuditRecordDetail` | empty, loading, detail, partial, hidden, redacted, permission_denied |
| `Domain/EvidenceRefList` | `EvidenceRef[]` / `EvidenceSummary[]` | available, hidden, redacted, unavailable, loading |
| `Domain/EffectiveConfigSummary` | `EffectiveConfigSummary | null` | unavailable, available, partial |
| `Domain/RelatedLogsLink` | `RelatedLogsLink[]`, `AuditPermissions` | enabled, disabled_permission, unavailable |

## 8. Audit Page Contract Matrix

| Audit contract state | Component coverage |
|---|---|
| `pageState.loading` | `Layout/AuditShell`, skeleton timeline/detail |
| `pageState.ready` | overview, filters, records, optional detail |
| `pageState.empty` | `Base/EmptyState`, filters with zero counts |
| `pageState.partial` | overview partial label, records retained |
| `pageState.hidden_evidence` | disclosure state, hidden evidence count |
| `pageState.permission_denied` | readonly shell with reason |
| `pageState.error` | `Base/ErrorState` in page or panel variant, retryable or non_retryable error panel |
| `pageState.stale` | stale banner and disabled high-risk controls, though Audit has no mutations |
| `AuditRecordFlags.partial` | partial badge and detail disclosure |
| `AuditRecordFlags.hidden` | hidden state, no raw payload |
| `AuditRecordFlags.redacted` | redaction indicator and safe summary |
| `AuditRecordFlags.stale` | stale label and resync affordance |

## 9. Acceptance Criteria

- Figma component creation has a required variant/state list before any write.
- Base, layout, and domain components cover loading, empty, error, disabled,
  readonly, and stale states where applicable.
- Canonical product states are mapped by dimension, not flattened.
- Audit Page evidence and disclosure states are represented explicitly.
- Missing variants block production Figma component work but do not block
  docs-only planning tasks.
