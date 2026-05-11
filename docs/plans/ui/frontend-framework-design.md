# Frontend Framework Technical Design

> Status: in_progress
> Last Updated: 2026-05-11
> Scope: UI-only implementation plan
> Boundary: frontend reaches the backend only through API contracts; backend implementation is out of scope for this session
> Related: [Task-first UI overview](../task-first-ui-interaction.md), [UI API interfaces](ui-api-interfaces.md), [Information architecture](information-architecture.md), [Visual reference](visual-reference.md)

---

## 1. Goal

TaskWeavn now has a Task-first UI blueprint, interaction concepts, API sketches, and early visual references. The next UI work should not start with complex execution details. It should first create a visible frontend shell with enough real structure to make the product feel coherent:

- Session frame;
- Task Tree / topology area;
- selected Task detail;
- Session Message Stream;
- Task-scoped message projection;
- confirmation action placeholder;
- global vs task-scoped input mode.

This document defines the frontend framework choice, module layout, API boundary, and incremental development plan.

---

## 2. Product Direction For The First UI

The first frontend should prove the product shape, not the full backend behavior.

Minimum visible experience:

```text
┌────────────────────────────────────────────────────────────┐
│ Header: session, run state, autonomy, connection status     │
├─────────────────┬──────────────────────┬───────────────────┤
│ Task Tree       │ Selected Task Detail │ Session Stream    │
│ / Topology      │ + Task Messages      │ + Confirmations   │
├─────────────────┴──────────────────────┴───────────────────┤
│ Input: global mode or task-scoped mode                       │
└────────────────────────────────────────────────────────────┘
```

First version rules:

- Use mock API data first.
- Keep UI state local and inspectable.
- Do not implement backend logic in the frontend.
- Do not build a chat-only interface.
- Keep Task cards, Task topology, messages, and confirmations visible from day one.

---

## 3. Framework Selection

### 3.1 Recommendation

Use:

| Layer | Choice | Reason |
|---|---|---|
| App framework/build | Vite + React + TypeScript | Fast dev server, simple client app, no backend coupling. |
| Routing | TanStack Router | Type-safe route/search params for session/task selection. |
| Server state | TanStack Query | API fetching, caching, invalidation, optimistic updates. |
| Local UI state | Zustand or small store module | Selected task, panel state, local drafts, filters. |
| Styling | Tailwind CSS + CSS variables | Fast layout work, easy design tokens, constrained UI language. |
| Accessible primitives | Radix Primitives | Dialog, tabs, select, tooltip, menu, scroll/focus primitives. |
| Icons | lucide-react | Consistent icon language for tools, status, actions. |
| API mock | Typed mock adapter first; MSW optional later | Lets UI develop before server endpoints exist. |
| Tests | Vitest + React Testing Library + Playwright later | Unit behavior first, visual/e2e once shell exists. |

### 3.2 Why Vite + React, not Next.js first

TaskWeavn UI is an authenticated app-like workspace, not a public content site. The backend will be implemented separately, and this UI session should stop at API contracts. That makes a client app a better first step:

- no SSR requirement yet;
- no SEO requirement;
- no full-stack routing requirement;
- lower scaffold complexity;
- easier to run as a local UI prototype against mock data.

Next.js or another full-stack React framework can be reconsidered later if deployment, auth, SSR, or server-rendered route data becomes important.

### 3.3 Why not a heavy component library

TaskWeavn needs a distinct Task-first product surface. A heavy design kit can make the UI look generic too early. The first system should use:

- Radix for behavior and accessibility;
- Tailwind/CSS variables for TaskWeavn-specific visual language;
- small local components for Task cards, message rows, confirmations, and topology.

---

## 4. Proposed Frontend Directory

First implementation should create a separate frontend root:

```text
frontend/
  package.json
  index.html
  vite.config.ts
  tsconfig.json
  src/
    main.tsx
    app/
      App.tsx
      router.tsx
      providers.tsx
      layout/
    api/
      client.ts
      contracts.ts
      mock/
    domain/
      task.ts
      message.ts
      confirmation.ts
      fileChange.ts
      session.ts
    features/
      session-shell/
      task-tree/
      task-detail/
      task-messages/
      session-stream/
      confirmations/
      composer/
    design/
      tokens.css
      primitives/
      icons.ts
    test/
      fixtures/
```

Rules:

