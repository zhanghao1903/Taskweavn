# Checkpoint: Main Page Frontend Runtime Integration

> Status: checkpoint / gap still open
> Date: 2026-05-21
> Work Stream: Phase 3E — Task-first UI
> Related Plan: [Main Page Frontend Runtime Integration](../plans/feature/main-page-frontend-runtime-integration.md)
> Technical Design: [Main Page Frontend Runtime Integration Technical Design](../plans/feature/main-page-frontend-runtime-integration-technical-design.zh-CN.md)
> Product: [Main Page UX Flow](../product/plato-main-page-ux-flow.md), [UI API Contract](../product/plato-ui-api-contract.md)
> Interaction Facts: [Main Page Interaction Model](../interaction-model/main-page.md), [External Calls Registry](../interaction-model/external-calls.md)

---

## 1. Summary

This checkpoint moves Plato Main Page from a fixture-compatible prototype toward a real session-centric runtime.

The frontend still preserves the 9-state fixture loop for product and visual review, but HTTP mode is no longer driven by fixture state identity or local synthetic truth. Runtime behavior now converges through backend snapshots, command responses, and conservative event invalidation.

This is not a completed release for the Main Page real-backend gap. It is a stage submission that proves core wiring and diagnostics while leaving substantial Product 1.0 work open.

---

## 2. Checkpoint Scope

### 2.1 Runtime Adapter Boundary

Added `frontend/src/pages/main-page/runtime/` with:

- `adapter.ts` for stable Main Page adapter and command function types;
- `metadata.ts` for deriving UI metadata from `MainPageSnapshot`;
- `commandRefresh.ts` for accepted/rejected command response handling;
- `eventRouter.ts` for conservative `UiEvent` invalidation behavior.

`httpMainPageAdapter.ts` no longer imports fixture-only types.

### 2.2 HTTP Mode Gating

`MainPageAdapter` now exposes:

- `runtimeKind`;
- `sessionId`;
- `showStatePicker`.

Mock mode still shows the 9-state `StatePicker`. HTTP mode hides it by default and keys snapshot queries by session id:

```text
mock -> ["main-page", "fixture", stateId]
http -> ["main-page", "snapshot", sessionId]
```

Local UI reset is now based on snapshot identity, so same-session refetches do not wipe selected TaskNode or input state.

### 2.3 Command Lifecycle

Accepted commands no longer create durable frontend-only facts.

Implemented behavior:

- accepted confirmation responses refetch backend facts;
- accepted session input refetches backend facts;
- accepted task input refetches backend facts;
- rejected command responses show structured error messages;
- frontend synthetic confirmation/input messages were removed.

### 2.4 Main Page Command Coverage

The Main Page adapter now exposes the full Main Page command set from `PlatoApi`:

- append session input;
- generate TaskTree;
- update TaskNode;
- append task input;
- publish TaskTree;
- resolve confirmation.

Visible UI coverage added:

- empty-session input calls `generateTaskTree`;
- draft TaskTree exposes `Publish TaskTree`;
- publish command uses `startImmediately: true` and refetches backend facts.

Structured TaskNode edit UI remains a later surface, but the runtime adapter boundary is ready.

### 2.5 Event Invalidation

`UiEvent` handling is now refetch-first.

Key behavior:

- `message.appended` is treated as a lightweight invalidation hint;
- event payloads no longer create complete local message cards;
- `session.resync_required` uses a cursor/reason loop guard;
- `command.failed` surfaces an error and refetches;
- unsupported canonical events fail safe by refetching snapshot facts.

### 2.6 Interaction Model Docs

Added UI interaction fact docs:

- `docs/interaction-model/README.md`;
- `docs/interaction-model/main-page.md`;
- `docs/interaction-model/external-calls.md`;
- `docs/interaction-model/page-template.md`.

These docs now define page-level allowed interactions and centralize UI-triggered external calls.

---

## 3. Validation

Final validation:

- `npm test` from `frontend/` — 12 test files passed, 63 tests passed.
- `npm run build` from `frontend/` — passed.
- `npm run lint` from `frontend/` — passed.
- `git diff --check` — passed.
- `uv run taskweavn plato-dev --help` — passed.
- `taskweavn plato-dev` temporary sidecar smoke:
  - sidecar started;
  - Vite dev server started on a fallback port;
  - sidecar `health` endpoint returned valid JSON;
  - sidecar `snapshot` endpoint returned valid `MainPageSnapshot` JSON.

Browser smoke caveat:

- Codex in-app browser loaded the Vite page and confirmed HTTP mode hides the fixture `StatePicker`.
- The Codex in-app browser page context reported no `fetch`, `Response`, `Headers`, or `XMLHttpRequest`.
- Because of that browser-runtime limitation, the page could not complete the sidecar snapshot request inside Codex's in-app browser.

This should be re-smoked in a normal browser or Electron shell before calling the user-facing local runtime fully verified.

---

## 4. Follow-ups Before Gap Closure

- Run a real Chrome/Safari/Electron smoke against `taskweavn plato-dev`.
- Add a user-facing session creation/selection flow instead of relying on env-provided `VITE_PLATO_SESSION_ID`.
- Implement structured TaskNode edit controls on top of the now-exposed `updateTaskNode` command.
- Add richer pending command UI if backend events take noticeable time.
- Harden message and confirmation UX beyond conservative refetch behavior.
- Implement file-change summary and audit/trust projections in the Main Page flow.
- Decide durable SSE/replay behavior or a clear replacement for broader user testing.
- Keep `docs/interaction-model/` updated whenever Main Page controls change.
