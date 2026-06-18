# Main Page No-Topbar Three-Column Frontend Implementation Plan

> Status: implemented through no-topbar shell; Markdown renderer follow-up
> planned
>
> Last Updated: 2026-06-17
>
> Gap: Main Page still uses a topbar-oriented workbench and does not yet expose
> the accepted Session conversation / Direct Task entry model as the primary
> user perception layer.
>
> Architecture:
> [Plato Frontend Technical Design](../../product/plato-frontend-technical-design.md),
> [Plato UI API Contract](../../product/plato-ui-api-contract.md)
>
> Product:
> [Conversation And Direct Task PRD](../../product/plato-conversation-and-direct-task-prd.md),
> [Conversation And Direct Task UX Flow](../../product/plato-conversation-and-direct-task-ux-flow.md),
> [Main Page UX Flow](../../product/plato-main-page-ux-flow.md)
>
> Release Record: 2026-06-16 local frontend validation

---

## 1. Problem / Gap

The current Main Page proves the Task-first control plane, but the user can
still experience work as background state changes:

```text
input -> status changes -> task progress
```

The accepted UX direction requires a clearer user perception loop:

```text
input
  -> Plato shows interpretation
  -> Plato chooses read-only answer, Direct Task, or Plan required
  -> the related answer / task / plan is visible in the workbench
```

The visual layout also needs to spend more space on work:

```text
Workspace Rail | Session Work Area | Detail Panel
```

This plan defines the frontend slices needed to remove the persistent topbar,
move its responsibilities into the three-column shell, and add the first
Conversation / Plan layer model.

---

## 2. References Reviewed

- Product acceptance source:
  [Conversation And Direct Task UX Flow](../../product/plato-conversation-and-direct-task-ux-flow.md)
- Product requirements:
  [Conversation And Direct Task PRD](../../product/plato-conversation-and-direct-task-prd.md)
- Existing Main Page UX:
  [Main Page UX Flow](../../product/plato-main-page-ux-flow.md)
- Frontend architecture:
  [Plato Frontend Technical Design](../../product/plato-frontend-technical-design.md)
- API boundary:
  [Plato UI API Contract](../../product/plato-ui-api-contract.md)
- Current implementation area:
  `frontend/src/pages/main-page/`

---

## 3. Scope

### 3.1 Included

1. Replace the Main Page persistent topbar with a three-column workbench shell.
2. Move product identity, workspace/session navigation, session status, event
   status, settings entry, and audit entry into their new locations.
3. Add a center-column `Conversation / Plan` layer switch.
4. Preserve existing Plan & Progress / TaskTree behavior.
5. Add first frontend representations for the three entry states:
   read-only answer, Direct Task, and Plan required.
6. Keep `ContextInputPanel` scope visible and aligned with the selected
   Session / Plan / Task target.
7. Preserve ASK, confirmation, stop, retry, audit, file summary, and detail
   panel behavior.
8. Add mock/fixture states for the new entry states before depending on backend
   route outcome fields.
9. Cover desktop and narrow responsive layouts.
10. Add a shared safe Markdown renderer for Conversation, Activity preview,
    and Detail result text.

### 3.2 Excluded

1. No backend Runtime Input Router implementation.
2. No new durable conversation store.
3. No new API endpoint required in the first frontend slice.
4. No Figma write in this plan.
5. No raw Action / Observation stream in Main Page.
6. No chat-first replacement of TaskTree.
7. No multi-agent routing visual model.
8. No raw HTML, script execution, MDX, or arbitrary custom component rendering
   from message Markdown.

---

## 4. Product Decisions Locked By This Plan

1. Main Page moves toward no persistent topbar.
2. The left column is the Workspace Rail.
3. The center column is the Session Work Area.
4. The right column remains the focused Detail Panel.
5. Conversation and Plan are switchable center-column layers.
6. Chat/conversation is a projection and perception layer, not a canonical
   state owner.
7. Direct Task is still a Task, even when it skips full visible Plan review.

---

## 5. Proposed Frontend Design

### 5.1 Target Component Shape

Current code should evolve toward:

```text
MainPage
  -> MainPageShell
      -> WorkspaceRail
      -> SessionWorkArea
          -> SessionWorkAreaHeader
          -> ConversationPlanSwitch
          -> ConversationLayer
          -> PlanProgressLayer
          -> ContextInputPanel
      -> MainPageDetailPanel
  -> SharedSafeMarkdownRenderer
```

Implementation can reuse existing components:

