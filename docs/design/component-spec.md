# Plato Component Spec

> Status: minimal production-grade contract
> Last Updated: 2026-05-24
> Scope: Component inventory, variants, data ownership, Figma-to-code mapping,
> and readiness criteria before frontend architecture and production Figma
> component work.
> Non-goals: no frontend implementation, no high-fidelity Figma components, no
> old Figma migration.

## 1. Purpose

This document defines the component contract that must exist before Plato
creates production Figma components or starts the next frontend architecture
slice. It uses:

- `docs/design/design-system.md` for token rules;
- `docs/product/canonical-status-model.md` for status dimensions;
- `docs/frontend/ui-viewmodel-contract.md` for props and ViewModel ownership;
- `docs/engineering/audit-page-contract.md` for Audit Page data;
- `docs/ux/prototype-state-map.md` for screen and transition coverage.

Figma components must be named and structured so they can map to frontend
components without copying old draft frame structure into production.

## 2. Component Contract Fields

Each production component must define:

| Field | Required |
|---|---:|
| Figma component name | yes |
| Component layer | yes |
| Target code path | yes, or `new component required` |
| Props or ViewModel source | yes |
| Required variants | yes |
| Required states | yes |
| Token dependencies | yes |
| Accessibility note | yes for interactive components |
| Responsive behavior | yes for layout/page components |
| Backend/source data | yes for domain components |

## 3. Naming Rules

Figma names use slash-separated component hierarchy:

```text
Base/Button
Layout/TopBar
Domain/TaskNodeCard
Domain/AuditRecordCard
```

Frontend paths use the project layering target:

```text
frontend/src/shared/components/*
frontend/src/shared/components/layout/*
frontend/src/entities/<entity>/ui/*
frontend/src/features/<feature>/ui/*
frontend/src/pages/<page>/*
```

Existing Main Page components may remain in `pages/main-page` during migration.
New reusable components should not be added as page-only one-offs when they
represent shared primitives, layout, or stable domain objects.

## 4. Base Components

Base components are domain-free. They may receive labels, icons, tones, and
state props, but they must not know about Project, Workflow, Session, Task,
Confirmation, Audit, or backend status names.

| Figma component | Target code path | Current status | Core props | Required variants/states |
|---|---|---|---|---|
| `Base/Button` | `frontend/src/shared/components/button/Button.tsx` | exists, extend later | `variant`, `size`, `disabled`, `loading`, `icon`, `children`, `aria-label` | primary, secondary, ghost, danger; sm, md; default, hover, focus-visible, active, disabled, loading |
| `Base/Badge` | `frontend/src/shared/components/badge/Badge.tsx` | exists, extend later | `tone`, `size`, `children` | neutral, info, success, warning, danger; sm, md; default, selected, disabled |
| `Base/Panel` | `frontend/src/shared/components/panel/Panel.tsx` | exists, extend later | `variant`, `padding`, `state`, `children` | surface, muted, selected, warning, danger; default, loading, error, stale |
| `Base/Card` | `frontend/src/shared/components/card/Card.tsx` | new component required | `variant`, `selected`, `interactive`, `children` | surface, selected, warning, danger; default, hover, focus-visible, selected, disabled |
| `Base/List` | `frontend/src/shared/components/list/List.tsx` | new component required | `items`, `selectedId`, `emptyState` | default, selected, loading, empty, error |
| `Base/Text` | `frontend/src/shared/components/text/Text.tsx` | exists | `variant`, `as`, `tone`, `children` | eyebrow, heading, subheading, body, muted, label |
| `Base/Input` | `frontend/src/shared/components/input/Input.tsx` | new component required | `value`, `placeholder`, `disabled`, `error`, `mode` | default, focus-visible, disabled, readonly, error, loading |
| `Base/TextArea` | `frontend/src/shared/components/input/TextArea.tsx` | new component required | `value`, `placeholder`, `disabled`, `error`, `minRows` | default, focus-visible, disabled, readonly, error, auto-grow |
| `Base/IconButton` | `frontend/src/shared/components/button/IconButton.tsx` | new component required | `icon`, `label`, `disabled`, `loading` | default, hover, focus-visible, active, disabled, loading |
| `Base/Tabs` | `frontend/src/shared/components/tabs/Tabs.tsx` | new component required | `items`, `value`, `onChange` | default, selected, disabled, overflow |
| `Base/Tooltip` | `frontend/src/shared/components/tooltip/Tooltip.tsx` | new component required | `content`, `children` | default, delayed-open |
| `Base/Dialog` | `frontend/src/shared/components/dialog/Dialog.tsx` | new component required | `open`, `title`, `description`, `actions` | default, destructive, loading |
| `Base/Drawer` | `frontend/src/shared/components/drawer/Drawer.tsx` | deferred placeholder | pending `open`, `placement`, `title`, `content`, `actions`, dismissal and responsive contract | deferred; do not use for next Domain Components or Main/Audit Screen States |
| `Base/Skeleton` | `frontend/src/shared/components/skeleton/Skeleton.tsx` | new component required | `shape`, `size` | text, block, card, timeline-row |
| `Base/Toast` | `frontend/src/shared/components/toast/Toast.tsx` | new component required | `tone`, `title`, `message`, `action` | info, success, warning, danger |
| `Base/EmptyState` | `frontend/src/shared/components/empty-state/EmptyState.tsx` | new component required | `title`, `message`, `action` | neutral, action-required, error |
| `Base/ErrorState` | `frontend/src/shared/components/error-state/ErrorState.tsx` | spec aligned; new code required | `title`, `message`, `severity`, `retryAction`, `secondaryAction`, `details`, `code` | page, panel, inline; default, retryable, non_retryable, retrying |

