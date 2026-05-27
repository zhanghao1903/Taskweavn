# Main Page Refactor / Rewrite Plan

> Status: P7.2 planning decision
> Last Updated: 2026-05-27
> Scope: Plato Main Page structure, design, and implementation review before
> further P7 component extraction.
> Decision: stop mechanical extraction; use a controlled render/composition
> rewrite around the existing adapter/runtime boundary.
> Non-goals: no Figma modification, no Audit Page implementation, no backend
> route implementation, no immediate full replacement of the runtime/event
> router.

## 1. Workflow Gate Report

| Item | Decision |
|---|---|
| User request | Re-examine Main Page structure, design, and implementation, then decide a refactor or rewrite plan. |
| Detected phase | P7 Vertical Slice Implementation. |
| Task type | Frontend architecture review and implementation planning. |
| Required upstream artifacts | Main Page UX flow, screen-state spec, canonical status model, frontend architecture plan, ViewModel/API/event contracts, current frontend implementation. |
| Found artifacts | `docs/product/plato-main-page-ux-flow.md`, `docs/ux/screen-state-spec.md`, `docs/product/canonical-status-model.md`, `docs/frontend/frontend-architecture-plan.md`, `docs/frontend/ui-viewmodel-contract.md`, `docs/frontend/api-ui-mapping.md`, `docs/frontend/event-reducer-contract.md`, `frontend/src/pages/main-page/*`. |
| Missing or weak artifacts | No dedicated Main Page rewrite plan existed before this document; visual regression baseline is still not automated; runtime reducer is not wired into Main Page. |
| Implementation allowed now | Planning is allowed. Broad UI implementation should wait for this plan to be accepted. |
| Prework required | Record rewrite/refactor decision and next implementation slices. |
| Execution scope | Review current structure, name risks, choose migration strategy, define phases and acceptance criteria. |
| Acceptance criteria | Plan states whether to refactor or rewrite, explains why, preserves accepted product direction, and gives small next tasks. |
| Risks and assumptions | The current page is still a checkpoint, not complete. Tests passing does not mean the UX or architecture is acceptable. |

## 2. Sources Reviewed

- Product: `docs/product/plato-main-page-ux-flow.md`
- UX/state: `docs/ux/screen-state-spec.md`
- Canonical model: `docs/product/canonical-status-model.md`
- Frontend contracts: `docs/frontend/ui-viewmodel-contract.md`,
  `docs/frontend/api-ui-mapping.md`,
  `docs/frontend/event-reducer-contract.md`
- Architecture: `docs/frontend/frontend-architecture-plan.md`
- Current implementation:
  - `frontend/src/pages/main-page/MainPage.tsx`
  - `frontend/src/pages/main-page/MainPage.module.css`
  - `frontend/src/pages/main-page/MainPageDetailPanel.tsx`
  - `frontend/src/pages/main-page/TaskTreePanel.tsx`
  - `frontend/src/pages/main-page/SessionMessagePanel.tsx`
  - `frontend/src/pages/main-page/ContextInputPanel.tsx`
  - `frontend/src/pages/main-page/mainPageSelectors.ts`
  - `frontend/src/pages/main-page/runtime/*`

## 3. Current Implementation Inventory

| Area | Current state |
|---|---|
| Route/runtime boundary | `MainPageRoute` wraps `MainPage`; good P7.1 boundary. |
| Main page component | `MainPage.tsx` is about 950 lines and owns query, events, commands, local UI state, command lifecycle, session lifecycle, projection, and page layout. |
| Runtime logic | Adapter and event router exist, but `MainPage.tsx` directly wires React Query, mutations, event subscription, and resync behavior. |
| Domain rendering | `TaskNodeCard` and `SessionMessageCard` are extracted. `MainPageDetailPanel` still mixes confirmation, result, file-change, task detail, and fallback state rendering. |
| Status mapping | P7.1C centralized label/tone mapping, but most components still consume flat compatibility fields as their primary display source. |
| CSS/layout | One page CSS module owns shell, layout, cards, detail, input, and responsive behavior. |
| Tests | Good App-level behavioral coverage and initial component tests. No browser visual regression baseline yet. |

## 4. Product And Design Findings

### 4.1 What Is Still Correct

