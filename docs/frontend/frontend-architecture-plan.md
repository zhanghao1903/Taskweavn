# Plato Frontend Architecture Plan

> Status: P5 architecture plan
> Last Updated: 2026-05-27
> Scope: Plato Main Page and Audit Page frontend architecture before P6 API/mock
> contracts and P7 vertical slice implementation.
> Non-goals: no production UI implementation, no MainPage refactor, no Audit
> Page implementation, no Figma modification.

## 1. Readiness Decision

Plato is ready to move from P4 design exploration into P5 frontend
architecture.

The decision is based on these inputs:

- Historical `Plato MVP Main Page Interactive Prototype v0.1` is accepted as a
  static visual/layout baseline for Main Page.
- Historical `Audit Page v0.1` is accepted as a static visual/layout baseline
  for Audit Page.
- Figma is frozen as visual reference only. Figma Auto Layout, canonical Figma
  component internals, and generated Figma component sets are not implementation
  sources.
- Behavioral source of truth exists in:
  - `docs/product/canonical-status-model.md`
  - `docs/ux/screen-state-spec.md`
  - `docs/frontend/ui-viewmodel-contract.md`
  - `docs/frontend/event-reducer-contract.md`
  - `docs/frontend/api-ui-mapping.md`
  - `docs/engineering/audit-page-contract.md`

Frontend implementation is not ready yet. The next allowed work is P6 API/mock
contract and fixture preparation, followed by P7 vertical slices.

## 2. Source-Of-Truth Hierarchy

Use this precedence order when implementation details conflict:

| Rank | Source | Owns |
|---:|---|---|
| 1 | Backend/domain contracts and canonical status model | Planning state, task readiness, execution status, confirmation status, permission/action availability, audit verdict. |
| 2 | `ui-viewmodel-contract.md`, `api-ui-mapping.md`, `event-reducer-contract.md` | Frontend ViewModel shape, reducer behavior, event handling, API adapter behavior. |
| 3 | `screen-state-spec.md`, `audit-page-contract.md` | Page states, route behavior, audit scopes, entry/return context, error/permission/stale states. |
| 4 | Historical Main/Audit Figma drafts | Visual density, layout intent, information hierarchy, static product copy examples. |
| 5 | Current frontend codebase | Existing implementation constraints and migration surface. |
| 6 | Canonical Figma design-system file | Historical work record only; not a one-to-one implementation map. |

Do not copy Figma-generated component geometry into React. Use CSS layout,
tokens, ViewModels, and browser verification.

## 3. Route Architecture

Introduce route constants before implementing new pages.

Target routes:

| Route name | Path | Page | Notes |
|---|---|---|---|
| `main.session` | `/projects/:projectId/workflows/:workflowId/sessions/:sessionId` | Main Page | Preferred contextual route. |
| `main.sessionFallback` | `/sessions/:sessionId` | Main Page | Use when project/workflow context is unavailable or inferred. |
| `audit.session` | `/sessions/:sessionId/audit` | Audit Page | Session-scope trust plane. |
| `audit.task` | `/sessions/:sessionId/tasks/:taskNodeId/audit` | Audit Page | Task-scope trust plane. |
| `diagnostics.logs` | `/sessions/:sessionId/diagnostics/logs` | Future diagnostics | Reserved; link only until implemented. |
| `settings` | `/settings` | Future settings | Reserved for user/config management. |

Current state:

- `frontend/src/app/routes.ts` exposes typed Main, Audit, diagnostics, and
  settings route constants/builders.
- `frontend/src/app/App.tsx` mounts `MainPageRoute`, not `MainPage` directly.
- `frontend/src/app/MainPageRoute.tsx` is the P7.1A route/runtime
  compatibility wrapper for the existing `MainPage`.
- There is still no browser route switch. Main Page remains mounted at `/` for
  the current dev flow.

P5/P6 target:

- Add typed route constants and route builders in `frontend/src/app/routes.ts`.
- Keep `MainPage` mounted at `/` temporarily for current dev flow.
- Add route parsing later through a minimal router wrapper, not inside
  `MainPage.tsx`.