Base components must use the token names in `docs/design/design-system.md`.
No production Figma base component is ready until its variants are represented
in `docs/design/component-state-matrix.md`.

### 4.1 Base/Drawer Alignment Decision

`Base/Drawer` is explicitly deferred for the next two phases:

- Domain Components can proceed without Drawer because domain objects should be
  modeled as reusable cards, rows, panels, summaries, and detail sections, not
  as a side-sheet interaction.
- Main/Audit Screen States can proceed without Drawer because the approved
  layout layer already includes `Layout/DetailPanel`,
  `Layout/AuditDetailPanel`, responsive stacking, and page-level shell states.
- Drawer becomes required only if the product chooses drawer-based mobile
  detail, side-sheet navigation, or transient inspector behavior.

Future Drawer alignment must define placement, overlay/backdrop, focus trap,
escape and outside-click dismissal, scroll lock, responsive breakpoints,
return-focus behavior, and whether Drawer is a base primitive or a layout
component. Until then, Figma `Base/Drawer` remains a visible placeholder and
must not be referenced as a production dependency by Domain Components or
screen states.

### 4.2 Base/ErrorState Alignment Decision

`Base/ErrorState` is formalized as a standalone base primitive. It is required
for Domain Components and Main/Audit Screen States because those phases need a
consistent way to render query errors, command errors, permission-denied
fallbacks, stale/resync failures, and audit snapshot/evidence errors.

`Base/ErrorState` is domain-free. It does not own canonical product state. The
owning layout or domain component must pass the relevant error or page-state
fact, such as `AuditPageState.error`, `AuditPageState.permission_denied`,
command `resolve_failed`, or stale/resync failure, and `Base/ErrorState` only
renders the generic error surface.

Required behavior:

- page, panel, and inline variants;
- default, retryable, non_retryable, and retrying states;
- optional primary retry action and secondary action;
- optional safe error code or detail summary;
- no raw backend payload, stack trace, provider payload, full prompt, or
  secret exposure;
- accessible heading, message, and action labels;
- stable minimum content area so error copy does not overlap neighboring
  layout regions.

`Base/EmptyState` may still include an error-toned empty variant for simple
"nothing to show because of a recoverable condition" presentations. Operational
query, command, permission, and audit errors should use `Base/ErrorState`.

## 5. Layout Components

Layout components own structure, density, responsive behavior, and overflow.
They do not own backend facts.