- Main Page remains the product control plane.
- TaskTree is still the central operating object.
- Message Stream is secondary process feedback, not a chat-first page.
- Detail Panel conceptually behaves as a Context Inspector.
- Bottom input already shows scope and supports session/task targeting.
- Adapter boundary and status selector work are moving in the right direction.

### 4.2 Design Problems To Fix Early

1. **The page does not yet fully match the accepted historical visual baseline.**
   The top bar, sidebar, and workspace are structurally close, but current
   implementation still feels like a prototype shell.

2. **TaskTree is still too visually simple for the product role it carries.**
   It needs hierarchy, current execution focus, selected node context, pending
   confirmation signals, and readiness/execution separation.

3. **Detail Panel is overloaded.**
   Confirmation, task detail, result, and file changes compete through boolean
   flags instead of a typed detail ViewModel.

4. **Session lifecycle controls use browser dialogs.**
   `prompt` and `confirm` are not product-grade interaction. They should be
   replaced with inline or dialog primitives before user testing.

5. **The Audit entry is a placeholder.**
   It currently shows an unavailable notice instead of preserving route/return
   context. This is acceptable only until the Audit mock slice starts.

6. **Desktop layout acceptance is not precise enough.**
   The product baseline is 1440px desktop workbench density, but current CSS
   collapses the internal work grid at `max-width: 1440px`. That can undermine
   the accepted layout direction.

## 5. Implementation Findings

### 5.1 MainPage Is A God Component

`MainPage.tsx` currently owns too many responsibilities:

- query identity and data loading;
- snapshot error handling;
- confirmation, input, publish, create, rename, and delete mutations;
- event subscription and resync state;
- local UI state reset rules;
- selected task projection;
- detail mode selection;
- top bar/sidebar/workspace/detail/input rendering;
- fixture StatePicker;
- browser prompt/confirm fallback.

This makes further mechanical extraction risky. Small components would inherit
bad boundaries instead of fixing them.

### 5.2 Runtime And Presentation Are Still Coupled

The runtime adapter is good, but `MainPage.tsx` still calls every adapter method
directly and owns all mutation callbacks. A product component should not need to
know that `generateTaskTree`, `appendSessionInput`, `appendTaskInput`, and
`publishTaskTree` are separate transport calls.

### 5.3 Local UI State Is Not A Model Yet

Local state exists as separate `useState` calls:

- selected task id;
- detail override;
- input draft/error;
- command errors;
- UI notices;
- event errors;
- active session id;
- event connection status.

There is no explicit `MainPageLocalState`, so reset/restore behavior is
implemented procedurally. This will become fragile as Audit return context,
permissions, stale snapshots, and confirmation lifecycle grow.

### 5.4 Detail Mode Needs A Typed ViewModel

`MainPageDetailPanel` receives `hasConfirmationFocus`, `hasResultView`,
`hasFileChangeView`, `confirmationDecision`, `selectedTask`, `result`, and
`fileChangeSummary`. This is a symptom that the page does not yet have a typed
detail state:

```ts
type MainPageDetailView =
  | { kind: "workflow"; ... }
  | { kind: "task"; ... }
  | { kind: "confirmation"; ... }
  | { kind: "result"; ... }
  | { kind: "file_changes"; ... }
  | { kind: "stale"; ... }
  | { kind: "error"; ... };
```

The plan should create that model before splitting more detail components.

### 5.5 Status Dimensions Are Present But Not Primary

Types now include `readiness`, `execution`, `confirmation`, and `auditVerdict`,
and mock fixtures populate them. But visual components still mostly rely on
legacy flat status or compatibility metadata. The next refactor must switch
component props toward separated dimensions.

### 5.6 CSS Needs A Layout Layer

`MainPage.module.css` is doing too much. It contains:

- app shell layout;
- top bar;
- sidebar;
- work grid;
- task cards;
- message cards;
- detail panel;
- result/file details;
- context input;
- responsive rules.

This blocks reliable visual iteration. Layout shell classes should move behind
layout components before deep domain UI work continues.

## 6. Decision: Controlled Composition Rewrite, Not Full Big-Bang Rewrite

Do not continue with blind line-by-line extraction from `MainPage.tsx`.

Do not rewrite the entire Main Page in one large replacement either.

Use a controlled rewrite of the render/composition layer while preserving the
working adapter, route wrapper, tests, and API contracts. This is effectively a
strangler rewrite:

```text
MainPageRoute
  -> MainPageRuntimeBoundary / useMainPageController
      -> MainPageWorkbench
          -> MainPageTopBar
          -> WorkflowSidebar
          -> MainWorkArea
              -> TaskTreePanel / TaskNodeCard
              -> SessionMessagePanel / SessionMessageCard
          -> MainPageDetailPanel
              -> TaskDetail
              -> ConfirmationPanel
              -> ResultSummaryPanel
              -> FileChangeSummaryPanel
          -> ContextInputBar
```

The page-level runtime contract remains stable. The render tree becomes new and
cleaner, with tests proving behavior did not regress.

## 7. Target Boundaries

### 7.1 Runtime Boundary

Create a hook or controller:

```ts
type UseMainPageControllerResult = {
  pageState: "loading" | "ready" | "empty_workspace" | "error";
  snapshot: MainPageSnapshot | null;
  view: MainPageViewModel | null;
  local: MainPageLocalState;
  actions: MainPageActions;
};
```

It should own:

- React Query snapshot loading;
- mutation commands;
- event subscription;
- resync and event connection state;
- local state reset/restore;
- command error/notice state.

It should not own:

- CSS layout;
- JSX composition;
- component-level visual details.

### 7.2 ViewModel Boundary

Introduce a `MainPageViewModel` derived from snapshot plus local state:

```ts
type MainPageViewModel = {
  topBar: MainPageTopBarView;
  sidebar: WorkflowSidebarView;
  workspace: MainWorkspaceView;
  detail: MainPageDetailView;
  input: MainPageInputView;
};
```

This is the main point where product design becomes explicit. Components render
ViewModels and call actions; they should not reconstruct product decisions.

### 7.3 Component Boundary

Target component ownership:

| Component | Owns | Must not own |
|---|---|---|
| `MainPageWorkbench` | page composition and slot order | data fetching, mutation callbacks |
| `MainPageTopBar` | product/project/workflow/session/status/audit/settings actions | query keys, adapter calls |
| `WorkflowSidebar` | workflow/session hierarchy and selected session action | browser prompts, session mutation details |
| `MainWorkArea` | work area layout and section order | task selection policy |
| `TaskTreePanel` | task tree rendering and select events | status derivation from backend facts |
| `SessionMessagePanel` | message stream rendering | filtering logic |
| `MainPageDetailPanel` | render typed detail variants | deciding which detail variant is active |
| `ContextInputBar` | input field, submit, disabled state | choosing command endpoint |

## 8. Refactor / Rewrite Phases

### P7.2A - Planning Decision

Status: this document.

Acceptance:

- current structural problems are recorded;
- mechanical extraction is explicitly stopped;
- controlled rewrite path is approved or rejected.

### P7.2B - Extract Main Page Controller

Create `useMainPageController` while preserving visible UI.

Scope:

- move snapshot query, mutations, event subscription, reset/restore logic, and
  handlers out of `MainPage.tsx`;
- keep current render tree initially;
- keep adapter behavior unchanged.

Acceptance:

- `MainPage.tsx` no longer directly wires every mutation;
- existing App/MainPageRoute tests pass;
- no visual/UI copy change.

### P7.2C - Introduce MainPageViewModel

Create selectors that transform snapshot plus local state into a typed
`MainPageViewModel`.

Scope:

- detail view becomes a discriminated union;
- input view includes explicit mode, scope, disabled reason, and target;
- top bar/sidebar/workspace views become explicit;
- components stop deriving business decisions from boolean combinations.

Acceptance:

- `MainPageDetailPanel` receives one `detail` prop instead of many mode booleans;
- input command selection is based on `input.mode`, not `hasTaskTree` and
  selected-task inference in JSX;
- existing tests pass.

### P7.2D - Recompose Workbench Layout

Create a new `MainPageWorkbench` composition that matches the accepted static
Main Page workbench direction.

Scope:

- preserve TaskTree as primary object;
- preserve Message Stream as secondary process feedback;
- preserve Context Inspector as right detail panel;
- keep bottom input scope visible;
- correct desktop layout behavior around 1440px.

Acceptance:

- no fixture/HTTP behavior change;
- desktop layout remains recognizable as the historical workbench;
- 1440px desktop does not collapse the core TaskTree/message/detail hierarchy
  prematurely;
- Browser or Playwright screenshot verification is run for representative
  states before marking this phase done.

### P7.2E - Split Detail Variants

Split `MainPageDetailPanel` into typed subcomponents:

- `TaskDetailPanel`
- `ConfirmationPanel`
- `ResultSummaryPanel`
- `FileChangeSummaryPanel`
- `StateNotePanel`
- later: `StaleSnapshotPanel`, `PermissionDeniedPanel`

Acceptance:

- each variant receives a narrow prop shape;
- no `confirmationDecision={null}` placeholder remains;
- confirmation actions use backend options and local resolving state;
- result/file-change toggle behavior remains tested.

### P7.2F - Move To Canonical Status Dimensions

Switch task and page presentation to separated dimensions where available:

- planning state;
- task readiness;
- execution status;
- confirmation status;
- audit verdict;
- permission/action availability.

Acceptance:

- flat `TaskNodeStatus` remains only as compatibility fallback;
- `waiting_user` is derived from confirmation/planning facts, not treated as
  execution;
- permission-disabled controls show `readonlyReason` when available.

### P7.2G - Replace Browser Dialogs

Replace `globalThis.prompt` and `globalThis.confirm` usage.

Scope:

- create inline or modal session create/rename/delete flow;
- delete confirmation should use product UI copy, not native browser confirm;
- keep behavior testable in jsdom.

Acceptance:

- no `globalThis.prompt` or `globalThis.confirm` in Main Page code;
- create/rename/delete session tests cover cancel, validation, pending, error,
  and success.

### P7.2H - Audit Entry Contract Wiring

Replace the placeholder `View audit` notice with a route-ready audit entry.

Scope:

- preserve return context;
- route to session-scope or task-scope audit when Audit Page route exists;
- until Audit UI exists, keep a disabled/reserved state with explicit reason.

Acceptance:

- no generic "not connected" notice for Audit in production path;
- route builder or disabled reason is tested.

### P7.2I - Visual And Regression Coverage

Add minimal browser visual checks after layout recomposition.

Representative states:

- empty session;
- draft ready;
- task selected;
- running;
- waiting confirmation;
- completed/result;
- file changes;
- permission denied;
- stale/resync;
- command failed.

Acceptance:

- desktop screenshot pass exists before broad styling changes;
- mobile/tablet can remain deferred if explicitly recorded.

## 9. Rewrite Triggers

Use these triggers to stop incremental extraction and switch to the controlled
composition rewrite path:

1. A component extraction would preserve or spread a known product bug.
2. A component needs more than two unrelated boolean mode props.
3. A component needs direct access to adapter, query, mutation, or event-router
   details.
4. A visual fix requires changing page shell, work grid, detail, and input CSS
   together.
5. A status display cannot be implemented without separating readiness,
   execution, confirmation, and audit verdict.
6. The implementation keeps `StatePicker`, fixture-only state, or native browser
   dialogs visible in code paths intended for real runtime.

When any trigger occurs, write or update a short plan before editing code.

## 10. What Not To Rewrite Yet

Keep these stable for now:

- `MainPageRoute`
- `MainPageAdapter`
- `createHttpMainPageAdapter`
- `createMainPageMockAdapter`
- existing mock fixtures and scenario manifests
- `runtime/eventRouter.ts` until reducer replacement is explicitly scheduled
- shared primitive components
- App-level behavior tests

Rewriting these too early would enlarge risk without fixing the current page
structure problem.

## 11. Recommended Next Task

Recommended next task:

```text
Use the product-workflow-gate skill first.

Task:
Start P7.2B Main Page Controller Extraction.

Context:
docs/frontend/main-page-refactor-rewrite-plan.md decides to stop mechanical
component extraction and use a controlled render/composition rewrite. The first
implementation step is to extract runtime/query/mutation/event/local-state
coordination into a `useMainPageController` hook without changing visible UI.

Do not redesign Main Page.
Do not change CSS.
Do not change adapter behavior.
Do not implement Audit Page.
Do not replace the event reducer yet.

Required work:
1. Create a controller hook for current MainPage runtime coordination.
2. Move snapshot query, command mutations, event subscription, local reset, and
   handler callbacks out of `MainPage.tsx`.
3. Keep the existing JSX composition initially.
4. Preserve fixture and HTTP adapter behavior.
5. Add focused tests or extend existing tests for controller behavior where
   practical.
6. Run frontend tests, lint, build, and diff check.

Output:
- files changed
- behavior preserved
- tests/checks run
- remaining P7.2C ViewModel extraction tasks
```
