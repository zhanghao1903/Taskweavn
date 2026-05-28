# Feature Plan: Main Page Frontend Runtime Integration

> Status: in_progress / checkpoint submitted
> Type: frontend runtime / UI-backend integration
> Last Updated: 2026-05-27
> Parent Plan: [Main Page Real Backend Integration](main-page-real-backend-integration.md)
> Gap: [Main Page real backend integration](../../gaps/README.md)
> Architecture: [UI And Backend Communication](../../architecture/ui-backend-communication.md), [Task Domain/UI Model Separation](../../architecture/task-domain-ui-model-separation.md), [Authoring Domain](../../architecture/authoring-domain.md)
> Product: [Plato Main Page UX Flow](../../product/plato-main-page-ux-flow.md), [Plato UI API Contract](../../product/plato-ui-api-contract.md), [Plato Frontend Technical Design](../../product/plato-frontend-technical-design.md)
> Technical Design: [中文详细技术方案](main-page-frontend-runtime-integration-technical-design.zh-CN.md)
> Checkpoint Record: [Main Page Frontend Runtime Integration](../../releases/main-page-frontend-runtime-integration.md)

---

## 0. Progress

| Date | Slice | Status | Notes |
|---|---|---|---|
| 2026-05-21 | Slice 1 — Runtime adapter boundary cleanup | done | Extracted stable Main Page runtime adapter types into `frontend/src/pages/main-page/runtime/adapter.ts`; moved HTTP metadata derivation into `runtime/metadata.ts`; HTTP adapter no longer imports fixture types. |
| 2026-05-21 | Slice 2 — HTTP mode gating and session-centric snapshot query | done | Added adapter runtime mode/config, session-centric HTTP query keys, HTTP-hidden StatePicker, and snapshot-identity-based local state reset. |
| 2026-05-21 | Slice 3 — Command response lifecycle | done | Added central command response handling; accepted commands now clear local pending/error state and refetch backend facts instead of creating durable synthetic messages. |
| 2026-05-21 | Slice 4 — Main Page command coverage | done | Added adapter coverage for generate/update/publish commands; empty-session input now generates TaskTree; draft TaskTree can be published from Main Page. |
| 2026-05-21 | Slice 5 — Event router and invalidation | done | Added conservative event router; all canonical events refetch by default, `message.appended` no longer creates local message cards, and resync events use a loop guard. |
| 2026-05-21 | Slice 6 — Integration smoke and docs closure | checkpoint | Frontend tests/build/lint pass; sidecar health/snapshot pass through loopback API; runtime logging exposed real browser issues and the stage PR fixed the default `fetch` receiver bug. This still does not close the Main Page real-backend gap. |
| 2026-05-27 | P7.1A — Main Page route/runtime compatibility wrapper | done | Added `MainPageRoute` so `App` composes runtime env into the current `MainPage` without changing visible behavior. API mock happy path is deferred. |
| 2026-05-27 | P7.1B — Wrapper boundary and next-step decision | done | Documented `MainPageRoute` ownership boundaries and decided to centralize status presentation mapping before P7.2 component extraction. |
| 2026-05-27 | P7.1C — Status presentation mapping | done | Moved session, task, message, event, file-change, confirmation option, and audit verdict label/tone derivation into `mainPageSelectors.ts` without changing visible UI. |
| 2026-05-27 | P7.2 — Light presentation component extraction | in_progress | Started low-risk extraction with `TaskNodeCard` and `SessionMessageCard`; panels still own data flow, selection state, and layout. |

---

## 1. Problem / Gap

The backend side of Main Page real-backend integration is now ahead of the
frontend runtime:

- `taskweavn plato-sidecar` and `taskweavn plato-dev` can start a local sidecar
  target.
- `MainPageSidecarApp` composes SessionManager, MessageStream, TaskBus,
  authoring services, UI gateways, HTTP transport, and stdlib sidecar server.
- `frontend/src/shared/api/platoApi.ts` can call the documented HTTP routes and
  subscribe to default plus named SSE events.
- backend-generated UI contract JSON fixtures are consumed by frontend tests.

But the Main Page itself still behaves like a fixture-compatible prototype:

- `MainPage` query identity is `["main-page-snapshot", stateId]`, not session id.
- `StatePicker` is always visible, including HTTP mode.
- the HTTP adapter bridges real snapshots into `mockPlatoApi` metadata types.
- accepted commands create local synthetic messages/decisions instead of waiting
  for backend facts.
- only `message.appended` and `session.resync_required` affect the page.
- `message.appended` page handling expects `title/body/kind` in payload, while
  backend events intentionally carry only lightweight invalidation data.

This plan finishes the frontend runtime convergence: Main Page HTTP mode should
be driven by session snapshots, command responses, and `UiEvent` invalidation,
while keeping fixture scenarios available for design/dev review.

