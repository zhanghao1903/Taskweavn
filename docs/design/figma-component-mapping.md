# Plato Figma Component Mapping

> Status: base, layout, domain, screen-state, prototype-flow, and Dev Handoff
> mapping
> Last Updated: 2026-05-25
> Scope: Figma-to-code mapping for governed base component skeletons,
> layout/domain visual drafts, Main Page screen states, Audit Page screen
> states, prototype flow references, and Dev Handoff sections in the canonical
> Figma file.

## 1. Source And Status

Canonical Figma file:
<https://www.figma.com/design/CTK1yALdNEFo2zL8ZcEJIA>

Target pages:

- `03 - Base Components`
- `04 - Layout Components`
- `05 - Domain Components`
- `06 - Main UX Flow`
- `07 - Main Screen States`
- `08 - Audit UX Flow`
- `09 - Audit Screen States`
- `10 - Prototype Flows`
- `11 - Dev Handoff`

Run markers:

- base components: `plato-base-components-2026-05-24-batched`
- layout components: `plato-layout-components-2026-05-24-batched`
- domain components: `plato-domain-components-2026-05-24-batched`
- Main screen states: `plato-main-screen-states-2026-05-24-batched`
- Audit screen states: `plato-audit-screen-states-2026-05-24-batched`
- Prototype flows: `plato-prototype-flows-2026-05-24-batched`
- Dev Handoff: `plato-dev-handoff-2026-05-24-batched`
- Handoff hygiene: `plato-handoff-hygiene-2026-05-25`
- layout visual upgrade: `plato-layout-visual-upgrade-2026-05-25`
- domain visual upgrade: `plato-domain-visual-upgrade-2026-05-25`
- domain overlap/bounds fix: `plato-domain-overlap-and-bounds-fix-2026-05-25`
- domain page-level overlap fix: `plato-domain-page-overlap-fix-2026-05-25`
- domain variant root zero-origin fix: `plato-domain-variant-root-zero-origin-fix-2026-05-25`
- domain TaskTree visual refinement: `plato-domain-tasktree-visual-refinement-2026-05-25`
- domain TaskTree height fix: `plato-domain-tasktree-height-fix-2026-05-25`
- P4 04/05 acceptance recorded: 2026-05-26 CST
- Main screen state recomposition: `plato-main-screen-state-recomposition-2026-05-26`

This mapping documents governed Figma artifacts and their handoff mappings.
It is an input to P5 frontend architecture. It does not mark frontend
implementation complete.
The 2026-05-26 P4 acceptance confirms that component mapping remains valid for
`04 - Layout Components` and `05 - Domain Components` within their accepted
reference/skeleton scopes.

Source docs:

- `docs/design/design-system.md`
- `docs/design/component-spec.md`
- `docs/design/component-state-matrix.md`
- `docs/design/figma-file-registry.md`
- `docs/design/figma-readiness-checklist.md`
- `docs/engineering/audit-page-contract.md`
- `docs/product/canonical-status-model.md`
- `docs/ux/screen-state-spec.md`
- `docs/ux/prototype-state-map.md`

## 2. Naming Decisions

| Decision | Canonical choice | Notes |
|---|---|---|
| Text area spelling | `Base/TextArea` | Matches `TextArea.tsx` and existing docs. `Base/Textarea` is treated as a search alias only. |
| Loading skeleton naming | `Base/Skeleton` | Covers requested `LoadingSkeleton`. A future code wrapper may be named `LoadingSkeleton`, but the base Figma component remains `Base/Skeleton`. |
| Drawer status | `Base/Drawer` deferred placeholder | Explicitly deferred for Domain Components and Main/Audit Screen States because current flows use panel/stacked detail instead of drawer-based interaction. |
| Error state status | `Base/ErrorState` formalized | Standalone base primitive for page, panel, and inline query/command/permission/stale errors. Existing Figma note/metadata is synced to this decision. |
| Side navigation naming | `Layout/SideNav` | User-facing Figma name. Maps to the spec concept `Layout/WorkflowSidebar`. |
| Main work area naming | `Layout/MainWorkArea` | User-facing Figma name. Maps to the spec concept `Layout/WorkbenchGrid`. |
| Context input naming | `Layout/ContextInputBar` | User-facing Figma name. Maps to the spec concept `Layout/BottomInputDock`. |
| Task node naming | `Domain/TaskNode` | User-facing Figma name. Maps to the spec concept `Domain/TaskNodeCard`. |
| Message stream naming | `Domain/MessageStream` | User-facing Figma name for the message collection composition around `Domain/SessionMessageRow`. |
| Message card naming | `Domain/MessageCard` | User-facing Figma name. Maps to the spec concept `Domain/SessionMessageRow`. |
| Confirmation naming | `Domain/ConfirmationPanel` | User-facing Figma name. Maps to the spec concept `Domain/ConfirmationCard`. |
| File change naming | `Domain/FileChangeTable` | User-facing Figma name. Maps to `Domain/FileChangeSummary` plus audit file-change evidence rows. |
| Audit entry naming | `Domain/AuditEntryCard` | User-facing Figma name. Maps to `Domain/AuditRecordCard` or `Domain/AuditSummaryLink` depending usage context. |