- Preserve Audit return context through query/state:
  `returnSessionId`, `returnTaskNodeId`, `returnFocus`, `recordId`, and
  `filter`.

### 3.1 MainPageRoute Responsibility Boundary

`MainPageRoute` is a route-level composition wrapper. It is intentionally thin.

It owns:

- resolving the `MainPageAdapter` from runtime env via
  `createMainPageAdapterFromRuntimeEnv`;
- allowing explicit adapter injection for tests and future route/runtime
  providers;
- forwarding `initialStateId` during the fixture-to-route compatibility period;
- preserving workspace-first startup, including HTTP mode without a startup
  session id.

It does not own:

- `MainPageSnapshot` query behavior;
- command submission or command response handling;
- event routing, reducer replacement, or resync loop behavior;
- status presentation mapping;
- local UI state such as selected task, detail override, pending input, or
  confirmation errors;
- CSS layout, visual density, or component extraction;
- API mock happy path behavior.

P7.1B should keep this boundary stable. Any logic that projects backend facts
into visible labels, tones, or disabled states should move to selectors/mappers
before layout/domain component extraction.

## 4. Feature And Module Structure

Adopt a feature-oriented structure without moving existing files in the first
slice.

Target structure:

```text
frontend/src/
  app/
    App.tsx
    routes.ts
    providers.tsx
  shared/
    api/
    components/
    styles/
    utils/
  entities/
    project/
    workflow/
    session/
    task/
    message/
    confirmation/
    result/
    file-change/
    audit/
  features/
    runtime/
      reducer.ts
      effects.ts
      selectors.ts
    main-page/
      api/
      model/
      components/
      MainPageRoute.tsx
    audit-page/
      api/
      model/
      components/
      AuditPageRoute.tsx
  pages/
    main-page/
    audit-page/
```

Migration rule:

- Do not move `frontend/src/pages/main-page/*` before P7 slices prove the new
  contracts.
- New architecture files may wrap existing page code from outside.
- New Audit files should be created under `pages/audit-page` or
  `features/audit-page` during implementation; do not add Audit logic into
  `MainPage.tsx`.

## 5. Component Layering Strategy

Use the existing frontend layers as the implementation base, not Figma component
sets.

### 5.1 Base Components

Current files:

- `frontend/src/shared/components/button/Button.tsx`
- `frontend/src/shared/components/badge/Badge.tsx`
- `frontend/src/shared/components/panel/Panel.tsx`
- `frontend/src/shared/components/text/Text.tsx`
- `frontend/src/shared/styles/tokens.css`

Plan:

- Keep these components.
- Add missing primitives only when needed by a vertical slice:
  `Input`, `TextArea`, `EmptyState`, `ErrorState`, `Skeleton`, `Toast`,
  `Tooltip`.
- Keep base components domain-free.
- Use token CSS variables; avoid page-local colors unless a token gap is
  explicitly recorded.

### 5.2 Layout Components

Target components:

| Component | Purpose | Initial source |
|---|---|---|
| `AppShell` | TopBar, SideNav, main work area, detail panel, input dock slots. | Extract/wrap from `MainPage.module.css` layout patterns later. |
| `TopBar` | Product mark, project/workflow/session context, status chips, actions. | Historical Main Page static draft. |
| `SideNav` | Workflow list and session list. | Existing `MainPage` sidebar markup. |
| `MainWorkArea` | Central TaskTree/messages/result/file area. | Existing `TaskTreePanel`, `SessionMessagePanel`, layout CSS. |
| `DetailPanel` | Selected task, confirmation, result, file/audit summary. | Existing `MainPageDetailPanel`. |
| `ContextInputBar` | Explicit input mode/scope and submit affordance. | Existing `ContextInputPanel`. |

Do not extract these components in the P5 document task. Extract them in P7 only
when a slice has tests and visual acceptance.

### 5.3 Domain Components

Target components:

| Component | Source of truth | Current status |
|---|---|---|
| `TaskTree` | `TaskTreeView` and selected task local state. | Existing `TaskTreePanel` can remain. |
| `TaskNode` | `TaskNodeCardView` with separated readiness/execution fields. | Current implementation uses flat `TaskNodeStatus`; wrap first. |
| `MessageStream` | `SessionMessageView[]` plus stream/local partial state. | Existing `SessionMessagePanel` can remain. |
| `MessageCard` | `SessionMessageView`. | Existing panel-local rendering can be extracted later. |
| `ConfirmationPanel` | `ConfirmationActionView` plus local resolving state. | Existing detail panel behavior can remain initially. |
| `FileChangeTable` | `FileChangeSummaryView`. | Existing detail/file summary rendering can be wrapped. |
| `AuditEntryCard` | `AuditSummaryView` or `AuditRecord`. | New component; not in current code. |

## 6. Main Page Composition Plan

Main Page keeps the historical workbench intent:

- Top bar: product mark, project, workflow, session, status, audit/settings
  actions.
- Left side: workflow/session hierarchy.
- Main area: TaskTree as primary control object.
- Supporting stream: process messages scoped by session or selected task.
- Right detail: workflow setup, selected task, confirmation, result, file
  changes, or audit entry.
- Bottom input: explicit mode and scope.

P5 composition boundary:

```text
MainPageRoute
  RuntimeProvider / useMainRuntime
    AppShell
      TopBar
      SideNav
      MainWorkArea
        TaskTree
        MessageStream
      DetailPanel
        TaskDetail | ConfirmationPanel | ResultSummary | FileChangeSummary
      ContextInputBar
```

Existing files:

| File | P5 decision |
|---|---|
| `pages/main-page/MainPage.tsx` | Keep for now. Wrap later; do not rewrite first. |
| `ContextInputPanel.tsx` | Keep; later rename/extract to `ContextInputBar`. |
| `MainPageDetailPanel.tsx` | Keep; later split detail modes. |
| `SessionMessagePanel.tsx` | Keep; later extract `MessageStream`/`MessageCard`. |
| `TaskTreePanel.tsx` | Keep; later adapt to separated status fields. |
| `MainPage.module.css` | Keep; later migrate repeated layout tokens into layout components. |
| `mainPageSelectors.ts` | Keep; extend selectors instead of adding logic to JSX. |
| `runtime/adapter.ts` | Keep; evolve toward `MainPageSnapshot` target contract. |
| `runtime/eventRouter.ts` | Keep as compatibility shim; replace with reducer in later phase. |
| `mockPlatoApi.ts`, `fixtures.ts` | Keep; extend into scenario manifests in P6. |

## 7. Audit Page Composition Plan

Audit Page is read-only. It does not publish, edit, retry, cancel, resolve
confirmations, or expose raw logs by default.

Audit Page layout intent:

- Top bar preserves Main Page context and return affordance.
- Left/filter area shows audit scope and record counts.
- Main area shows audit records/timeline.
- Detail area shows selected record, evidence, hidden/partial state, config
  summary, and related logs link.
- Return target preserves the originating Main Page session/task/confirmation
  context.

Target composition:

```text
AuditPageRoute
  useAuditRuntime
    AppShell
      TopBar
      AuditFilterPanel
      AuditRecordList
        AuditEntryCard
      AuditRecordDetailPanel
        EvidenceSummary
        FileChangeTable
        EffectiveConfigSummary
        RelatedLogsLink
```

First implementation should support:

- `audit.session`
- `audit.task`
- loading
- empty
- ready with records
- selected record
- partial evidence
- hidden evidence / permission limited
- permission denied
- stale snapshot
- query error
- evidence load error

Do not implement logs or settings pages. Show links as reserved affordances only
when the contract provides them.

## 8. ViewModel Boundaries

The frontend must consume ViewModels, not raw backend facts.

### 8.1 Main Page Snapshot

Target owner: `MainPageSnapshot`.

Required dimensions:

- `planning.state`
- `taskTree.readiness`
- `taskNode.readiness`
- `taskNode.execution`
- `taskNode.confirmation`
- `taskNode.auditVerdict`
- `permissions`
- `availableActions`
- `cursor`

Current gap:

- `frontend/src/shared/api/types.ts` still uses flat `SessionStatus`,
  `TaskTreeStatus`, and `TaskNodeStatus`.

Migration strategy:

1. Add new status dimension types alongside current flat types.
2. Add adapter selectors that derive target dimensions from current flat
   statuses for compatibility.
3. Move components to derived dimensions.
4. Remove canonical UI reliance on flat status only after backend transport is
   migrated.

### 8.2 Audit Page Snapshot

Target owner: `AuditPageSnapshot`.

Required fields:

- request, scope, entryContext, returnTarget
- project/workflow/session/selectedTask
- overview
- filters
- records
- selectedRecord
- effectiveConfig
- relatedLogs
- permissions
- pageState
- cursor/generatedAt

Current gap:

- Backend additive models exist.
- Frontend types and HTTP methods do not exist.
- HTTP routes are not implemented.

P6 must add mock-compatible frontend types and adapter methods before any UI.

## 9. Local UI State Boundaries

Local UI state must stay out of backend snapshots.

Main local state:

- selected task node id
- expanded task ids
- detail override
- input draft text
- input mode override only when user explicitly changes target
- pending command state
- confirmation local status: `idle`, `resolving`, `resolve_failed`
- event connection state
- stale/resync state
- transient notices/errors

Audit local state:

- selected record id
- active filter
- expanded evidence sections
- copied/opened evidence UI state
- stale/resync state
- evidence detail loading/error state
- return navigation state

Rule:

- Backend status changes only through snapshots/events.
- Command accepted creates local pending state, not canonical success.
- Selection should restore by id after resync when possible.

## 10. Reducer And Event Architecture

Introduce a shared runtime reducer after route/API types are stable.

Target runtime state:

```ts
type RuntimeState<TSnapshot, TLocal> = {
  snapshot: TSnapshot | null;
  local: TLocal;
  pendingCommands: Record<string, PendingCommandState>;
  event: EventConnectionState;
  lastAppliedCursor: EventCursor | null;
};
```

Reducer responsibilities:

- load snapshot atomically;
- apply safe complete ViewModel event fragments;
- request targeted query or resync for incomplete events;
- handle command accepted/rejected/completed/failed;
- preserve selection across resync;
- disable high-risk controls when stale/resyncing;
- ignore unsupported events safely.

Current state:

- `MainPage.tsx` uses React Query plus local `useState`.
- `runtime/eventRouter.ts` refetches for all events except ignore handling.

Migration strategy:

1. Keep current event router as compatibility shim.
2. Add reducer tests against `event-reducer-contract.md`.
3. Move event side effects to adapter/effects layer.
4. Switch Main Page to reducer only after mock and HTTP paths pass.
5. Use the same reducer pattern for Audit Page from the start.

## 11. API Adapter Boundary

API adapters must isolate transport from components.

Current API:

- `frontend/src/shared/api/platoApi.ts` exposes Main Page snapshot, commands,
  session lifecycle, and events.
- It does not expose Audit Page query methods.
- `uiEventTypes` does not include `audit.records_changed`,
  `audit.record_updated`, `audit.evidence_hidden`, or `audit.snapshot_stale`.

Target adapter additions for P6:

```ts
type PlatoApi = {
  getAuditSnapshot(request: AuditSnapshotRequest): Promise<QueryResponse<AuditPageSnapshot>>;
  listAuditRecords(request: AuditRecordsRequest): Promise<QueryResponse<AuditRecord[]>>;
  getAuditRecordDetail(request: AuditRecordDetailRequest): Promise<QueryResponse<AuditRecordDetail>>;
  getEvidenceDetail(request: EvidenceDetailRequest): Promise<QueryResponse<EvidenceDetail>>;
};
```