| Existing component | Target role |
|---|---|
| `MainPageSessionSidebar` | Seed for `WorkspaceRail`. |
| `MainPageWorkspaceSwitcher` | Workspace rail section. |
| `MainPageTopBar` | Remove after moving responsibilities. |
| `MainPageWorkbench` | Split into center-column layer composition. |
| `TaskTreePanel` | Plan & Progress layer content. |
| `LatestActivityStrip` | Session Work Area status/activity row. |
| `ActivityOverlay` | Candidate for full Conversation layer or transition source. |
| `MainPageDetailPanel` | Keep as right-column focused object inspector. |
| `ContextInputPanel` | Keep bottom input; clarify Session / Plan / Task scope. |
| Shared safe Markdown renderer | Shared text renderer for Conversation, Activity preview, and Detail result bodies. |

### 5.2 Local UI State

The first frontend slice can keep this as local UI state:

```ts
type CenterLayer = "conversation" | "plan";
```

Recommended defaults:

| Session condition | Default layer |
|---|---|
| Empty/new session | `conversation` |
| Active Plan/TaskTree exists | `plan` |
| Direct Task active | `conversation`, with compact task progress visible |
| User manually switches layer | preserve until session changes |

Do not persist the layer choice to backend in the first slice.

### 5.3 Entry State Projection

The frontend should display route outcomes as projected UI states:

```ts
type RuntimeEntryProjection =
  | { kind: "none" }
  | { kind: "read_only_answer"; messageId: string }
  | { kind: "direct_task"; taskNodeId: string }
  | { kind: "plan_required"; planId?: string };
```

In the first implementation slice this can be derived from existing fixture
data and mock scenarios. The backend contract can later add explicit route
outcome fields if needed.

### 5.4 Layout Rules

Desktop target:

```text
Workspace Rail: fixed, compact, scrollable session list
Session Work Area: flexible center, owns Conversation / Plan switch
Detail Panel: fixed or minmax right column, scrollable content
Input: bottom of Session Work Area
```

Narrow target:

```text
Workspace Rail -> collapsible
Session Work Area -> primary
Detail Panel -> drawer or stacked panel
Conversation / Plan switch -> stays visible
```

The implementation should use existing CSS tokens. New hardcoded colors,
spacing, radius, shadows, and z-index values should be avoided when tokens
exist.

---

## 6. Implementation Slices

### C0. Maintainability Inventory

Before code edits, run the maintainability gate because current Main Page files
already include large files:

| File | Current risk |
|---|---|
| `frontend/src/pages/main-page/useMainPageController.ts` | Over 1200 lines; avoid adding broad behavior directly. |
| `frontend/src/pages/main-page/MainPage.module.css` | Over 1200 lines; prefer extracting layout CSS modules or scoped sections. |
| `frontend/src/pages/main-page/mockPlatoApi.ts` | Over 1000 lines; fixture additions should be narrow. |

Expected output:

- a short maintainability report;
- decision on whether to split shell/layout before adding behavior;
- explicit files to touch in the first code slice.

### C1. Shell Extraction Without Behavior Change

Goal: introduce the new shell structure while preserving existing behavior.

Work:

- add or refactor `MainPageShell`;
- move current layout slots into left/center/right regions;
- keep current content and tests passing;
- do not remove `MainPageTopBar` until its responsibilities have a target.

Acceptance:

- existing Main Page tests pass;
- no feature behavior changes;
- visual layout can still render current states.

### C2. Workspace Rail Migration

Goal: make left rail the home for product identity and workspace/session
navigation.

Work:

- place compact Plato identity in rail header;
- move workspace selector and session list into rail;
- place settings/workspace management entry in rail footer or compact rail
  control;
- remove duplicated navigation from topbar.

Acceptance:

- workspace/session switching remains functional;
- first-run/workspace-entry paths still reach Main Page;
- rail scroll behavior is stable.

### C3. Session Work Area Header And Status Row

Goal: replace topbar status with a center-column header.

Work:

- show current session title in Session Work Area;
- show published/running/stopping/failed status in the status row;
- keep event-live indicator discoverable;
- move audit entry to related object control.

Acceptance:

- selected session and status remain visible without topbar;
- audit is still reachable from session/task context;
- stale/error states remain visible.

### C4. Conversation / Plan Layer Switch

Goal: add the center-column layer model.

Work:

- add a segmented control or tabs for `Conversation` and `Plan & Progress`;
- default layer from session condition;
- preserve user-selected layer during the current session;
- keep TaskTree selection independent from layer choice.

Acceptance:

- switching layers does not lose selected TaskNode;
- Plan & Progress still shows the existing TaskTree;
- empty sessions default to Conversation.

### C5. Conversation Layer First Projection