## 3. Base Component Mapping

| Figma component | Node ID | Variant axes | Covered states | Code component path | Canonical prop mapping | Readiness | Pending blockers |
|---|---|---|---|---|---|---|---|
| `Base/Button` | `28:46` | `variant`: primary, secondary, ghost, danger | default, hover, focus, disabled, loading | `frontend/src/shared/components/button/Button.tsx` | `variant`, `size`, `disabled`, `loading`, `icon`, `children`, `aria-label` | skeleton stabilized | `sm/md`, active, icon slot, component props not represented in skeleton |
| `Base/Badge` | `28:84` | `tone`: neutral, info, success, warning, danger | default, selected, disabled | `frontend/src/shared/components/badge/Badge.tsx` | `tone`, `size`, `children` | skeleton stabilized | `sm/md` and final text/content property wiring deferred |
| `Base/Input` | `30:14` | state-only skeleton | default, focus, disabled, error, loading | `frontend/src/shared/components/input/Input.tsx` | `value`, `placeholder`, `disabled`, `error`, `mode` | skeleton stabilized | `text/command`, hover, readonly, validation message props deferred |
| `Base/TextArea` | `30:35` | state-only skeleton | default, focus, disabled, error | `frontend/src/shared/components/input/TextArea.tsx` | `value`, `placeholder`, `disabled`, `error`, `minRows` | skeleton stabilized | compact/expanded, readonly, auto-grow behavior deferred |
| `Base/Card` | `30:79` | `variant`: surface, selected, warning, danger | default, selected, disabled | `frontend/src/shared/components/card/Card.tsx` | `variant`, `selected`, `interactive`, `children` | skeleton stabilized | hover, focus-visible, interactive prop, content slots deferred |
| `Base/Panel` | `30:157` | `variant`: surface, muted, selected, warning, danger | default, loading, error, stale, readonly | `frontend/src/shared/components/panel/Panel.tsx` | `variant`, `padding`, `state`, `children` | skeleton stabilized | padding variants and final child slots deferred |
| `Base/Dialog` | `32:20` | `variant`: normal, destructive | default, loading, error | `frontend/src/shared/components/dialog/Dialog.tsx` | `open`, `title`, `description`, `actions` | skeleton stabilized | focus trap, action slots, modal overlay behavior deferred |
| `Base/Drawer` | `32:37` | deferred placeholder | deferred | `frontend/src/shared/components/drawer/Drawer.tsx` pending | pending `open`, placement, title, content, actions, focus, scroll lock, dismissal decision | deferred | Not required for Domain Components or Main/Audit Screen States; formalize only if drawer-based mobile detail, side-sheet navigation, or transient inspector behavior is approved |
| `Base/Toast` | `32:81` | `tone`: info, success, warning, danger | default, action, dismissing | `frontend/src/shared/components/toast/Toast.tsx` | `tone`, `title`, `message`, `action` | skeleton stabilized | global stack positioning, timeout behavior, action props deferred |
| `Base/Tooltip` | `32:93` | state-only skeleton | default, delayed-open | `frontend/src/shared/components/tooltip/Tooltip.tsx` | `content`, `children` | skeleton stabilized | placement, arrow, trigger timing, accessibility wiring deferred |
| `Base/EmptyState` | `34:11` | `variant`: neutral, action-required, error | empty, error | `frontend/src/shared/components/empty-state/EmptyState.tsx` | `title`, `message`, `action` | skeleton stabilized | compact variant, final action slot, illustration slot deferred |
| `Base/ErrorState` | `34:25` | `variant`: page, panel, inline | default, retryable, non_retryable, retrying | `frontend/src/shared/components/error-state/ErrorState.tsx` | `title`, `message`, `severity`, `retryAction`, `secondaryAction`, `details`, `code` | formalized skeleton | Screen-state mappings, implementation mapping, and final visual polish deferred |
| `Base/Skeleton` | `34:50` | `shape`: text, block, card, timeline-row | loading | `frontend/src/shared/components/skeleton/Skeleton.tsx` | `shape`, `size` | skeleton stabilized | Requested `LoadingSkeleton` is an alias; final shimmer/motion behavior deferred |

## 4. Layout Component Mapping