Rules:

- Components receive ViewModels from hooks/selectors, not `PlatoApi` directly.
- API errors map through `api-ui-mapping.md`.
- Audit evidence detail must not expose raw payloads by default.
- Missing audit routes in real backend must be handled by mock adapter until P8.

## 12. Mock Scenario Plan

P6 must extend mocks before implementation.

Required scenario groups:

| Group | Scenarios |
|---|---|
| Main happy path | empty session, understanding, draft ready, task selected, task editing, running, waiting confirmation, completed, file changes/audit entry. |
| Main negative/recovery | permission denied, stale/resync, backend busy, command failed/recoverable. |
| Confirmation | pending, resolving, resolved, expired, resolve failed. |
| Audit happy path | empty, loading, records ready, record selected. |
| Audit evidence/verdict | partial evidence, hidden evidence, warning, failed, inconclusive, not available. |
| Audit negative/recovery | permission denied, stale snapshot, query error, evidence load error. |
| Events | duplicate, unsupported, malformed, cursor expired, resync required, audit records changed. |

Each mock scenario must declare:

- route;
- page;
- canonical status dimensions;
- ViewModel fixture;
- expected visible components;
- primary actions;
- disabled actions;
- expected recovery behavior.

Existing fixtures in `pages/main-page/fixtures.ts` can remain. Add scenario
manifests around them instead of replacing all fixtures at once.

## 13. Visual Baseline Acceptance Notes

Use historical drafts as static references for:

- 1440px desktop workbench density;
- TopBar context density;
- workflow/session SideNav hierarchy;
- TaskTree as the central operating object;
- contextual DetailPanel;
- bottom scoped input;
- message stream as process feedback, not chat-first UI;
- Audit Page as trust plane with records/detail/evidence.

Do not use historical drafts for:

- exact pixel copying;
- Figma Auto Layout constraints;
- component internal hierarchy;
- code component names;
- production text;
- mobile/responsive final behavior.

Visual acceptance for P7:

- Main Page must be recognizable as the historical workbench layout.
- Audit Page must preserve read-only trust-plane behavior.
- TaskTree hierarchy, selected task, confirmation, result, file summary, audit
  entry, permission, stale, and error states must remain visually distinct.
- Desktop layout must be checked first; tablet/mobile can be explicitly deferred
  unless required by a slice.

## 14. Implementation Phases From P6 To P7

### P6.1 Frontend Type Contract

- Add target status dimension types.
- Add Audit Page ViewModel types.
- Add route constants/builders.
- Add compatibility mappers from flat current statuses to separated dimensions.
- Tests: type-level fixtures and mapper tests.

### P6.2 Mock Scenario Layer

- Add scenario manifests.
- Extend Main Page fixtures without deleting existing fixture states.
- Add Audit mock snapshots and records.
- Tests: every required scenario loads a valid ViewModel.

### P6.3 API Adapter Boundary

- Add Audit API method signatures.
- Add mock adapter implementation.
- Add HTTP adapter stubs only after backend route contract is final.
- Extend event type list with audit event candidates.
- Tests: API error mapping, stale/resync mapping, permission mapping.

### P6.4 Runtime Reducer Foundation

- Add shared reducer and effects contract.
- Keep Main Page current event router until reducer tests pass.
- Build Audit Page on reducer from the start.
- Tests: confirmation lifecycle, command accepted vs final facts, stale/resync,
  unsupported events.

### P7.1 Main Page Compatibility Wrap

- Wrap current `MainPage` with route/runtime providers.
- Preserve existing visible behavior.
- Move status presentation mapping into one selector module.
- Do not redesign UI in this slice.

P7.1A status: `MainPageRoute` now wraps the current `MainPage` while preserving
fixture and HTTP adapter behavior.

P7.1B decision: centralize status presentation mapping before P7.2 component
extraction. Extracting layout/domain components first would spread the current
flat status compatibility logic across more files and make the later canonical
status migration more expensive.

### P7.2 Main Page Component Extraction