| Figma component | Target code path | Primary source | Required behavior |
|---|---|---|---|
| `Layout/AppShell` | `frontend/src/shared/components/layout/AppShell.tsx` | route model | page frame, min width strategy, mobile stacking |
| `Layout/TopBar` | `frontend/src/shared/components/layout/TopBar.tsx` | route/session/project summaries | product mark, project/workflow/session context, global actions |
| `Layout/WorkflowSidebar` | `frontend/src/shared/components/layout/WorkflowSidebar.tsx` | `WorkflowSummary[]`, `SessionSummary[]` | session list, selected workflow, overflow |
| `Layout/WorkbenchGrid` | `frontend/src/shared/components/layout/WorkbenchGrid.tsx` | page composition | desktop multi-panel layout, tablet collapse |
| `Layout/DetailPanel` | `frontend/src/shared/components/layout/DetailPanel.tsx` | selected object | dynamic inspector region, empty/selected/error |
| `Layout/BottomInputDock` | `frontend/src/shared/components/layout/BottomInputDock.tsx` | input mode | fixed or sticky input, disabled/read-only handling |
| `Layout/AuditShell` | `frontend/src/shared/components/layout/AuditShell.tsx` | `AuditPageSnapshot` | read-only audit frame, return target, responsive timeline/detail |
| `Layout/AuditTimeline` | `frontend/src/shared/components/layout/AuditTimeline.tsx` | `AuditRecord[]` | selected record persistence, scroll, filtered empty |
| `Layout/AuditDetailPanel` | `frontend/src/shared/components/layout/AuditDetailPanel.tsx` | `AuditRecordDetail | null` | record detail, disclosure, evidence, logs link |

Current Main Page layout logic lives mainly in
`frontend/src/pages/main-page/MainPage.tsx` and adjacent files. The target
paths above are architecture targets, not required migration in this task.

## 6. Domain Components

Domain components represent product objects and must receive backend-derived
ViewModels or frontend-local state explicitly. They must not infer canonical
state from labels or colors.

### 6.1 Main Page Domain Components

| Figma component | Target code path | Props/ViewModel source | Backend data source |
|---|---|---|---|
| `Domain/ProjectBreadcrumb` | `frontend/src/entities/project/ui/ProjectBreadcrumb.tsx` | `ProjectSummary`, `WorkflowSummary`, `SessionSummary` | Main Page snapshot summaries |
| `Domain/WorkflowSummaryCard` | `frontend/src/entities/workflow/ui/WorkflowSummaryCard.tsx` | `WorkflowSummary` | Main Page snapshot |
| `Domain/SessionSummaryItem` | `frontend/src/entities/session/ui/SessionSummaryItem.tsx` | `SessionSummary`, selected state | Main Page snapshot |
| `Domain/PlanningStatusBanner` | `frontend/src/features/author-task-tree/ui/PlanningStatusBanner.tsx` | `PlanningView` | RawTask/DraftTaskTree projection |
| `Domain/TaskTree` | `frontend/src/entities/task/ui/TaskTree.tsx` | `TaskTreeView`, selected id | TaskTree ViewModel |
| `Domain/TaskNodeCard` | `frontend/src/entities/task/ui/TaskNodeCard.tsx` | `TaskNodeCardView` | task readiness, execution, confirmation, audit verdict |
| `Domain/TaskNodeInspector` | `frontend/src/entities/task/ui/TaskNodeInspector.tsx` | selected `TaskNodeCardView` | selected task node ViewModel |
| `Domain/SessionMessageRow` | `frontend/src/entities/message/ui/SessionMessageRow.tsx` | `SessionMessageView` | MessageStream projection |
| `Domain/ConfirmationCard` | `frontend/src/features/confirm-action/ui/ConfirmationCard.tsx` | `ConfirmationActionView`, local confirmation status | confirmation projection and command reducer |
| `Domain/ResultCard` | `frontend/src/entities/result/ui/ResultCard.tsx` | `ResultCardView` | result projection |
| `Domain/FileChangeSummary` | `frontend/src/entities/file-change/ui/FileChangeSummary.tsx` | `FileChangeSummaryView` | file-change projection |
| `Domain/AuditSummaryLink` | `frontend/src/entities/audit/ui/AuditSummaryLink.tsx` | `AuditSummaryView` or `AuditLinkView` | audit summary projection |
| `Domain/ContextInput` | `frontend/src/features/context-input/ui/ContextInput.tsx` | input mode, selected context, action availability | route context, permissions, command reducer |

### 6.2 Audit Page Domain Components