Goal: make the user see how Plato responded.

Work:

- render a session-level conversation/activity list from existing projected
  messages and latest activity;
- add visible route interpretation copy for:
  - read-only answer;
  - Direct Task;
  - Plan required;
- avoid raw Action / Observation payloads;
- link conversation items to related Plan/Task/Audit refs when available.

Acceptance:

- user input and Plato response are visible in chronological order;
- read-only answer does not create a Task row;
- Direct Task links to its Task;
- Plan required links to Plan & Progress.

### C5A. Shared Safe Markdown Renderer

Goal: render user-facing long text consistently without making Markdown a new
authority boundary.

Work:

- add a shared Markdown rendering primitive outside page-specific components,
  for example `frontend/src/shared/components/MarkdownContent.tsx` or the
  nearest existing shared UI location;
- choose an implementation that supports paragraphs, emphasis, headings,
  ordered/unordered lists, blockquotes, inline code, fenced code blocks, links,
  and tables;
- sanitize or disable raw HTML, script tags, event handlers, iframes, and
  unsafe URL schemes such as `javascript:`;
- expose a small surface API for variants such as `conversation`, `activity`,
  and `detail`, plus optional preview controls such as max lines or collapsed
  display;
- replace ad hoc plain-text rendering for Conversation message bodies,
  Activity preview/result bodies, and Detail result bodies where the source
  content is Markdown-capable;
- keep audit evidence and domain facts unchanged; Markdown output is display
  only;
- add fixtures covering lists, tables, fenced code, links, long Markdown, and
  unsafe HTML input.

Acceptance:

- the same Markdown body renders consistently across Conversation, Activity,
  and Detail surfaces;
- unsafe HTML/script input is stripped or rendered inert;
- Markdown links cannot execute unsafe URL schemes;
- preview surfaces can avoid large layout jumps from long content;
- tests cover lists, tables, code blocks, links, and unsafe HTML;
- no production path uses unsanitized `dangerouslySetInnerHTML`.

### C6. Mock Scenarios And Fixture Coverage

Goal: make the three entry states testable before backend routing is complete.

Work:

- add fixture/mock states for:
  - read-only answer;
  - Direct Task queued/running/done;
  - Plan required draft;
- update state catalog labels if present;
- add tests for layer defaults and entry projection.

Acceptance:

- mock mode can manually inspect all three entry states;
- tests assert no Task appears for read-only answer;
- tests assert Direct Task appears as a task, not a full plan review.

### C7. Detail Panel And Context Input Preservation

Goal: preserve existing task-first operations.

Work:

- ensure `MainPageDetailPanel` still follows selected Task/Plan/ASK/
  confirmation;
- keep stop/retry/ASK/confirmation controls available where currently
  supported;
- keep `ContextInputPanel` bottom anchored and scope-labeled.

Acceptance:

- existing ASK/confirmation tests pass;
- task selection updates Detail Panel;
- input disabled/read-only states remain correct.

### C8. Responsive And Visual QA

Goal: verify the new density and layout behavior.

Work:

- desktop viewport check;
- narrow viewport check;
- long session list;
- long task title;
- long conversation answer;
- detail panel overflow.

Acceptance:

- no incoherent overlap;
- no clipped primary controls;
- topbar is gone in Main Page;
- each column has one stable purpose.

### C9. Docs And Closure

Goal: close the implementation loop.

Work:

- update this plan with completion notes;
- update Product 1.0/1.1 gap or roadmap docs if this changes release scope;
- update frontend QA runbook if smoke paths change;
- add release note after acceptance.

Acceptance:

- docs match implementation facts;
- validation commands are recorded;
- screenshots or browser smoke evidence exist if UI changed.

---

## 7. API And Backend Assumptions

The first frontend implementation should not require a backend migration.

Allowed:

- derive route outcome presentation from existing snapshot/messages/fixtures;
- add frontend-only mock scenarios;
- add optional frontend ViewModel fields if they are normalized from existing
  API fields.

Not allowed without a separate API contract update:

- inventing new backend command names in UI code;
- requiring a new endpoint for Direct Task routing;
- treating conversation messages as canonical Plan/Task state;
- hiding backend inconsistency in component logic.

If the frontend needs explicit route outcome fields, update
[Plato UI API Contract](../../product/plato-ui-api-contract.md) before
implementing HTTP mode behavior.

---

## 8. Test And Validation Plan

Minimum local checks for implementation slices:

```text
cd frontend
npm run test -- MainPage
npm run test -- main-page
npm run build
```

Targeted test coverage:

- shell layout renders without topbar;
- Workspace Rail navigation remains functional;
- Conversation / Plan switch preserves selection;
- read-only answer creates no task;
- Direct Task renders as a task;
- Plan required opens Plan & Progress;
- ASK and confirmation panels still render;
- command rejected / error states still preserve input.
- shared Markdown renderer handles lists, tables, code blocks, links, long
  content, and unsafe HTML safely.

Browser validation:

- mock mode desktop;
- mock mode narrow viewport;
- HTTP sidecar mode if route outcome fields are wired to backend data;
- Electron smoke only after layout is stable in Vite.

---

## 9. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Existing Main Page controller is too large. | Run maintainability gate and prefer shell/layout extraction before behavior changes. |
| CSS file grows further. | Create scoped layout CSS modules for shell/rail/layers if needed. |
| Conversation layer pulls UI toward chat-first. | Keep Plan & Progress as first-class layer and preserve Task authority. |
| Backend lacks explicit Direct Task route outcome. | Start with fixture/projection; update API contract only when backend work starts. |
| Topbar removal hides important status. | Move status into Session Work Area header/status row before removing topbar. |
| Detail Panel loses context. | Keep selected object model unchanged in early slices. |
| Markdown rendering introduces XSS or inconsistent display. | Use a single shared sanitized renderer and ban raw HTML/script execution. |

---

## 10. Acceptance Criteria

The frontend implementation can be considered accepted when:

1. Main Page no longer uses a persistent topbar.
2. Workspace Rail, Session Work Area, and Detail Panel are visually distinct.
3. Product identity and workspace/session navigation are available in the rail.
4. Session title/status and event status remain visible.
5. Conversation / Plan switch exists and preserves selected Task state.
6. Read-only answer, Direct Task, and Plan required can be inspected in mock
   scenarios.
7. Existing ASK, confirmation, stop, retry, result, file summary, and audit
   paths still work.
8. Desktop and narrow viewport checks pass without incoherent overlap.
9. Relevant unit tests and `npm run build` pass.
10. Conversation, Activity, and Detail result Markdown render through the shared
    safe renderer.
11. Product/docs closure records the implementation result.

---

## 11. Recommended First Code Slice

Start with C0 and C1 only:

```text
Maintainability gate
  -> MainPageShell extraction
  -> preserve current behavior
  -> tests
```

Do not implement Conversation routing visuals until the shell extraction is
stable. This keeps the layout migration reversible and reduces the chance of
mixing visual restructuring with runtime behavior changes.

---

## 12. Implementation Notes

Implemented on 2026-06-16 as a frontend-only slice.

Completed:

1. Removed the persistent Main Page topbar from the normal, loading, error, and
   no-session shells.
2. Moved compact Plato identity, workspace/session navigation, and utility
   controls into the Workspace Rail.
3. Moved project/session/status context into the Session Work Area header.
4. Added a center-column `Conversation` / `Plan & Progress` layer switch.
5. Added the first Conversation layer projection using existing session
   messages and runtime activity items.
6. Preserved existing Plan & Progress, task selection, Details, ASK,
   confirmation, stop/retry, result, file summary, and audit behaviors.
7. Added mock fixtures and scenario catalog coverage for:
   - read-only answer;
   - Direct Task;
   - Plan required through the existing draft-ready state.
8. Added mock URL inspection support:
   - `/?stateId=s15-read-only-answer`;
   - `/?stateId=s16-direct-task`;
   - `/?stateId=s3-draft-ready`.

Validation:

```text
cd frontend
npm run test -- mockPlatoApi mockScenarios MainPageWorkbench
npm run test -- MainPage App AppRouting MainPageRoute mainPageViewModel
npm run test -- MainPageRoute mockPlatoApi mockScenarios MainPageWorkbench
npm run build
```

Browser smoke:

- default mock state: old topbar absent, rail brand visible, Plan & Progress
  selected;
- `s15-read-only-answer`: Conversation selected, answer visible, no task row;
- `s16-direct-task`: single running task visible, base plan rows absent;
- narrow viewport `390x844`: no horizontal overflow, core controls remain
  reachable.

Known follow-up:

Direct Task currently defaults to `Plan & Progress` because the real snapshot
contract does not yet expose an explicit route outcome. The mock state is
inspectable and semantically correct, but changing the default layer for real
Direct Task sessions should wait for a small UI API contract addition.

Added on 2026-06-17:

- `C5A. Shared Safe Markdown Renderer` is now a planned follow-up slice.
- This slice should land before expanding Conversation and Activity into
  richer natural-language surfaces, because those surfaces will render longer
  model-authored Markdown by default.