- Extract layout/domain components only when each extracted unit has tests.
- Replace flat status reads with separated dimension selectors.
- Keep CSS/token changes scoped.

P7.2 decision update: further Main Page work should follow
`docs/frontend/main-page-refactor-rewrite-plan.md`. Do not continue mechanical
component extraction when it preserves bad boundaries. The next implementation
step should extract a `useMainPageController` runtime boundary, then introduce a
typed `MainPageViewModel`, then recompose the workbench layout.

### P7.3 Audit Page Mock Vertical Slice

- Implement read-only Audit Page against mock `AuditPageSnapshot`.
- Cover loading, empty, ready, selected record, partial, hidden evidence,
  permission denied, stale, query error, evidence error.

### P7.4 Real Audit Adapter Integration

- Wire HTTP audit routes only after backend handlers exist.
- Keep mock route switch for development.
- Add integration tests for snapshot/query/error behavior.

## 15. Existing Frontend File Decisions

| Path | Decision |
|---|---|
| `frontend/src/app/App.tsx` | Keep; later wrap with route switch/provider. |
| `frontend/src/app/routes.ts` | Extend in P6. |
| `frontend/src/shared/api/types.ts` | Extend with new status dimensions and Audit types; do not remove flat types immediately. |
| `frontend/src/shared/api/platoApi.ts` | Extend with Audit query methods and audit event types in P6. |
| `frontend/src/pages/main-page/MainPage.tsx` | Keep intact for first architecture/mocking phases; wrap before refactor. |
| `frontend/src/pages/main-page/runtime/adapter.ts` | Keep; evolve into Main runtime adapter. |
| `frontend/src/pages/main-page/runtime/eventRouter.ts` | Keep as compatibility shim; replace after reducer foundation. |
| `frontend/src/pages/main-page/runtime/metadata.ts` | Keep; later replace flattened status derivation with separated selectors. |
| `frontend/src/pages/main-page/mainPageSelectors.ts` | Keep and extend; preferred place for ViewModel projection logic. |
| `frontend/src/pages/main-page/fixtures.ts` | Keep; add scenario manifests around fixtures. |
| `frontend/src/shared/components/*` | Keep; add missing primitives only as needed. |
| `frontend/src/entities/audit/model.ts` | Extend or supersede with Audit ViewModel types in P6. |

## 16. Risks And Blockers

| Risk/blocker | Impact | Mitigation |
|---|---|---|
| Backend transport still exposes flat statuses. | UI may keep collapsing dimensions. | Add compatibility mapper and migrate component reads incrementally. |
| Audit HTTP routes are not implemented. | Real Audit Page integration blocked. | Build mock Audit vertical slice first; keep adapter boundary explicit. |
| Figma canonical components are unstable as implementation source. | Pixel/component churn and accidental semantic edits. | Freeze Figma; use historical drafts only as visual references. |
| `MainPage.tsx` contains mixed runtime, data, local state, and presentation logic. | Refactor blast radius is high. | Wrap first; extract in tested vertical slices. |
| Event reducer is not implemented. | Stale/resync and command lifecycle behavior may stay ad hoc. | Add reducer tests before wiring broadly. |
| Existing CSS may encode page-specific layout values. | Component extraction may regress visual baseline. | Preserve CSS initially; introduce layout components gradually. |
| Audit hidden evidence/log behavior can leak internals if rushed. | Trust and security risk. | Keep raw payloads/logs out of primary UI; follow Audit contract. |
| Mobile/responsive behavior is not final. | Wider device support delayed. | Mark desktop as first target; add responsive acceptance later. |

## 17. Explicit Non-Goals

- No Figma writes.
- No Figma component-to-React one-to-one implementation requirement.
- No production UI changes.
- No `MainPage.tsx` refactor in this task.
- No Audit Page implementation in this task.
- No backend route implementation.
- No new visual design language.
- No final production copy approval.
- No mobile/responsive finalization.
- No raw logs, raw tool payloads, provider payloads, or stack traces in the
  primary UI.
