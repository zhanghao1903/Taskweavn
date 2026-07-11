# Fix Log: ui-backend-communication.md

> Architecture document:
> [../ui-backend-communication.md](../ui-backend-communication.md)
>
> Original:
> [../ui-backend-communication.original.md](../ui-backend-communication.original.md)
>
> Calibration date: 2026-07-10

## Workflow Gate Report

1. User request summary: fact-check and update one architecture document at a
   time, preserving the old document and recording evidence in a per-document
   fix log.
2. Detected workflow phase: P5/P6/P8 architecture, API-contract, and backend
   integration maintenance, with P9 tests used as verification evidence.
3. Task type: documentation-only architecture fact calibration.
4. Required upstream artifacts: target architecture document, Product 1.1
   product/technical docs, UI contract models, HTTP route/transport code, event
   source and SSE code, frontend API/adapter/event code, and targeted tests.
5. Found artifacts: all required artifacts were present in repository docs,
   production code, and tests.
6. Missing or weak artifacts: the old document mixed implemented behavior,
   long-term recommendations, speculative query names, and incomplete Product
   1.1 updates.
7. Whether implementation is allowed now: yes. The change is documentation
   only and can be grounded in current code.
8. Prework required before implementation: preserve the original file and
   inspect current backend, frontend, docs, and tests.
9. Proposed execution scope: replace only
   `docs/architecture/ui-backend-communication.md` and add this fix log.
10. Acceptance criteria: original preserved; implemented query, command, route,
    event, replay, auth, and frontend behavior stated accurately; known gaps
    made explicit; targeted validation run.
11. Risks and assumptions: the main risk is describing the SSE replay helper as
    a continuous live stream or treating declared event variants as proof of
    producer and frontend coverage.

## Sources Inspected

Architecture, product, and feature docs:

- `docs/architecture/ui-backend-communication.md`
- `docs/product/plato-1-1-open-work.md`
- `docs/product/plato-frontend-technical-design.md`
- `docs/plans/feature/session-conversation-activity-timeline.md`
- `docs/plans/feature/runtime-input-router-contract.md`

Backend contract and transport code:

- `src/taskweavn/server/ui_contract/base.py`
- `src/taskweavn/server/ui_contract/envelopes.py`
- `src/taskweavn/server/ui_contract/errors.py`
- `src/taskweavn/server/ui_contract/events.py`
- `src/taskweavn/server/ui_contract/gateway_protocols.py`
- `src/taskweavn/server/ui_contract/gateways.py`
- `src/taskweavn/server/ui_contract/command_gateway.py`
- `src/taskweavn/server/ui_contract/command_mapping.py`
- `src/taskweavn/server/ui_contract/runtime_input.py`
- `src/taskweavn/server/ui_contract/session_activity_projection.py`
- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/ui_events.py`
- `src/taskweavn/server/ui_http.py`
- `src/taskweavn/server/ui_http_routes.py`
- `src/taskweavn/server/ui_http_activity.py`
- `src/taskweavn/server/ui_http_commands.py`
- `src/taskweavn/server/ui_http_runtime_input.py`
- `src/taskweavn/server/ui_http_sse.py`
- `src/taskweavn/server/ui_command_idempotency.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/main_page_audit_events.py`
- `src/taskweavn/server/sidecar.py`

Frontend code:

- `frontend/src/shared/api/client.ts`
- `frontend/src/shared/api/types.ts`
- `frontend/src/shared/api/platoApi.ts`
- `frontend/src/app/platoRuntime.ts`
- `frontend/src/pages/main-page/httpMainPageAdapter.ts`
- `frontend/src/pages/main-page/useMainPageController.ts`
- `frontend/src/pages/main-page/useMainPageEventSubscription.ts`
- `frontend/src/pages/main-page/runtime/adapter.ts`
- `frontend/src/pages/main-page/runtime/eventRouter.ts`
- `frontend/src/pages/main-page/runtime/commandRefresh.ts`

Tests selected for verification:

- `tests/test_ui_http_transport.py`
- `tests/test_ui_event_projection.py`
- `tests/test_ui_query_gateway.py`
- `tests/test_ui_command_gateway.py`
- `tests/test_runtime_input_router.py`
- `tests/test_session_activity_projection.py`
- `tests/test_diagnostic_bundle_export.py`
- `tests/test_workspace_inspection_api.py`
- `tests/test_token_usage_analytics.py`
- `tests/test_execution_plane_http_transport.py`
- `tests/test_ui_http_runtime_config_transport.py`
- `tests/test_settings_readiness.py`
- `tests/test_settings_config.py`
- `tests/test_ui_command_idempotency.py`
- `frontend/src/shared/api/client.test.ts`
- `frontend/src/shared/api/platoApi.events.test.ts`
- `frontend/src/shared/api/backendContractFixtures.test.ts`
- `frontend/src/pages/main-page/runtime/eventRouter.test.ts`
- `frontend/src/pages/main-page/runtime/eventRouterCompatibility.test.ts`
- `frontend/src/pages/main-page/runtime/commandRefresh.test.ts`
- `frontend/src/pages/main-page/useMainPageController.test.tsx`

## Verified Facts

### Contract facts

1. `UiContractModel` generates lower-camel JSON aliases, forbids unknown
   fields, freezes models, and serializes contract aliases.
2. `QueryResponse` includes request id, success flag, data, error, cursor, and
   generation time.
3. A successful `QueryResponse` requires data and forbids an error; a failed
   response requires an error.
4. `CommandRequest` includes command id, session id, optional idempotency key,
   optional expected version, and typed payload.
5. `CommandResult.status` is restricted to `accepted` or `rejected` and also
   carries task, object, message, published-task, and debug references.
6. `CommandResponse.ok: true` requires an accepted result and no error.
7. `RefreshHint` carries event-wait behavior, suggested queries, affected task
   refs, and affected scopes.
8. `ApiError` has a closed code union covering request, lookup, version,
   command, permission, load, resync, internal, and idempotency failures.
9. Valid application-level command rejection is encoded in the command
   envelope, while transport validation and idempotency conflict use non-200
   HTTP statuses.

### Query and projection facts

10. `UiQueryGateway` currently exposes Main Page snapshot, ASK list/detail,
    Session Activity, Audit snapshot/records/detail, and evidence detail reads.
11. `UiQueryGateway` has no `getTaskTimeline` method.
12. `TaskInteractionTimelineService` exists and contributes to Audit
    projection; it is not a standalone UI transport endpoint.
13. The Main Page snapshot is the main frontend server-state read and carries a
    cursor used to begin event replay.
14. Snapshot transport invokes configured recovery before projection.
15. Snapshot recovery is best effort: a recovery exception is traced and the
    read continues.
16. Settings, runtime configuration, workspace inspection, file reads, usage,
    lifecycle, diagnostics, and execution-plane capabilities use focused
    transport gateways instead of being added to `UiQueryGateway`.

### Command and Runtime Input facts

17. `UiCommandGateway` implements session input, tree generation, task update,
    task input, publish, archive, retry, stop, confirmation, ASK, authoring ASK,
    authoring repair, defer, and cancel commands.
18. Session lifecycle, execution dispatch, diagnostic export, and runtime
    configuration mutation are separate transport capabilities.
19. Publish, retry, and ASK-answer HTTP handlers can request immediate execution
    dispatch after an accepted domain command.
20. Runtime Input validates body/path session identity.
21. A workspace-prefixed Runtime Input route injects the path workspace id and
    rejects a conflicting body workspace id.
22. Runtime Input returns `QueryResponse[RuntimeInputRouteResult]`, not a plain
    `CommandResponse`.
23. A Runtime Input result can include read-only inquiry, Activity, routing
    metadata, and a downstream command response.
24. The command idempotency cache is keyed by session id and idempotency key.
25. An identical repeated request replays the stored HTTP response; a reused key
    with a different request hash returns HTTP 409 `idempotency_conflict`.
26. `expectedVersion` is optional and used by selected command paths, not every
    route.

### HTTP and workspace facts

27. `PlatoUiHttpTransport` is explicitly an HTTP/RPC-style wrapper around UI
    gateways.
28. `ui_http_routes.py` implements sidecar health, settings, runtime config,
    workspace, inspection, usage, session, Main Page, Audit, ASK, command,
    diagnostics, event, and execution-plane route families.
29. `_match_workspace_route` maps a workspace-prefixed path back through the
    active `/api/v1/...` matcher and records the workspace id.
30. The frontend uses workspace-prefixed routes for session operations and
    token usage when a workspace id is selected.
31. The local stdlib sidecar binds to loopback hosts by default and requires an
    explicit override for remote binding.

### Event and replay facts

32. Backend `UiEventType` defines session, task, message, confirmation, ASK,
    result, file, Audit, and command event variants.
33. `UiEvent` carries cursor and affected identities plus a small payload.
34. Task-tree and task-node constructors produce invalidation hints rather than
    full ViewModels.
35. `SqliteUiEventSource` persists events with unique event id and unique
    session/cursor constraints.
36. With a valid cursor it returns later events; with an unavailable cursor it
    returns `session.resync_required` followed by retained session events.
37. `ResyncOnlyEventSource` is the fallback when no durable event source is
    supplied.
38. `sse_frame` writes cursor as `id`, type as `event`, and serialized event as
    `data`.
39. `_sse_response` materializes all currently returned events into a tuple.
40. `sse_stream` documents and implements serialization of a finite batch.
41. Current SSE transport therefore implements framed replay, not a continuously
    attached live stream.
42. Production call-site inspection found selected task-tree, task-node, and
    Audit-record event emission, but no production calls to ASK event
    constructors.

### Frontend facts

43. `createHttpPlatoApi` is a hand-written API client, and
    `createHttpMainPageAdapter` maps its consumed subset to Main Page operations.
44. The event subscriber registers the generic `message` event and an explicit
    list of named event types.
45. Frontend `UiEventType` and that registration list omit all five ASK event
    variants defined by the backend.
46. The Main Page subscribes from the snapshot cursor and ignores duplicate
    cursors within the active subscription.
47. The Main Page event router refetches for every recognized event.
48. `session.resync_required` produces a resyncing refetch state.
49. `command.failed` produces a refetch and can expose a sanitized user-facing
    message.
50. Command response handling refetches when refresh hints, affected refs or
    scopes, emitted messages, or published task ids require it.
51. The backend ASK detail route and query gateway method exist, but the current
    `PlatoApi` interface does not expose a dedicated `getAsk` method.
52. `SidecarAuth` supports bearer headers and an SSE query token, but the stock
    frontend client supplies neither.

### Product alignment facts

53. Product 1.1 docs identify workspace-aware runtime, Plan/TaskNode,
    Session Activity, read-only inquiry, token usage, Runtime Input Router, and
    Contract Revision foundations as implemented/accepted baselines.
54. Session Activity is a user-readable projection and is not a replacement for
    Audit evidence and disclosure.
55. Runtime Input low-confidence interpretation must not directly mutate Plan,
    TaskBus, or workspace state.

## Stale or Corrected Claims

1. The old document said a complete HTTP server was not required by the first
   version. The repository now has a local sidecar server, route matcher,
   transport, runtime assembly, and frontend HTTP adapter.
2. The old required-query table listed `getTaskTimeline`. That method is not in
   the current UI query protocol or route surface.
3. The old layering section treated `TaskInteractionTimelineService` as a
   direct query service. It currently contributes to Audit projection.
4. The old document described HTTP and SSE primarily as recommendations. HTTP
   JSON and SSE framing/replay now exist in code.
5. The old replay-then-attach description implied a continuously attached
   stream. The current helper serializes only a finite replay batch.
6. The old event discussion did not distinguish declared event variants,
   producer wiring, and frontend registration. Those three layers are not
   currently in full parity.
7. The old document did not expose the backend/frontend ASK event mismatch.
8. The old query and command lists did not reflect Runtime Input, Activity,
   Plan archive, diagnostics, token usage, runtime config, workspace
   inspection, and the execution-plane API now present.
9. The old command envelope omitted current object refs, affected objects,
   published task ids, debug refs, and refresh hints.
10. The old document treated Runtime Input like an ordinary command. The
    implemented router returns a query envelope containing a routing result and
    optionally a downstream command response.
11. The old document did not describe command-response idempotency replay and
    request-hash conflict behavior.
12. The old document did not state that the Main Page currently refetches on
    every recognized event instead of selectively patching frontend state.
13. The old document did not distinguish optional backend sidecar auth from the
    lack of stock frontend token wiring.
14. The old document mixed current architecture with open design questions
    about HTTP framework and transport choice. Those questions were removed or
    converted to explicit current limits.

## New Document Decisions

1. Treat the current code contract as authoritative and keep roadmap behavior
   out of the current-state sections.
2. Preserve Query/Command/Event as the stable semantic boundary.
3. Separate `UiQueryGateway` and `UiCommandGateway` from focused transport
   gateways and the execution plane.
4. List implemented route families from the route matcher rather than inventing
   conceptual RPC names.
5. State the finite replay implementation precisely and avoid claiming live
   SSE attachment.
6. Record backend/frontend ASK event drift and frontend auth drift as current
   limits.
7. Describe events as invalidation hints and snapshots as authoritative UI
   projections.
8. Keep Activity and Audit roles distinct.

## Validation Log

Validation commands run after this rewrite:

```bash
git diff --check
uv run pytest tests/test_ui_http_transport.py tests/test_ui_event_projection.py tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py tests/test_runtime_input_router.py tests/test_session_activity_projection.py tests/test_diagnostic_bundle_export.py tests/test_workspace_inspection_api.py tests/test_token_usage_analytics.py tests/test_execution_plane_http_transport.py tests/test_ui_http_runtime_config_transport.py tests/test_settings_readiness.py tests/test_settings_config.py tests/test_ui_command_idempotency.py
npm --prefix frontend run test -- src/shared/api/client.test.ts src/shared/api/platoApi.events.test.ts src/shared/api/backendContractFixtures.test.ts src/pages/main-page/runtime/eventRouter.test.ts src/pages/main-page/runtime/eventRouterCompatibility.test.ts src/pages/main-page/runtime/commandRefresh.test.ts src/pages/main-page/useMainPageController.test.tsx
```

Results:

- `git diff --check`: passed.
- Backend pytest: 202 passed.
- Frontend Vitest: 7 files passed, 41 tests passed.
