# Feature Plan: Frontend API Mock Happy Path

> Status: deferred
> Type: frontend API mock / interactive integration test
> Last Updated: 2026-05-27
> Parent Plan: [Main Page Frontend Runtime Integration](main-page-frontend-runtime-integration.md)
> Architecture: [Frontend Architecture Plan](../../frontend/frontend-architecture-plan.md), [Event Reducer Contract](../../frontend/event-reducer-contract.md), [API/UI Mapping](../../frontend/api-ui-mapping.md)
> Product: [Plato MVP PRD](../../product/plato-mvp-prd.md), [Plato UI API Contract](../../product/plato-ui-api-contract.md), [Audit Page Contract](../../engineering/audit-page-contract.md)
> Technical Design: [中文详细技术方案](frontend-api-mock-happy-path-technical-design.zh-CN.md)

---

## 1. Problem

> Decision update, 2026-05-27: this API mock plan is parked. P7.1A Main Page
> Compatibility Wrap may proceed first because it only wraps the current page
> with route/runtime composition and does not require a full interactive API
> mock.

The frontend now has type contracts, Main/Audit mock scenarios, API boundary
hardening, a runtime reducer foundation, and a reducer compatibility harness.
Continuing to add isolated state/event scenario tests has diminishing value.

The missing next capability is an API-shaped mock that lets the frontend move
through a user-visible workflow by calling the same `PlatoApi` methods that the
future backend adapter will use.

Current limitation:

- Main Page fixture mode switches static states.
- Main Page tests can verify adapter methods are called, but the mock does not
  behave like a session state machine.
- Audit mocks are separate from the Main Page session lifecycle.
- A user cannot exercise a single happy path where commands mutate mock backend
  state and snapshots reflect the new facts.

## 2. Deferred Decision

Park the API mock work while P7.1A proceeds. When this plan is resumed, build
one in-memory `PlatoApi` mock for a single Main/Audit happy path session.

The resumed first slice must be deliberately narrow:

- one project;
- one workflow;
- one session;
- one happy path;
- one confirmation;
- one completed result;
- one file-change summary;
- one Audit entry path.

This is not a scenario gallery. It is an API contract simulator for frontend
development and integration tests.

## 3. Goals

1. Provide test data for every API the current Main Page and Audit Page frontend
   depends on.
2. Make Main Page move through a real command/query flow without manually
   switching fixture state ids.
3. Keep the mock behind the existing `PlatoApi` interface.
4. Use command accepted responses as local pending signals only; durable UI facts
   come from subsequent snapshots.
5. Emit lightweight `UiEvent` invalidation events from the mock where useful.
6. Let one integration test drive the happy path as a session.
7. Keep real backend integration unblocked: replacing the mock with HTTP should
   not require changing page components.

## 4. Non-goals

- Do not add more static Figma/state scenario tests.
- Do not implement every failure path.
- Do not implement real backend aggregation.
- Do not implement long-running agent execution.
- Do not implement full SSE replay, retention, or cursor expiry.
- Do not make Audit Page production-complete in this slice.
- Do not replace Main Page runtime wiring until the mock proves the API contract.

## 5. Happy Path

The first session mock test should exercise this path:

| Step | User/API action | Mock state transition | Expected visible result |
|---|---|---|---|
| 1 | `listSessions` / `getSessionSnapshot` | Workspace has one empty session. | Main Page loads session shell with empty TaskTree. |
| 2 | `generateTaskTree` from session input | Planning becomes draft-ready. | Snapshot contains draft TaskTree nodes. |
| 3 | `publishTaskTree` | Execution starts. | Snapshot shows published/running TaskTree. |
| 4 | `resolveConfirmation` | Confirmation becomes resolved and execution continues. | Pending confirmation disappears or becomes resolved in facts. |
| 5 | Query snapshot after completion event | Result and file-change summary appear. | Main Page shows completed result and file changes. |
| 6 | `getAuditSnapshot` / `listAuditRecords` | Audit records are available for the session/task. | Audit entry data can be queried through the API mock. |

The test should treat commands as asynchronous facts:

```text
command accepted -> event/refetch -> new snapshot facts
```

## 6. Deliverables

### P6.9 API Mock Foundation

- Add `frontend/src/shared/api/mockPlatoApi.ts` or
  `frontend/src/testing/api/happyPathMockPlatoApi.ts`.
- Implement a single in-memory `PlatoApi`.
- Add unit tests for all implemented methods.
- Do not wire it into production app startup yet.

### P6.10 Main Page Happy Path Integration Test

- Render Main Page through `createHttpMainPageAdapter({ api: mockApi })`.
- Drive the UI with `@testing-library/user-event`.
- Assert snapshots move from empty to draft/running/confirmation/completed.
- Assert the test uses API calls, not fixture state picker changes.

### P6.11 Audit API Happy Path Test

- Query Audit snapshot/records/detail/evidence from the same mock session.
- Verify Audit data is linked to the completed Main Page path.
- Keep Audit UI implementation out of scope unless separately approved.

## 7. Workload Estimate

| Slice | Estimate | Notes |
|---|---:|---|
| P6.9 API mock foundation | 0.5-1 day | Mostly model state and implement `PlatoApi`. |
| P6.10 Main Page happy path integration test | 0.5-1 day | Uses existing MainPage and adapter. Some selector/test timing work expected. |
| P6.11 Audit API happy path test | 0.5 day | API-only unless Audit UI is wired. |
| Stabilization | 0.5 day | Cursor/event timing, test readability, fixture cleanup. |

Expected total: 2-3 engineering days for a maintainable first version.

## 8. Acceptance Criteria

1. The mock implements every `PlatoApi` method needed by Main/Audit happy path.
2. The Main Page happy path test uses `createHttpMainPageAdapter`, not fixture
   state switching.
3. Commands return `CommandResponse.status = accepted` and mutate mock state only
   through the mock API state machine.
4. Query responses return contract-shaped `MainPageSnapshot` and
   `AuditPageSnapshot`.
5. Events are optional but, when emitted, remain lightweight invalidation hints.
6. Unsupported or unimplemented methods fail with explicit structured errors.
7. No production UI behavior changes in the initial mock foundation slice.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Mock becomes a second backend. | Keep one happy path only; no broad domain simulation. |
| Test duplicates static scenario coverage. | Drive by API commands, not state ids. |
| Mock snapshots drift from contracts. | Type against `PlatoApi`, `MainPageSnapshot`, and `AuditPageSnapshot`. |
| Events introduce flakiness. | Prefer explicit refetch after accepted commands first; add events only where deterministic. |
| Audit mock remains disconnected. | Store Audit records in the same session mock state. |

## 10. Recommended Next Prompt

```text
Use the product-workflow-gate skill first.

Task:
Implement P6.9 Frontend API Mock Foundation.

Context:
docs/plans/feature/frontend-api-mock-happy-path.md and
docs/plans/feature/frontend-api-mock-happy-path-technical-design.zh-CN.md define
the plan. Build one in-memory `PlatoApi` mock for a single Main/Audit happy path
session.

Do not change MainPage UI.
Do not wire the mock into production runtime.
Do not add more static scenario tests.

Required work:
1. Create the happy-path mock API module.
2. Implement contract-shaped responses for Main/Audit happy path APIs.
3. Add focused API tests for state transitions and response contracts.
4. Keep unsupported paths explicit.

Output:
- files changed
- API methods implemented
- tests run
- remaining gaps
```