| Figma component | Node ID | Variant axes | Covered states | Code component path | Canonical prop mapping | Base components reused | Readiness | Pending blockers |
|---|---|---|---|---|---|---|---|---|
| `Layout/AppShell` | `45:24` | `variant`: main; `state`: ready, loading, stale, error | desktop workbench shell, loading shell, stale shell, error shell | `frontend/src/shared/components/layout/AppShell.tsx` | `route`, `pageState`, `navigation`, `mainSlot`, `detailSlot`, `contextInputSlot`, `stale`, `error` | `Base/Panel`, `Base/Skeleton`, `Base/ErrorState`, `Base/Badge` | visual baseline aligned draft | audit-specific shell, tablet/mobile concrete variants, final route chrome deferred |
| `Layout/TopBar` | `45:52` | `variant`: main; `state`: default, loading, readonly, stale | project/workflow/session title area, status badges, loading, readonly, stale indicator | `frontend/src/shared/components/layout/TopBar.tsx` | `productMark`, `project`, `workflow`, `session`, `actions`, `readonly`, `stale`, `busy` | `Base/Button`, `Base/Badge`, `Base/Skeleton` | visual baseline aligned draft | final product mark binding, audit-return context, responsive overflow deferred |
| `Layout/SideNav` | `46:43` | `state`: expanded, collapsed, selectedItem, disabledItem, empty, loading | workflow/session hierarchy, selected item, disabled item, empty, loading | `frontend/src/shared/components/layout/WorkflowSidebar.tsx` or future `SideNav.tsx` alias | `items`, `selectedId`, `collapsed`, `disabledItemIds`, `emptyState`, `loading`, `onSelect` | `Base/Button`, `Base/Badge`, `Base/EmptyState`, `Base/Skeleton` | visual baseline aligned draft | 5 obsolete skeleton variants are hidden/archived; workflow/session hierarchy slot typing and frontend naming decision remain |
| `Layout/MainWorkArea` | `46:76` | `state`: ready, loading, empty, error, splitPanel, stale | dense workbench grid, loading, empty, error, split-panel, stale content | `frontend/src/shared/components/layout/WorkbenchGrid.tsx` or future `MainWorkArea.tsx` alias | `mode`, `pageState`, `primarySlot`, `secondarySlot`, `emptyState`, `error`, `stale`, `scrollBehavior` | `Base/Panel`, `Base/Badge`, `Base/Skeleton`, `Base/EmptyState`, `Base/ErrorState` | visual baseline aligned draft | 5 obsolete skeleton variants are hidden/archived; exact grid semantics, scroll behavior, and responsive stacking remain P5 work |
| `Layout/DetailPanel` | `48:72` | `state`: empty, selectedTask, sessionWorkflow, result, auditEntry, loading, error, stale, permissionDenied, readonly | task, session/workflow, result, audit entry, loading, error, stale, permission denied, readonly | `frontend/src/shared/components/layout/DetailPanel.tsx` | `selectedEntity`, `detailKind`, `pageState`, `permission`, `readonly`, `error`, `stale`, `evidenceLinks` | `Base/Panel`, `Base/Badge`, `Base/Skeleton`, `Base/EmptyState`, `Base/ErrorState` | visual baseline aligned draft | 6 obsolete skeleton variants are hidden/archived; final detail slot typing and route-specific copy remain |
| `Layout/ContextInputBar` | `48:134` | `state`: goalInput, taskInstruction, clarificationAnswer, confirmationResponse, disabledReadonly, loadingSubmitting, error | goal input, task instruction, clarification answer, confirmation response, disabled/readonly, submitting, error | `frontend/src/shared/components/layout/BottomInputDock.tsx` or future `ContextInputBar.tsx` alias | `inputMode`, `value`, `placeholder`, `disabled`, `readonly`, `submitting`, `error`, `actions`, `onSubmit` | `Base/Input`, `Base/TextArea`, `Base/Button`, `Base/Badge`, `Base/Skeleton`, `Base/ErrorState` | visual baseline aligned draft | 7 obsolete skeleton variants are hidden/archived; reducer wiring, keyboard shortcuts, mobile dock behavior, frontend naming decision remain |

## 5. Domain Component Mapping