| Figma component | Target code path | Props/ViewModel source | Backend data source |
|---|---|---|---|
| `Domain/AuditOverview` | `frontend/src/entities/audit/ui/AuditOverview.tsx` | `AuditOverview` | `AuditPageSnapshot.overview` |
| `Domain/AuditFilterList` | `frontend/src/entities/audit/ui/AuditFilterList.tsx` | `AuditFilterView[]`, active filter | audit snapshot filters |
| `Domain/AuditRecordCard` | `frontend/src/entities/audit/ui/AuditRecordCard.tsx` | `AuditRecord`, selected state | audit records query |
| `Domain/AuditRecordDetail` | `frontend/src/entities/audit/ui/AuditRecordDetail.tsx` | `AuditRecordDetail | null` | selected record detail |
| `Domain/EvidenceRefList` | `frontend/src/entities/audit/ui/EvidenceRefList.tsx` | `EvidenceSummary[]` or `EvidenceRef[]` | evidence summaries/detail endpoint |
| `Domain/EvidenceDisclosure` | `frontend/src/entities/audit/ui/EvidenceDisclosure.tsx` | `AuditDisclosure` | audit record/evidence detail |
| `Domain/EffectiveConfigSummary` | `frontend/src/entities/audit/ui/EffectiveConfigSummary.tsx` | `EffectiveConfigSummary | null` | effective config summary |
| `Domain/RelatedLogsLink` | `frontend/src/entities/audit/ui/RelatedLogsLink.tsx` | `RelatedLogsLink[]`, permissions | diagnostics/log link projection |
| `Domain/AuditReturnTarget` | `frontend/src/entities/audit/ui/AuditReturnTarget.tsx` | `MainPageReturnTarget` | audit entry context |

Audit components are read-only. Any edit, retry, publish, cancel, or
confirmation action belongs on Main Page or a future explicit control surface.

## 7. Canonical Status Mapping

Status badges and controls must preserve separate state dimensions.

| Canonical dimension | Component owner | Allowed UI mapping |
|---|---|---|
| planning state | `PlanningStatusBanner`, `ContextInput`, `TopBar` summary | label/tone/action mode only |
| task readiness | `TaskNodeCard`, `TaskTree`, `TaskNodeInspector` | readiness badge and edit/publish affordances |
| execution status | `TaskNodeCard`, `ResultCard`, progress/message components | execution badge, progress, retry/cancel availability |
| confirmation status | `ConfirmationCard`, `TaskNodeCard` | confirmation badge and action buttons |
| permission/action availability | all interactive domain components | disabled/hidden/pending states with reason |
| audit verdict | `AuditSummaryLink`, `AuditOverview`, `AuditRecordCard` | trust badge/tone; never execution status |

Do not collapse these into one `status` prop. Component props may expose a
single presentation object only after the owning dimension is still present in
the parent ViewModel.

## 8. Audit Contract Mapping

| Audit contract field | Component | Required state coverage |
|---|---|---|
| `AuditPageSnapshot.pageState` | `Layout/AuditShell` | loading, ready, empty, partial, hidden evidence, permission denied, error, stale |
| `AuditOverview.verdict` | `Domain/AuditOverview` | passed, warning, failed, inconclusive, not_available |
| `AuditOverview.completeness` | `Domain/AuditOverview` | not_started, running, partial, complete, failed, hidden |
| `AuditFilterView` | `Domain/AuditFilterList` | enabled, disabled, zero count, selected |
| `AuditRecord.flags` | `Domain/AuditRecordCard` | partial, hidden, redacted, stale, selected |
| `AuditRecordDetail.disclosure` | `Domain/AuditRecordDetail` | raw unavailable, raw hidden, redacted, partial, permission denied |
| `EvidenceRef` / `EvidenceDetail` | `Domain/EvidenceRefList` | available, hidden, redacted, unavailable |
| `AuditPermissions` | `AuditShell`, `RelatedLogsLink`, `EvidenceDisclosure` | readonly, evidence denied, logs denied |

## 9. Figma Creation Readiness

Actual Figma component creation is allowed only when:

1. token dependencies are named in `docs/design/design-system.md`;
2. component appears in this spec;
3. all states and variants are in `docs/design/component-state-matrix.md`;
4. screen/prototype usage is mapped in `docs/ux/prototype-state-map.md`;
5. code path is either existing or marked `new component required`;
6. backend/ViewModel source is named for domain components;
7. the component is recreated canonically, not migrated by copying old Figma
   draft content.

## 10. Acceptance Criteria

- Every required Base, Layout, Main Page domain, and Audit Page domain
  component has a Figma name and code path target.
- Component props map to ViewModels or local UI state, not raw backend objects.
- Canonical status dimensions remain separated.
- Audit Page components map to the Audit Page contract and remain read-only.
- This document can be used by the Figma governance gate to allow the next
  token/component creation task, while still blocking dev handoff until Figma
  components and prototype flows exist.