---

## 2. Current Code Facts

| Area | Current fact | Risk |
|---|---|---|
| Runtime mode | `VITE_PLATO_API_MODE=http` creates an HTTP adapter when `VITE_PLATO_SESSION_ID` exists. | Real mode is env-only and cannot create/select sessions in UI. |
| Snapshot query | `MainPage` uses `stateId` as query key. | HTTP mode still inherits fixture identity and reset behavior. |
| Adapter boundary | `MainPageAdapter` lives in `mockPlatoApi.ts` and does not expose all `PlatoApi` commands. | Mock/prototype concerns leak into real runtime. |
| Commands | Session input, Task input, and confirmation response are wired. | Generate tree, update node, and publish tree exist in `PlatoApi` but are not page actions. |
| Command result | `onSuccess` stores local input/confirmation messages. | UI can diverge from backend truth. |
| Events | Low-level client subscribes to all canonical event names. | Main Page ignores most event types. |
| Message events | Page maps event payload into a message card. | Backend `message.appended` does not guarantee card title/body. |
| Dev scenarios | 9 Figma baseline states are first-class. | Good for design review, but should not define HTTP runtime behavior. |

---

## 3. Goals

1. Make HTTP mode session-centric.
2. Keep fixture mode available for visual QA and product discussion.
3. Separate Main Page runtime adapter types from mock fixture implementation.
4. Use backend snapshots as the source of TaskTree, messages, confirmations,
   result, and file-change truth.
5. Treat `CommandResponse` as accepted/rejected plus refresh hints, not as final
   UI state.
6. Treat `UiEvent` as invalidation/refetch hint by default.
7. Hide or dev-gate prototype-only controls in HTTP mode.
8. Add tests that prove the page can run against contract-shaped backend facts.

---

## 4. Non-goals

- Do not redesign visual layout.
- Do not implement Electron packaging.
- Do not add full Project/Workflow/Session creation UI.
- Do not implement durable SSE replay.
- Do not implement TaskBus claim/execute/complete lifecycle.
- Do not implement the Audit Page.
- Do not solve multi-user editing or remote deployment.
- Do not remove fixture scenarios; they remain useful as dev/demo states.

---

## 5. Product Behavior Target

### 5.1 Fixture mode

Fixture mode remains the default when no HTTP env is set:

```text
VITE_PLATO_API_MODE missing or "mock"
  -> use 9-state fixture adapter
  -> show StatePicker
  -> keep fast product/visual review loop
```

### 5.2 HTTP mode

HTTP mode is a real runtime:

```text
VITE_PLATO_API_MODE=http
VITE_PLATO_API_BASE_URL=http://127.0.0.1:<port>
VITE_PLATO_SESSION_ID=<session-id>
  -> load session snapshot by session id
  -> subscribe to session events by snapshot cursor
  -> submit commands to sidecar
  -> refresh from backend facts
  -> hide StatePicker by default
```

### 5.3 User-visible convergence rule

Accepted commands may show a short pending affordance, but the durable visible
objects must converge through backend facts:

- TaskTree from `MainPageSnapshot.taskTree`;
- messages from `MainPageSnapshot.messages`;
- confirmations from `MainPageSnapshot.pendingConfirmations`;
- results from `MainPageSnapshot.result`;
- file changes from `MainPageSnapshot.fileChangeSummary`.

---

## 6. Runtime Design Direction

### 6.1 Split runtime adapter from mock fixtures

Move the stable adapter boundary out of `mockPlatoApi.ts`.

Target shape:

```text
frontend/src/pages/main-page/runtime/
  adapter.ts
  mockAdapter.ts
  httpAdapter.ts
  eventRouter.ts
  commandRefresh.ts
```

`mockAdapter.ts` may continue to wrap fixtures. `httpAdapter.ts` should wrap
`PlatoApi` without importing fixture state metadata.

### 6.2 Separate UI metadata from fixture metadata

The page needs derived UI metadata in both modes:

- top status label/tone;
- default selected TaskNode;
- detail panel default mode;
- input scope label.

But this metadata should be derived from `MainPageSnapshot`, not from fixture
state ids in HTTP mode.

### 6.3 Session-centric query key

HTTP mode should use a session-centric query key:

```ts
["main-page", "snapshot", sessionId]
```

Mock mode may still use:

```ts
["main-page", "fixture", stateId]
```

This is the small hinge that keeps design fixtures and real runtime from
stepping on each other.

### 6.4 Conservative event handling

Default rule:

```text
unknown or non-patch event -> invalidate/refetch snapshot
```

MVP event strategy:

| Event | First behavior |
|---|---|
| `session.resync_required` | Refetch snapshot, with loop guard. |
| `session.status_changed` | Refetch snapshot. |
| `task.tree.changed` | Refetch snapshot. |
| `task.node.changed` | Refetch snapshot. |
| `message.appended` | Refetch snapshot unless payload contains complete display fields. |
| `confirmation.created` | Refetch snapshot. |
| `confirmation.resolved` | Refetch snapshot and clear matching pending command. |
| `result.updated` | Refetch snapshot. |
| `file_changes.updated` | Refetch snapshot. |
| `audit.summary_updated` | Refetch snapshot or leave for Audit Page if no Main Page field depends on it. |
| `command.completed` | Clear matching pending command; refetch snapshot. |
| `command.failed` | Show command error; refetch only if retryable or affected scopes say so. |

This is intentionally boring. A precise patch layer can come later once event
payloads are richer and stable.

### 6.5 Resync-only sidecar loop guard

The current sidecar can use `ResyncOnlyEventSource`. That source may emit
`session.resync_required` immediately because durable replay is not available.

The frontend must avoid a refetch-subscribe-resync loop:

- track the last resync cursor/reason;
- do not immediately resubscribe infinitely for the same cursor;
- after one successful refetch, mark event status as `connected_limited` or
  equivalent if the event source reports replay unavailable;
- continue allowing manual commands to invalidate/refetch.

---

## 7. Implementation Slices

### Slice 1 — Runtime adapter boundary cleanup ✅ Done

Output:

- extract `MainPageAdapter` types from `mockPlatoApi.ts`;
- create runtime metadata derivation helpers that work from `MainPageSnapshot`;
- keep current mock adapter behavior unchanged;
- HTTP adapter no longer depends on fixture state metadata except for optional
  dev labels.

Acceptance:

- existing fixture tests pass;
- `httpMainPageAdapter.test.ts` still proves snapshot loading;
- no production runtime type imports `fixtures.ts`.

Completion notes:

- `frontend/src/pages/main-page/runtime/adapter.ts` now owns `MainPageAdapter`,
  command function types, metadata shape, and runtime snapshot shape.
- `frontend/src/pages/main-page/runtime/metadata.ts` derives UI metadata from
  `MainPageSnapshot`.
- `frontend/src/pages/main-page/httpMainPageAdapter.ts` delegates API calls and
  imports no fixture-only types.
- Verified with `npm test`, `npm run build`, and `npm run lint`.

### Slice 2 — HTTP mode gating and session-centric snapshot query ✅ Done

Output:

- `MainPage` receives runtime mode/config from adapter or runtime env;
- query key uses `sessionId` in HTTP mode and `stateId` in mock mode;
- `StatePicker` hidden in HTTP mode unless a dev flag enables it;
- selected task/detail/input local state resets only when session/snapshot
  identity changes, not on irrelevant fixture state changes.

Acceptance:

- HTTP mode does not render the `State` selector by default;
- snapshot fetches are keyed by session id;
- fixture mode still exposes the 9 states.

Completion notes:

- `MainPageAdapter` now carries `runtimeKind`, `sessionId`, and
  `showStatePicker`.
- `mainPageSnapshotQueryKey()` keys mock mode by fixture state and HTTP mode by
  session id.
- `mainPageSnapshotIdentity()` keeps local UI reset scoped to fixture state or
  HTTP session identity.
- HTTP adapters hide `StatePicker` by default; mock adapters still show the 9
  Figma baseline states.
- Verified with `npm test`, `npm run build`, and `npm run lint`.

### Slice 3 — Command response lifecycle ✅ Done

Output:

- central `handleCommandResponse` helper;
- accepted commands create pending command entries, not final facts;
- rejected commands show structured error;
- `refresh.affectedScopes` maps to query invalidation;
- local synthetic messages removed or clearly marked as transient pending UI.

Acceptance:

- session input and task input refetch from backend after acceptance;
- confirmation response does not permanently mutate TaskNode status locally;
- command errors remain visible and retryable when appropriate.

Completion notes:

- `frontend/src/pages/main-page/runtime/commandRefresh.ts` centralizes accepted
  versus rejected command handling.
- Confirmation, session input, and task input commands now refetch through the
  existing snapshot query after accepted responses.
- Frontend no longer appends durable synthetic confirmation or input messages
  after accepted commands.
- Verified with `npm test`, `npm run build`, and `npm run lint`.

### Slice 4 — Main Page command coverage ✅ Done

Output:

- no TaskTree + input can call `generateTaskTree`;
- draft TaskNode edits can call `updateTaskNode` when structured card edits are introduced;
- draft tree publish action can call `publishTaskTree`;
- existing `appendSessionInput`, `appendTaskInput`, and `resolveConfirmation`
  remain wired.

Acceptance:

- all `PlatoApi` Main Page commands are reachable through the adapter boundary;
- UI only exposes actions allowed by snapshot permissions/status;
- tests cover command request payloads.

Completion notes:

- `MainPageAdapter` now exposes `generateTaskTree`, `updateTaskNode`, and
  `publishTaskTree` in addition to existing input and confirmation commands.
- Empty-session input uses `generateTaskTree` instead of generic session input.
- Draft TaskTrees expose a `Publish TaskTree` action that submits
  `publishTaskTree` and refetches backend facts.
- Structured TaskNode edit UI is still a later surface, but the runtime adapter
  boundary already exposes `updateTaskNode`.
- Verified with `npm test`, `npm run build`, and `npm run lint`.

### Slice 5 — Event router and invalidation ✅ Done

Output:

- `eventRouter.ts` maps `UiEvent` to refetch/error/pending-command actions;
- `message.appended` handles lightweight backend payload correctly;
- `session.resync_required` includes loop guard;
- unsupported canonical events fail safe by refetching snapshot.

Acceptance:

- backend fixture `ui_event.message_appended.json` triggers safe refetch behavior;
- `confirmation.resolved`, `task.tree.changed`, and `command.failed` are covered;
- no event creates durable UI facts from incomplete payloads.

Completion notes:

- `frontend/src/pages/main-page/runtime/eventRouter.ts` maps events to
  refetch/error actions.
- `message.appended` is treated as an invalidation hint, not a complete message
  card payload.
- `session.resync_required` uses a cursor/reason loop guard.
- Unsupported canonical events fail safe by refetching snapshot facts.
- Verified with `npm test`, `npm run build`, and `npm run lint`.

### Slice 6 — Integration smoke and docs closure ✅ Done With Caveat

Output:

- focused frontend tests for HTTP-mode runtime behavior;
- optional browser smoke with `taskweavn plato-dev`;
- update parent plan, gap registry, and release notes when accepted.

Acceptance:

- `npm test` and `npm run build` pass;
- focused backend/frontend integration tests pass;
- manual or automated `plato-dev` smoke proves the page can load a sidecar
  snapshot and submit at least one command.

Completion notes:

- `npm test`, `npm run build`, and `npm run lint` pass from `frontend/`.
- `taskweavn plato-dev` starts a temporary sidecar and Vite dev server.
- Sidecar `health` and `snapshot` endpoints return valid JSON over loopback.
- The Codex in-app browser can load the Vite page and confirms HTTP mode hides
  the fixture StatePicker, but this browser context reports no `fetch`,
  `Response`, `Headers`, or `XMLHttpRequest`, so the page cannot complete the
  HTTP snapshot request inside that browser. A real Chrome/Safari/Electron smoke
  remains a follow-up.

---

## 8. Testing Strategy

### 8.1 Unit / component tests

- fixture mode still renders 9 baseline states;
- HTTP mode hides `StatePicker`;
- snapshot query key uses session id;
- command accepted creates pending + invalidation;
- command rejected surfaces `ApiError.message`;
- event router maps every canonical `UiEventType`;
- lightweight `message.appended` event does not invent card title/body.

### 8.2 Contract tests

- frontend consumes backend fixture `MainPageSnapshot`;
- frontend consumes backend fixture `CommandResponse`;
- frontend consumes backend fixture `UiEvent`;
- contract fixture events drive the same router used by Main Page.

### 8.3 Smoke tests

Manual first:

```text
uv run taskweavn plato-dev --workspace ./plato-workspace --session-name Demo
open http://127.0.0.1:5173
```

Automated later if stable:

- start sidecar with stub LLM;
- start Vite preview/dev server;
- open Main Page with Browser/Playwright;
- assert snapshot loaded;
- submit session input;
- assert backend-refreshed message or TaskTree appears.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| Event loop caused by resync-only source | Add cursor/reason loop guard and fallback to manual refetch. |
| Frontend over-patches incomplete event payload | Treat events as invalidation by default. |
| Fixture mode breaks during cleanup | Keep mock adapter tests and state catalog tests as guardrails. |
| HTTP mode still depends on fixture metadata | Move adapter types and metadata derivation into runtime files. |
| Command UI diverges from backend | Remove durable synthetic messages; refresh from snapshot. |
| Too much frontend refactor in one slice | Slice adapter cleanup, query identity, commands, and event router separately. |

---

## 10. Completion Criteria

This plan is done when:

- HTTP mode loads and refreshes by session id;
- prototype `StatePicker` is hidden or dev-gated in HTTP mode;
- accepted commands converge through backend snapshot/event facts;
- all canonical events have a safe router behavior;
- backend lightweight `message.appended` events do not produce fake complete
  message cards;
- fixture mode remains useful for product and visual review;
- documentation and release records reflect the new factual state.