| Figma component | Node ID | Variant axes | Covered states | Code component path | Canonical prop/ViewModel mapping | Base/layout reused | Readiness | Pending blockers |
|---|---|---|---|---|---|---|---|---|
| `Domain/TaskTree` | `58:55` | `state`: default, loading, empty, error, readonly, permissionLimited, selectedNode | default, loading, empty, error, readonly, permission-limited, selected node, nested hierarchy note, S7-style card-row hierarchy | `src/features/task-tree/components/TaskTree.tsx`; spec equivalent `frontend/src/entities/task/ui/TaskTree.tsx` | `TaskTreeView.readiness`, execution rollup, selected id, permission/action availability | `Base/Badge`, `Base/Card`, `Base/EmptyState`, `Base/ErrorState`, `Base/Skeleton` | visual baseline aligned draft; TaskTree static-baseline refinement applied | final data slots, keyboard navigation, implementation path decision |
| `Domain/TaskNode` | `58:203` | `status`: ready, suggested, running, waiting, completed, failed; `state`: default, hover, focus, selected, editing, disabled, permissionDenied | requested status and interaction states | `src/features/task-tree/components/TaskNode.tsx`; spec equivalent `frontend/src/entities/task/ui/TaskNodeCard.tsx` | task readiness, execution status, confirmation status, audit verdict, permissions, `ActionAvailabilityView` | `Base/Badge`, `Base/Card` | visual baseline aligned draft | final status presentation names, edit affordance, action slots, exact code path |
| `Domain/MessageStream` | `59:113` | `state`: empty, loading, streaming, error, partialData, hiddenEvidenceNote | empty, loading, streaming, error, partial data, hidden evidence note, scroll note | `src/features/session/components/MessageStream.tsx`; spec equivalent message stream composition around `Domain/SessionMessageRow` | message stream projection, event reducer streaming/partial/stale behavior, hidden/redacted evidence disclosure | `Base/Badge`, `Base/Card`, `Base/EmptyState`, `Base/ErrorState`, `Base/Skeleton` | visual baseline aligned draft | final virtualization/scroll behavior, event reducer wiring |
| `Domain/MessageCard` | `59:201` | `type`: info, userRequest, assistantResponse, result, warning, error; `display`: compact, expanded | all requested tone/type variants and display variants | `src/features/session/components/MessageCard.tsx`; spec equivalent `frontend/src/entities/message/ui/SessionMessageRow.tsx` | `SessionMessageView` actor/type, local streaming/partial/error display facts | `Base/Badge`, `Base/Card`, `Base/ErrorState` | visual baseline aligned draft | final message content slots, markdown/code handling, streaming cursor |
| `Domain/ConfirmationPanel` | `60:333` | `risk`: low, medium, high; `state`: pending, resolving, confirmed, skipped, rejected, expired, stale, permissionDenied, conflict | risk variants and confirmation lifecycle states | `src/features/confirmation/components/ConfirmationPanel.tsx`; spec equivalent `frontend/src/features/confirm-action/ui/ConfirmationCard.tsx` | backend confirmation status, local command overlay, decision outcome, action availability, audit/risk signals | `Base/Button`, `Base/Badge`, `Base/Panel`, `Base/Skeleton`, `Base/ErrorState` | visual baseline aligned draft | exact outcome value model, conflict retry behavior, action copy |
| `Domain/FileChangeTable` | `61:316` | `state`: empty, loading, partial, hiddenEvidence, permissionDenied, added, modified, deleted, riskyChange | file-change and evidence disclosure states | `src/features/audit/components/FileChangeTable.tsx`; spec equivalent `frontend/src/entities/file-change/ui/FileChangeSummary.tsx` plus audit file evidence rows | `FileChangeSummaryView`, `AuditRecord.kind=file_change`, `EvidenceRef`, `AuditPermissions` | `Base/Badge`, `Base/Panel`, `Base/EmptyState`, `Base/ErrorState`, `Base/Skeleton` | visual baseline aligned draft | table density, path truncation, evidence-link behavior |
| `Domain/AuditEntryCard` | `61:409` | `state`: passed, warning, failed, inconclusive, notAvailable, expanded, hiddenEvidence, permissionDenied, staleSnapshot | audit verdict and display/disclosure states | `src/features/audit/components/AuditEntryCard.tsx`; spec equivalent `Domain/AuditRecordCard` or `Domain/AuditSummaryLink` | `AuditVerdict`, `AuditRecord.flags`, `AuditPermissions`, `audit.snapshot_stale` | `Base/Badge`, `Base/Card`, `Base/ErrorState`, `Base/Skeleton` | visual baseline aligned draft | final compact/expanded API, selected state, route/deep-link behavior |

## 6. Stabilization Notes

The base component page was stabilized on 2026-05-24:

- existing component set node IDs were preserved;
- notes were moved next to corresponding component sets;
- no new component variants were invented;
- no old Figma content was migrated;
- `Base/Drawer` remains visible but deferred for production use until drawer
  interaction behavior is selected.
- `Base/ErrorState` is now formalized in docs as a standalone base primitive;
  its visible Figma note/metadata was synced on 2026-05-24 with run marker
  `plato-base-spec-status-sync-2026-05-24`.

The layout component page was created and verified on 2026-05-24:

- all six requested layout component sets were created on
  `04 - Layout Components`;
- existing base components are reused as instances where applicable;
- notes were created next to each component set;
- `Layout/SideNav`, `Layout/MainWorkArea`, and `Layout/ContextInputBar`
  explicitly document their equivalent spec concepts;
- no domain components, screen states, prototype interactions, or frontend
  implementation files were created.

The domain component page was created and verified on 2026-05-24:

- all seven requested domain component sets were created on
  `05 - Domain Components`;
- existing base components are reused as instances where applicable;
- `Base/ErrorState` is used for error/permission surfaces;
- `Base/Drawer` is not used;
- notes were created next to each component set;
- user-facing Figma names that differ from current component-spec names are
  documented as aliases;
- at domain-component creation time, screen states, prototype interactions,
  and frontend implementation files were out of scope.

The domain component page was visually upgraded on 2026-05-25:

- all seven domain component set node IDs were preserved;
- skeleton-only placeholders were replaced with product-real sample content
  from `docs/design/domain-components-visual-upgrade-brief.md`;