- `api/contracts.ts` mirrors [ui-api-interfaces.md](ui-api-interfaces.md).
- `domain/` contains frontend domain types, not backend database schemas.
- `features/` owns UI behavior and composition.
- `design/` owns reusable UI primitives and tokens.
- Mock data lives under `api/mock/` or `test/fixtures/`, never mixed into production components.

---

## 5. API Boundary

The frontend talks to backend only through API contracts.

### 5.1 First API Client Shape

```ts
export interface TaskWeavnApi {
  getSessionOverview(sessionId: SessionId): Promise<SessionOverview>
  listTaskTrees(sessionId: SessionId): Promise<TaskTreeView[]>
  getTaskNode(sessionId: SessionId, taskId: TaskId): Promise<TaskNodeDetail>
  listSessionMessages(
    sessionId: SessionId,
    filters?: SessionMessageFilters,
  ): Promise<SessionMessagePage>
  listTaskMessages(
    sessionId: SessionId,
    taskId: TaskId,
    scope?: TaskMessageScope,
  ): Promise<SessionMessagePage>
  listPendingConfirmations(
    sessionId: SessionId,
    filters?: ConfirmationFilters,
  ): Promise<ConfirmationActionView[]>
  getTaskFileChanges(
    sessionId: SessionId,
    taskId: TaskId,
    options?: { recursive?: boolean },
  ): Promise<TaskFileChangeSummary[]>
  appendSessionMessage(request: AppendSessionMessageRequest): Promise<CommandResult>
  appendTaskMessage(request: AppendTaskMessageRequest): Promise<CommandResult>
  updateTaskNode(request: UpdateTaskNodeRequest): Promise<CommandResult>
  resolveConfirmation(request: ResolveConfirmationRequest): Promise<CommandResult>
  subscribeSessionEvents(
    sessionId: SessionId,
    cursor?: Cursor,
    onEvent?: (event: SessionEvent) => void,
  ): SessionEventSubscription
}
```

### 5.2 API Implementation Modes

| Mode | Purpose | When |
|---|---|---|
| `MockTaskWeavnApi` | Develop visible UI immediately. | First frontend slice. |
| `HttpTaskWeavnApi` | Connect to backend REST/RPC later. | When server API exists. |
| `EventSource/WebSocket adapter` | Real-time session events. | After backend event endpoint exists. |

The UI code should depend on `TaskWeavnApi`, not on `fetch` directly.

---

## 6. State Model

### 6.1 Server State

Use TanStack Query for API-backed state:

| Query Key | Source |
|---|---|
| `["session", sessionId, "overview"]` | `getSessionOverview` |
| `["session", sessionId, "taskTrees"]` | `listTaskTrees` |
| `["session", sessionId, "task", taskId]` | `getTaskNode` |
| `["session", sessionId, "messages", filters]` | `listSessionMessages` |
| `["session", sessionId, "taskMessages", taskId, scope]` | `listTaskMessages` |
| `["session", sessionId, "confirmations", filters]` | `listPendingConfirmations` |
| `["session", sessionId, "fileChanges", taskId, recursive]` | `getTaskFileChanges` |

Real-time events invalidate or patch these query keys.

### 6.2 Client UI State

Keep this outside server state:

- selected Task ID;
- expanded Task IDs;
- active panel/tab;
- input mode: `global` or `task_scoped`;
- local draft text;
- local filters;
- unread markers;
- panel layout preferences.

First implementation can use a small store:

```ts
type UiState = {
  selectedTaskId: TaskId | null
  expandedTaskIds: Set<TaskId>
  inputMode: "global" | "task_scoped"
  sessionMessageFilter: SessionMessageFilterState
  taskMessageScope: "direct" | "subtree"
}
```

---

## 7. Routes

Use a small route tree first:

| Route | Purpose |
|---|---|
| `/` | Redirect to demo or last session. |
| `/sessions/$sessionId` | Main Task-first workspace. |
| `/sessions/$sessionId/tasks/$taskId` | Same workspace, selected Task encoded in URL. |
| `/dev/mock` | Optional mock data playground. |

URL should preserve:

- session;
- selected task;
- task/message filters when useful.

This makes screenshots, debugging, and user tests easier.

---

## 8. Component Slices

### Slice UI-1: Static App Shell

Goal: visible structure with mock data, no real API.

Build:

- `AppShell`
- `SessionHeader`
- `TaskTreePanel`
- `TaskDetailPanel`
- `SessionStreamPanel`
- `ComposerBar`

Acceptance:

- The main Task-first layout is visible.
- User can select a mock Task.
- Detail panel and task-scoped messages update from local mock data.

### Slice UI-2: Design Tokens And Primitives

Goal: stop ad-hoc CSS before it spreads.

Build:

- color tokens;
- spacing scale;
- typography scale;
- button/icon button primitives;
- badge/status primitives;
- panel/card primitives;
- tooltip/menu/dialog primitives through Radix.

Acceptance:

- Task card, message row, confirmation prompt, and toolbar share primitives.
- UI does not look like a generic landing page or chat app.

### Slice UI-3: API Contract Client

Goal: front-end API boundary is real even before backend exists.

Build:

- `TaskWeavnApi` interface;
- mock implementation;
- query hooks;
- command mutation hooks;
- event subscription abstraction.

Acceptance:

- Components call hooks, not fixtures directly.
- Switching mock API to HTTP API requires replacing provider wiring, not rewriting components.

### Slice UI-4: Core Task Interactions

Goal: make the first user flows testable.

Build:

- global input -> mock Task Tree generation;
- task selection -> task-scoped input mode;
- confirmation action card -> resolve option;
- task message projection over session messages;
- recursive file summary display.

Acceptance:

- User can see the difference between global and task-scoped input.
- User can resolve a mock confirmation and see the message stream update.
- Parent Task file summary includes child changes.

### Slice UI-5: Visual Hardening And E2E

Goal: make the shell stable enough for real user testing.

Build:

- responsive layout;
- keyboard navigation for main panels;
- loading/empty/error states;
- Playwright smoke tests;
- screenshot checks for desktop and narrow viewport.

Acceptance:

- Main shell renders without overlap at desktop and tablet widths.
- Empty session, populated session, pending confirmation, and completed task states are covered.

---

## 9. UI Design Rules For Implementation

These rules matter because this is a work surface, not a marketing site:

- No landing page as the first screen.
- No hero section.
- No decorative cards inside cards.
- Use dense but readable operational layout.
- Use icons for tool actions where possible.
- Keep cards at small radius; use status color sparingly.
- Make Task status, pending confirmations, and selected Task immediately scannable.
- Do not hide confirmations inside ordinary chat messages.
- Keep Session Message Stream and Task Message View visually related but distinct.
- Finished Task Nodes are read-only.
- Running Task Nodes accept guidance but not structural edits.

---

## 10. First Implementation Branch Plan

Suggested branch:

```text
codex/ui-frontend-shell
```

First branch scope:

1. Scaffold `frontend/` with Vite + React + TypeScript.
2. Add Tailwind/CSS variable setup.
3. Add initial route shell.
4. Add typed mock API.
5. Render:
   - Task Tree;
   - Task Detail;
   - Session Stream;
   - Composer.
6. Add one small Playwright or component-level smoke test if tooling is ready.

Non-goals:

- no backend server;
- no auth;
- no real WebSocket;
- no full diff viewer;
- no complex drag-and-drop;
- no multi-agent execution UI yet.

Current branch:

- `codex/ui-frontend-shell`
- Initial scaffold created under `frontend/`
- First implementation uses `MockTaskWeavnApi`

---

## 11. Open Questions

These do not block the first shell:

1. Should the UI be eventually embedded in a desktop shell, served by the Python backend, or deployed as a separate web app?
2. Should Task topology become a graph/canvas later, or remain tree-first with a separate map mode?
3. Should API schemas be generated from OpenAPI later, or kept as hand-written shared contracts?
4. Should the mock API use MSW once HTTP paths are stable?
5. Should selected Task be encoded only in URL, or also in persisted local session preferences?

---

## 12. References

Official docs reviewed for stack selection:

- [React: Creating a React App](https://react.dev/learn/start-a-new-react-project)
- [Vite: Getting Started](https://vite.dev/guide/)
- [TanStack Router: Type Safety](https://tanstack.com/router/v1/docs/guide/type-safety)
- [TanStack Query: Overview](https://tanstack.com/query/v4/docs/react/overview)
- [Tailwind CSS: Utility-first styling](https://tailwindcss.com/docs/utility-first)
- [Radix Primitives: Introduction](https://www.radix-ui.com/primitives/docs/overview/introduction)