- permission, hidden evidence, partial evidence, stale, confirmation, file
  change, and audit verdict states remain semantically separate;
- post-write effective-visible verification reported zero text overlaps, zero
  clipping, zero page-level set/note overlap pairs, and all visible descendants
  contained by component/note bounds;
- follow-up page-level verification included all 16 visible top-level siblings
  on `05 - Domain Components` and fixed stale title/hygiene note overlap with
  the `Domain/TaskTree` gallery;
- variant root normalization removed `14,14` root offsets by forcing visible
  `P4.12 visual draft` root frames to `x=0, y=0` inside fixed-layout variants;
- `Domain/TaskTree` was refined with
  `plato-domain-tasktree-visual-refinement-2026-05-25` to match the S7 static
  visual baseline more closely: compact card rows, indentation rhythm, connector
  markers, status pills, selected-node treatment, and state-specific
  loading/empty/error/read-only previews;
- `plato-domain-tasktree-height-fix-2026-05-25` fixed loading/empty/error
  variant overflow while preserving component set node ID `58:55`;
- representative exports passed for `Domain/TaskTree`,
  `Domain/ConfirmationPanel`, `Domain/FileChangeTable`, and
  `Domain/AuditEntryCard`.

Handoff hygiene was completed on 2026-05-25:

- Base, Layout, and Domain component galleries were reflowed into readable
  grids where long variant rows previously overflowed horizontally;
- note frames were kept adjacent to their component sets;
- component set node IDs, variant counts, token bindings, and semantic
  mappings were preserved;
- visible hygiene notes clarify that placeholder labels are not production
  copy.

## 7. Main Screen State Mapping

The Main UX flow map and Main screen state frames were created and verified on
2026-05-24 with run marker `plato-main-screen-states-2026-05-24-batched`.
The screen state frames were recomposed on 2026-05-26 with run marker
`plato-main-screen-state-recomposition-2026-05-26` using the accepted
`04 - Layout Components`, accepted `05 - Domain Components`, and upgraded
`06 - Main UX Flow` overview. They are product-aligned P4 references only:
not prototype-wired and not frontend-implemented.

Flow map:

| Figma element | Node ID | Purpose | Readiness |
|---|---|---|---|
| `Main UX Flow Overview / P4.9` | `292:2` | readable Main Page UX flow overview with happy path, recovery/negative path, and Main-to-Audit entry/return context | created, no prototype interactions |
| `State Inventory / Governed S1-S13 (preserved)` | `69:2` | preserved Main Page state inventory storyboard | preserved, no prototype interactions |

Screen state frames:

| Figma frame | Node ID | Canonical state mapping | Primary component reuse | Backend/ViewModel dimensions represented | Readiness |
|---|---|---|---|---|---|
| `S1 - Empty New Session` | `71:2` | `prototype-state-map S1 Empty` | `Layout/AppShell`, `Layout/TopBar`, `Layout/SideNav`, `Layout/MainWorkArea`, `Layout/DetailPanel`, `Layout/ContextInputBar`, `Domain/MessageStream`, `Base/EmptyState`, `Base/Input`, `Base/Button` | planning `empty`, execution `not_started`, confirmation none, can create goal, audit `not_available` | recomposed product-aligned reference |
| `S2 - Understanding / Planning` | `71:110` | `prototype-state-map S2 Understanding` | layout shell, `Domain/MessageStream`, `Domain/TaskTree`, `Base/Skeleton`, `Base/Badge` | planning `capturing_input` or `assessing`, execution `not_started`, limited planning actions | recomposed product-aligned reference |
| `S3 - Draft Task Tree Ready` | `71:217` | user label mapped to `prototype-state-map S4 Draft Ready` | layout shell, `Domain/TaskTree`, `Domain/TaskNode`, `Domain/MessageCard`, `Base/Badge`, `Base/Button` | planning `draft_ready`, readiness `draft` or `accepted`, can edit/publish when valid | recomposed product-aligned reference |
| `S4 - Task Node Selected` | `73:216` | user label mapped to `prototype-state-map S5 Task Selected` | layout shell, `Domain/TaskTree`, `Domain/TaskNode`, `Domain/MessageStream`, `Base/Badge`, `Base/Panel` | selected task id, readiness/execution/confirmation/audit dimensions for selected node | recomposed product-aligned reference |
| `S5 - Task Node Editing` | `73:334` | user label mapped to `prototype-state-map S6 Task Editing` | layout shell, `Domain/TaskTree`, `Domain/TaskNode`, `Base/TextArea`, `Base/Input`, `Base/Button` | planning `draft_ready`, readiness `draft`, local edit buffer, can edit/append guidance | recomposed product-aligned reference |
| `S6 - Published / Running` | `73:450` | user combined state mapped to `prototype-state-map S7 Published/Pending` plus `S8 Running` | layout shell, `Domain/TaskTree`, `Domain/TaskNode`, `Domain/MessageStream`, `Base/Skeleton`, `Base/Badge` | planning `published`, readiness `published`, execution `pending` or `running`, edit disabled | recomposed product-aligned reference |
| `S7 - Waiting For Confirmation` | `75:432` | user label mapped to `prototype-state-map S9 Waiting Confirmation` | layout shell, `Domain/ConfirmationPanel`, `Domain/TaskNode`, `Domain/MessageCard`, `Base/Button`, `Base/Badge` | confirmation `pending`, local `resolving`/`resolve_failed`, can resolve confirmation | recomposed product-aligned reference |
| `S8 - Completed With Result` | `75:563` | user label mapped to `prototype-state-map S10 Completed` | layout shell, `Domain/MessageCard`, `Domain/FileChangeTable`, `Domain/AuditEntryCard`, `Domain/TaskNode`, `Base/Badge` | execution `done`, confirmation resolved/none, audit verdict separate from execution | recomposed product-aligned reference |
| `S9 - File Change Summary / Audit Entry` | `75:686` | focused `completed-with-result-file-audit` Main Page state | layout shell, `Domain/FileChangeTable`, `Domain/AuditEntryCard`, `Domain/MessageCard`, `Base/Badge`, `Base/Panel` | result/file summary, audit entry route context, evidence visibility and permissions | recomposed product-aligned reference |
| `S10 - Permission Denied` | `77:659` | permission-denied-readonly scenario | layout shell, `Base/ErrorState`, `Domain/TaskTree`, `Domain/TaskNode`, `Base/Badge`, `Base/Button` | permission/action availability and `readonlyReason` independent from status | recomposed product-aligned reference |
| `S11 - Stale Snapshot / Resync Required` | `77:775` | user label mapped to `prototype-state-map S12 Stale/Resync` | layout shell, `Base/ErrorState`, `Base/Skeleton`, `Domain/MessageStream`, `Domain/TaskTree`, `Base/Badge` | stale snapshot, last-known state retained, high-risk actions disabled | recomposed product-aligned reference |
| `S12 - Backend Busy / Command Accepted But Delayed` | `77:883` | command accepted / `pending_command` overlay | layout shell, `Base/Skeleton`, `Domain/MessageStream`, `Domain/TaskNode`, `Base/Badge`, `Base/Button` | last-known state plus local pending command, duplicate command disabled | recomposed product-aligned reference |
| `S13 - Command Failed / Recoverable Error` | `77:986` | recoverable command failure related to `S13 Load Error` | layout shell, `Base/ErrorState`, `Domain/MessageStream`, `Domain/MessageCard`, `Base/Button`, `Base/Badge` | command error envelope, retry eligibility, last safe snapshot retained | recomposed product-aligned reference |

State frame metadata:

- each frame contains visible fields for trigger, planning state, task
  readiness, execution status, confirmation status, permission/action
  availability, audit verdict, required data, visible components, actions,
  disabled states, exit condition, behavior, source docs, and readiness;
- state frames are stabilized at 1440x1080 and placed without overlap;
- Audit Page state work, prototype interactions, old-file migration, frontend
  code, and dev handoff annotations were out of scope for this Main-specific
  task.

## 8. Audit Screen State Mapping

The Audit UX flow map and Audit screen state frames were created and verified
on 2026-05-24 with run marker
`plato-audit-screen-states-2026-05-24-batched`. These frames are governed
skeletons only. They are not prototype-wired and do not mark frontend
implementation complete.

Flow map:

| Figma element | Node ID | Purpose | Readiness |
|---|---|---|---|
| `Audit UX Flow Map / Governed States` | `89:2` | Audit Page state storyboard and transition intent | created, no prototype interactions |

Screen state frames:

| Figma frame | Node ID | Canonical state mapping | Primary component reuse | Audit dimensions represented | Readiness |
|---|---|---|---|---|---|
| `A1 - Audit Empty` | `91:2` | `pageState.empty`; related to `prototype-state-map A5 Empty Audit` | `Layout/AppShell`, `Layout/TopBar`, `Layout/SideNav`, `Layout/MainWorkArea`, `Layout/DetailPanel`, `Base/EmptyState`, `Base/Badge`, `Base/Button`, `Base/Panel` | verdict `not_available`, evidence none, current snapshot, ready-empty query | governed skeleton |
| `A2 - Audit Loading` | `91:93` | `pageState.loading` | layout shell, `Base/Skeleton`, `Base/Badge`, `Base/Button` | pending permission/evidence, unknown freshness, loading query | governed skeleton |
| `A3 - Audit Records Ready` | `91:165` | `pageState.ready`; records list | layout shell, `Domain/AuditEntryCard`, `Domain/FileChangeTable`, `Base/Badge`, `Base/Button`, `Base/Panel` | aggregate verdict, permitted evidence by record, current snapshot, ready query | governed skeleton |
| `A4 - Audit Record Selected` | `93:149` | selected `AuditRecordDetail`; related to `prototype-state-map A2 Record Selected` | layout shell, `Domain/AuditEntryCard`, `Domain/FileChangeTable`, `Domain/MessageCard`, `Base/Badge`, `Base/Button`, `Base/Panel` | selected record verdict, detail/evidence permissions, current snapshot | governed skeleton |
| `A5 - Partial Evidence` | `93:248` | `pageState.partial`; `AuditRecord.flags.partial` | layout shell, `Domain/AuditEntryCard`, `Domain/FileChangeTable`, `Base/Badge`, `Base/Button`, `Base/Panel` | warning/inconclusive signal, partial evidence, current snapshot | governed skeleton |
| `A6 - Hidden Evidence / Permission Limited` | `93:344` | `pageState.hidden_evidence`; hidden/redacted `EvidenceRef` | layout shell, `Domain/AuditEntryCard`, `Domain/FileChangeTable`, `Base/Badge`, `Base/Button`, `Base/Panel` | verdict preserved, limited evidence permission, hidden/redacted evidence | governed skeleton |
| `A7 - Warning Verdict` | `95:313` | `AuditVerdict.warning` | layout shell, `Domain/AuditEntryCard`, `Domain/FileChangeTable`, `Base/Badge`, `Base/Button`, `Base/Panel` | warning verdict, available/partial evidence, current snapshot | governed skeleton |
| `A8 - Failed Verdict` | `95:410` | `AuditVerdict.failed` | layout shell, `Domain/AuditEntryCard`, `Domain/FileChangeTable`, `Base/Badge`, `Base/Button`, `Base/Panel` | failed verdict, evidence refs, read-only audit actions | governed skeleton |
| `A9 - Inconclusive Verdict` | `95:507` | `AuditVerdict.inconclusive`; related to `prototype-state-map A8 Inconclusive` | layout shell, `Domain/AuditEntryCard`, `Domain/FileChangeTable`, `Domain/MessageCard`, `Base/Badge`, `Base/Panel` | inconclusive verdict, insufficient/conflicting evidence | governed skeleton |
| `A10 - Not Available Verdict` | `95:601` | `AuditVerdict.not_available` | layout shell, `Domain/AuditEntryCard` or `Base/EmptyState`, `Base/Badge`, `Base/Button`, `Base/Panel` | not available verdict, no applicable evidence, current snapshot | governed skeleton |
| `A11 - Permission Denied` | `98:527` | `pageState.permission_denied`; `canViewAudit=false` | layout shell, `Base/ErrorState`, `Base/Badge`, `Base/Button`, `Base/Panel` | not available verdict, audit-view permission denied, no evidence visible | governed skeleton |
| `A12 - Stale Snapshot / Records Changed` | `98:613` | `audit.snapshot_stale`, `audit.records_changed`, `pageState.stale` | layout shell, `Domain/AuditEntryCard`, `Domain/FileChangeTable`, `Base/ErrorState`, `Base/Badge`, `Base/Button`, `Base/Panel` | verdict preserved until refresh, stale freshness, refresh-only actions | governed skeleton |
| `A13 - Audit Query Error` | `98:977` | `AuditPageSnapshot` query failure; `pageState.error` | layout shell, `Base/ErrorState`, `Base/Badge`, `Base/Button`, `Base/Panel` | not available verdict, evidence not loaded, unknown freshness, query error | governed skeleton |
| `A14 - Evidence Load Error` | `98:1040` | `EvidenceDetail` query failure while snapshot remains ready | layout shell, `Domain/AuditEntryCard`, `Domain/FileChangeTable`, `Base/ErrorState`, `Base/Badge`, `Base/Button`, `Base/Panel` | record verdict preserved, evidence detail error, current snapshot | governed skeleton |

State frame metadata:

- each frame contains visible fields for trigger, entry context, audit scope,
  audit verdict, permission/action availability, evidence visibility, snapshot
  freshness, query/loading/error state, required data, visible components,
  actions, disabled states, exit condition, behavior, source docs, and
  readiness;
- state frames are stabilized at 1440x1120 and placed without overlap;
- `Base/Drawer` is not used;
- screenshot verification passed for `A3 - Audit Records Ready` at 1600x892;
- no old-file migration, frontend code, or dev handoff annotations were
  created.

## 9. Prototype Flow Mapping

The Prototype Flow references were created and verified on 2026-05-24 with run
marker `plato-prototype-flows-2026-05-24-batched`. These frames are governed
interaction references only. They do not mark the canonical Figma file as
frontend implementation complete.

Prototype flow title:

| Figma element | Node ID | Purpose | Readiness |
|---|---|---|---|
| `Prototype Flows / Governed Interaction References` | `124:2` | Page title and governance rules for transition references | created, not dev handoff |

Prototype flow references:

| Figma frame | Node ID | State frames linked/referenced | Route/return context represented | Recovery path represented | Readiness |
|---|---|---|---|---|---|
| `Flow 1 - Main happy path` | `124:6` | `S1` -> `S9` | Main route with project/workflow/session and selected task/query context | branches to Flow 2 on stale/load/permission/command issue | governed reference |
| `Flow 2 - Main recovery / negative path` | `124:71` | `S10` -> `S13` | same Main route with selected context preserved | permission fallback, stale resync, backend busy wait, command retry | governed reference |
| `Flow 3 - Main to Audit entry` | `128:2` | `S8`, `S9`, `S4`, `S7` -> `A2`/`A3`/`A4` | Audit route carries `sessionId`, optional `taskNodeId`, `recordId`, `entryContext`, and `MainPageReturnTarget` | query failure -> `A13`, denied -> `A11`, return handled by Flow 7 | governed reference |
| `Flow 4 - Audit happy path` | `128:69` | `A1` -> `A4` | Audit route remains read-only and retains return target | empty stays `A1`, query error -> `A13`, stale -> `A12` | governed reference |
| `Flow 5 - Audit evidence / verdict path` | `130:2` | `A4` -> `A5`/`A6`/`A7`/`A8`/`A9`/`A10` | same Audit route with `recordId`/`filter` preserved | evidence error -> `A14`, denied -> `A11`, stale -> `A12` | governed reference |
| `Flow 6 - Audit recovery / negative path` | `130:62` | `A11`, `A12`, `A13`, `A14` | Audit route preserves scope, entry context, and return target during recovery | `A12` refreshes snapshot, `A13` retries snapshot query, `A14` retries evidence detail only | governed reference |
| `Flow 7 - Return paths` | `130:124` | Audit states -> `S8`, `S9`, `S4`, `S7`, `S13`, or previous valid Audit state | `returnTarget=session|task|confirmation|result|fileChange` plus selected IDs | stale refresh -> `A2`/`A3`, query failure may return to Main recovery | governed reference |

Prototype flow metadata:

- each flow contains visible metadata for flow ID, flow name, entry state, exit
  state, trigger, user action, backend/API dependency, route context, recovery
  behavior, related source docs, and readiness;
- Main to Audit entry preserves return context;
- stale snapshot recovery is separate from generic query/evidence retry;
- permission denied has explicit fallback/return behavior;
- hidden evidence remains permission-limited, not missing data;
- `A3 - Audit Records Ready` covers passed/default audit entries;
- screenshot verification passed for the prototype flow title frame at
  1600x219.

## 10. Dev Handoff Mapping

The Dev Handoff mapping was created and verified on 2026-05-24 with run marker
`plato-dev-handoff-2026-05-24-batched`. These sections bridge governed Figma
artifacts into P5 frontend architecture. They do not implement frontend code.

| Handoff section | Node ID | Mapping coverage |
|---|---|---|
| `Dev Handoff / Overview` | `136:2` | source docs, canonical file, readiness scope, not-ready scope, usage rules |
| `Dev Handoff / Token-to-Code Mapping` | `136:7` | Figma tokens to CSS/theme token candidates |
| `Dev Handoff / Component-to-Code Mapping` | `136:12` | Base, Layout, and Domain components to expected React paths and props |
| `Dev Handoff / Main State Handoff S1-S13` | `138:2` | Main states to route, ViewModel fields, status dimensions, components, actions, API/event dependencies, recovery |
| `Dev Handoff / Audit State Handoff A1-A14` | `140:2` | Audit states to route, entry context, audit scope, snapshot/record/evidence fields, verdict, permission, stale behavior |
| `Dev Handoff / Prototype Flow Handoff Flow 1-7` | `142:2` | flow nodes to transition triggers, route changes, API/event dependencies, return contexts, recovery |
| `Dev Handoff / API and ViewModel Gaps` | `142:7` | missing/weak audit routes, query gateway, frontend types, mocks, reducer behavior, stale/resync handling |
| `Dev Handoff / Frontend Architecture Input Summary` | `142:12` | routes, feature modules, component layers, ViewModel boundaries, mock scenarios, tests |
| `Dev Handoff / Implementation Readiness Checklist` | `142:17` | P5 readiness criteria and direct-implementation blockers |
| `Dev Handoff / Not Ready and Blocked` | `142:22` | explicit downstream blockers and guardrails |

Verification notes:

- all ten Dev Handoff sections are present on `11 - Dev Handoff`;
- all sections carry run marker `plato-dev-handoff-2026-05-24-batched`;
- repository mirror exists at `docs/design/dev-handoff.md`;
- screenshot verification was not run for this handoff task;
- frontend source code was not modified.

## 11. Readiness Boundary

Allowed next:

- P5 frontend architecture plan from `docs/design/dev-handoff.md`.
- optional clickable Figma prototype reactions as a separate interaction-wiring
  task if product review needs click-through behavior.
- future `Base/Drawer` formalization only if drawer-based navigation, mobile
  detail, or transient inspector behavior becomes part of the product flow.

Not ready yet:

- frontend implementation;
- Audit Page real API integration;
- production-grade visual polish.
