# Feature Plan: Main Page Real Backend Integration

> Status: in_progress
> Last Updated: 2026-05-21
> Gap: [Main Page real backend integration](../../gaps/README.md)
> Architecture: [UI And Backend Communication](../../architecture/ui-backend-communication.md), [Task Domain/UI Model Separation](../../architecture/task-domain-ui-model-separation.md), [Authoring Domain](../../architecture/authoring-domain.md), [Bus V2](../../architecture/bus-v2.md)
> Product: [Plato Main Page UX Flow](../../product/plato-main-page-ux-flow.md), [Plato UI API Contract](../../product/plato-ui-api-contract.md), [Plato Frontend Technical Design](../../product/plato-frontend-technical-design.md)
> Technical Design: [中文详细技术方案](main-page-real-backend-integration-technical-design.zh-CN.md)
> Frontend Runtime Subplan: [Main Page Frontend Runtime Integration](main-page-frontend-runtime-integration.md)
> Release Record: TBD

---

## 1. Problem / Gap

Plato now has four important foundations:

- a task-first Main Page frontend with mock scenarios and an HTTP adapter;
- a backend UI contract package with query, command, event, and error envelopes;
- a local sidecar API shell that can serve HTTP/SSE routes over `UiQueryGateway`, `UiCommandGateway`, and `UiEventSource`;
- a composed Main Page sidecar application that wires session registry, message stream, TaskBus, authoring services, gateways, HTTP transport, and CLI startup together.

The remaining gap is no longer just backend composition. The current gap is the
**frontend runtime convergence** from fixture-driven prototype behavior to real
backend facts.

Today the frontend can switch to HTTP mode and a local sidecar target exists. But Main Page still has several prototype-era seams:

- the page query key and UI state still center on the 9-state fixture `stateId`;
- `StatePicker` is still visible in the product page shell;
- command success still writes local synthetic messages/decisions instead of using `CommandResponse.refresh`, `affectedScopes`, and backend events as the source of truth;
- Main Page handles only `message.appended` and `session.resync_required`, while the low-level client can already receive all canonical named `UiEventType` events;
- current `message.appended` page handling expects `title/body/kind` in event payload, but the backend event contract is intentionally lighter and points to message ids / affected facts.

Without this final convergence, Main Page can connect to the sidecar but still behaves like an HTTP-capable mock prototype rather than a fully backend-driven product page.

---

## 2. Scope

This plan closes the first real-backend integration path for Main Page.

In scope:

1. Sidecar application assembly for Main Page.
2. Real snapshot route backed by `SessionManager`, `TaskProjectionService`, `MessageStream`, Task stores, and gateway composition.
3. Real command routes backed by `DefaultUiCommandGateway` and existing authoring/task command services.
4. Frontend SSE compatibility with the sidecar's named SSE event frames.
5. A developer entrypoint that prints the `baseUrl` and `sessionId` needed by Vite/Electron.
6. Tests that exercise the integrated backend through HTTP-like or real localhost calls.
7. Frontend runtime convergence from fixture-centric state to session snapshot / command / event semantics.
8. Documentation updates for the gap, roadmap, and release when complete.

Out of scope:

- durable RawTask/DraftTaskTree stores;
- durable SSE replay;
- TaskBus claim/execute/complete/fail lifecycle;
- packaging and Electron process ownership;
- multi-session UI creation flows;
- production auth and token lifecycle;
- full Audit Page integration.

---

## 3. Design Direction

### 3.1 Compose, do not bypass

The sidecar must keep using the gateway boundary:

```text
HTTP/SSE
  -> LocalSidecarServer
  -> PlatoUiHttpTransport
  -> UiQueryGateway / UiCommandGateway / UiEventSource
  -> server-core services
```

If the integration needs a new read/write ability, add it behind gateway/service composition. Do not let the sidecar read SQLite rows or domain models directly.

### 3.2 First version can be mixed durable/volatile

Current durable pieces:

- session registry: SQLite via `SessionManager`;
- workspace messages: SQLite via `SqliteMessageStream`;
- published tasks: SQLite via `SqliteTaskBus`.

Current volatile pieces:

- RawTask store;
- DraftTaskTree store;
- Collaborator template registry;
- finite/resync-only event source.

This is acceptable for the first integration because `Persistent authoring stores` and `durable SSE replay` are separate known gaps. The plan must make that limitation visible, not hide it.

### 3.3 EventSource compatibility matters

The backend SSE shell emits named events:

```text
event: message.appended
event: session.resync_required
```

The frontend client must subscribe to the canonical `UiEventType` names, not only the default `message` event. Otherwise the first real sidecar connection silently misses updates.

Named-event compatibility is now implemented in the low-level client. The next correctness issue is semantic: Main Page should treat events as invalidation / query hints unless the event payload explicitly contains a complete ViewModel. In particular, `message.appended` currently carries `messageIds`, task refs, `message_type`, and `agent_id`; it does not guarantee full message title/body.

### 3.4 Start with a developer shell

The first deliverable should be easy to run locally:

```text
taskweavn plato-sidecar --workspace ./plato-workspace --session-name "Demo"
```

The default sidecar port is stable: `52789`. Developers may still pass
`--port 0` / `--sidecar-port 0` when they explicitly want an ephemeral free
port.

It should print:

```text
baseUrl=http://127.0.0.1:52789
sessionId=<session-id>
vite:
  VITE_PLATO_API_MODE=http
  VITE_PLATO_API_BASE_URL=http://127.0.0.1:52789
  VITE_PLATO_SESSION_ID=<session-id>
```

Packaging/Electron ownership can come later.

---

## 4. Implementation Slices

### Slice 1 — Frontend SSE named-event compatibility

Output:

- frontend `EventSourceLike` accepts named event types;
- `createHttpPlatoApi.subscribeSessionEvents` listens to all canonical `UiEventType` names plus the default `message` event;
- tests cover named `session.resync_required` / `message.appended` events.

Acceptance:

- current mock/EventSource tests still pass;
- real sidecar SSE frames can drive `MainPage` resync behavior.

Status: implemented at low-level `createHttpPlatoApi` client. Main Page still needs broader event handling beyond `message.appended` and `session.resync_required`.

### Slice 2 — Main Page sidecar application assembly

Output:

- `MainPageSidecarApp` or equivalent application object;
- builder that wires:
  - `WorkspaceLayout`;
  - `SessionManager`;
  - `SqliteMessageStream`;
  - `InProcessMessageBus`;
  - `SqliteTaskBus`;
  - in-memory RawTask/DraftTask stores;
  - `DefaultAuthoringCommandService`;
  - `DefaultCollaboratorAuthoringService`;
  - `DefaultCollaboratorApiAdapter`;
  - `DefaultTaskCommandService`;
  - `DefaultTaskProjectionService`;
  - `DefaultUiQueryGateway`;
  - `DefaultUiCommandGateway`;
  - `PlatoUiHttpTransport`;
  - `LocalSidecarServer`.

Acceptance:

- an empty live session snapshot returns `ok=true` and `session.status=new`;
- command routes can mutate backing services through the gateway path;
- resources close cleanly.

Status: implemented.

### Slice 3 — Developer CLI entrypoint

Output:

- `taskweavn plato-sidecar`;
- `taskweavn plato-dev` for starting the backend sidecar and frontend Vite dev
  server together;
- options for workspace root, session id/session name, host/port, model, and optional auth token;
- startup prints env values needed by frontend HTTP mode.

Acceptance:

- developer can start the backend target without importing Python manually;
- developer can run a single command for local Main Page manual testing;
- missing LLM/provider configuration produces a clear startup or command-level error.

Status: implemented.

### Slice 4 — Integrated command smoke path

Output:

- tests through `LocalSidecarServer` for:
  - snapshot before input;
  - append session input;
  - snapshot after message/raw authoring;
  - optional generate task tree with a stub LLM.

Acceptance:

- real gateway composition is exercised end-to-end;
- no sidecar route bypasses the gateway layer.

Status: implemented for backend/HTTP-side smoke. Manual Vite-to-sidecar smoke remains the remaining product-facing validation question.

### Slice 5 — Frontend runtime convergence

Output:

- hide or dev-gate `StatePicker` when `VITE_PLATO_API_MODE=http`;
- make snapshot query identity session-centric instead of fixture-state-centric;
- convert accepted command responses into pending/refresh behavior instead of local synthetic truth;
- use `refresh.affectedScopes`, canonical `UiEventType`, and `session.resync_required` to drive invalidation/refetch;
- handle lightweight `message.appended` events correctly by querying snapshot/messages when title/body are not present;
- keep local UI state limited to selection, detail mode, input draft, and temporary pending affordances.

Acceptance:

- live sidecar snapshot is the source of TaskTree/messages/confirmation/result/file-change truth;
- confirmation and input flows converge through backend snapshot/event facts;
- named events beyond `message.appended` are either handled directly or cause a safe snapshot resync;
- fixture state catalog remains available for dev/demo tests but does not define HTTP runtime behavior.

### Slice 6 — Docs and release closure

Output:

- release record;
- gap registry `done`;
- roadmap next item updated to pipeline/execution lifecycle or the next UI/backend blocker discovered during integration.

Acceptance:

- limitations are explicit: volatile authoring stores and resync-only SSE are not accidentally sold as complete persistence.

---

## 5. Risks

| Risk | Mitigation |
|---|---|
| Integration grows into packaging work | Keep Electron ownership and signing out of scope. |
| Authoring volatility surprises later work | Mark RawTask/DraftTask persistence as a separate gap and keep the builder's store choices visible. |
| SSE appears connected but does not update UI | Fix named-event listener compatibility first. |
| LLM-backed collaborator makes tests flaky | Use stub LLM tests for integration; leave provider behavior to LLM reliability tests. |
| Sidecar accumulates business logic | Require all business reads/writes to go through gateways/services. |

---

## 6. Validation

Expected final validation:

```text
uv run ruff check src tests
uv run mypy src tests
uv run pytest
npm test
npm run build
npm run lint
git diff --check
```

Focused validation during implementation:

```text
uv run pytest tests/test_main_page_sidecar_app.py tests/test_local_sidecar_server.py tests/test_ui_http_transport.py
npm test -- platoApi.test.ts platoRuntime.test.ts httpMainPageAdapter.test.ts
```

---

## 7. Completion Criteria

This plan is done when:

- Main Page has a real local backend target, not only fixtures;
- snapshot and command routes are served by composed backend services;
- frontend can consume named SSE frames emitted by the sidecar;
- a developer can start the sidecar and configure Vite to connect to it;
- Main Page HTTP mode uses backend snapshot/event facts rather than fixture-derived state and local synthetic truth;
- known follow-ups are routed rather than hidden.

---

## 8. Current Implementation

Started on branch `codex/main-page-real-backend-integration`.

Implemented so far:

- frontend `createHttpPlatoApi.subscribeSessionEvents` now listens to:
  - default `message`;
  - every canonical `UiEventType` name emitted by the backend SSE shell.
- `DefaultUiQueryGateway` can include session-level `AgentMessage` rows, not only TaskTree-node messages.
- `DefaultUiCommandGateway.append_session_input` lets the Collaborator adapter publish the user message instead of treating the UI command id as an already-existing message id.
- `DefaultCollaboratorApiAdapter` now carries emitted user message ids in `CommandResult.emitted_message_ids`.
- `SqliteTaskBus` is safe for sidecar request threads via `check_same_thread=False` and a connection lock.
- Added `MainPageSidecarApp` composition with:
  - `WorkspaceLayout`;
  - `SessionManager`;
  - `SqliteMessageStream`;
  - `InProcessMessageBus`;
  - `SqliteTaskBus`;
  - volatile RawTask/DraftTask stores;
  - Collaborator authoring service;
  - authoring command service;
  - Task command/projection services;
  - UI query/command gateways;
  - `PlatoUiHttpTransport`;
  - `LocalSidecarServer`.
- Added `taskweavn plato-sidecar` dev entrypoint that prints Vite runtime env values.
- Added `taskweavn plato-dev` one-command local dev entrypoint. It starts the
  backend sidecar, starts the frontend Vite server, and injects the sidecar
  `baseUrl` and `sessionId` through `VITE_PLATO_*` environment variables.
- Changed Main Page sidecar CLI defaults from ephemeral port `0` to the stable
  Plato development port `52789`, while keeping `--port` / `--sidecar-port`
  overrides for conflicts or parallel test runs.
- Added a friendly root route for the local sidecar. Opening `baseUrl` now returns
  API hints instead of an `unknown Plato UI route` error.
- The sidecar CLI now prints direct `health` and `snapshot` URLs alongside the
  Vite env values, so manual smoke tests do not require remembering route shapes.
- Hardened Collaborator raw task parsing for real LLM output. The parser now
  accepts common `{"raw_task": {...}}` wrapper shapes and discards model-generated
  ids/timestamps before validating the strict `RawTaskProposal`.
- Hardened another common real LLM shape: string feasibility values such as
  `"Feasible"` and string-list clarification questions are normalized into the
  structured `FeasibilityReport` and `RawTaskAskProposal` shapes.
- Strengthened the Collaborator authoring prompt with explicit output protocols
  for `RawTaskProposal`, `DraftTaskTreeProposal`, and `DraftTaskPatchProposal`,
  including enum values, field types, and forbidden generated ids/timestamps.
- Expanded the Collaborator prompt into a detailed authoring contract. It now
  explains the Plato/TaskWeavn work scenario, authoring lifecycle, context fields,
  protocol purpose, parameter meanings, field dependencies, and final validation
  checklist before returning JSON.
- Clarified the Collaborator Agent's system role and positioning: it is the
  first structured boundary between user language and TaskWeavn's task domain,
  and its JSON output is a product-facing contract that may become durable
  authoring state.
- Centralized system prompts under `taskweavn.prompts` so prompt contracts can
  be versioned and reviewed separately from service implementation code. Existing
  public constants such as `DEFAULT_SYSTEM_PROMPT` and `AUDIT_SYSTEM_PROMPT`
  remain as compatibility aliases.

Focused validation so far:

- `uv run ruff check src/taskweavn/server src/taskweavn/task/collaborator_api.py src/taskweavn/task/sqlite_bus.py src/taskweavn/cli/main.py tests/test_main_page_sidecar_app.py tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py tests/test_cli.py`
- `uv run mypy src/taskweavn/server src/taskweavn/task/collaborator_api.py src/taskweavn/task/sqlite_bus.py src/taskweavn/cli/main.py tests/test_main_page_sidecar_app.py tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py tests/test_cli.py`
- `uv run pytest tests/test_main_page_sidecar_app.py tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py tests/test_ui_http_transport.py tests/test_local_sidecar_server.py tests/test_sqlite_task_bus.py tests/test_cli.py` — 59 passed
- `npm test -- platoApi.test.ts httpMainPageAdapter.test.ts platoRuntime.test.ts` — 19 passed

Full validation:

- `uv run ruff check src tests` — passed
- `uv run mypy src tests` — passed
- `uv run pytest` — 756 passed
- `npm test` — 50 passed
- `npm run build` — passed
- `npm run lint` — passed
- `git diff --check` — passed
- after the root-route fix:
  - `uv run ruff check src/taskweavn/server/ui_http.py src/taskweavn/cli/main.py tests/test_ui_http_transport.py tests/test_local_sidecar_server.py tests/test_cli.py` — passed
  - `uv run mypy src/taskweavn/server/ui_http.py src/taskweavn/cli/main.py tests/test_ui_http_transport.py tests/test_local_sidecar_server.py tests/test_cli.py` — passed
  - `uv run pytest tests/test_ui_http_transport.py tests/test_local_sidecar_server.py tests/test_cli.py` — 32 passed
- after real LLM wrapper-shape smoke failure:
  - `uv run ruff check src/taskweavn/task/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run mypy src/taskweavn/task/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run pytest tests/test_collaborator_authoring_service.py tests/test_collaborator_api_adapter.py tests/test_main_page_sidecar_app.py tests/test_ui_command_gateway.py` — 28 passed
- after real LLM string feasibility / string asks smoke failure:
  - `uv run ruff check src/taskweavn/task/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run mypy src/taskweavn/task/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run pytest tests/test_collaborator_authoring_service.py tests/test_collaborator_api_adapter.py tests/test_main_page_sidecar_app.py tests/test_ui_command_gateway.py` — 29 passed
  - `uv run pytest` — 760 passed
- after prompt protocol hardening and `taskweavn.prompts` centralization:
  - `uv run ruff check src/taskweavn/prompts src/taskweavn/core/loop.py src/taskweavn/audit/agent.py src/taskweavn/interaction/risk.py src/taskweavn/task/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run mypy src/taskweavn/prompts src/taskweavn/core/loop.py src/taskweavn/audit/agent.py src/taskweavn/interaction/risk.py src/taskweavn/task/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run pytest tests/test_collaborator_authoring_service.py tests/test_audit.py tests/test_interaction_risk_llm.py tests/test_loop.py` — 58 passed
  - `uv run ruff check src tests` — passed
  - `uv run mypy src tests` — passed
  - `uv run pytest` — 761 passed
- after detailed Collaborator prompt expansion:
  - `uv run ruff check src/taskweavn/prompts/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run mypy src/taskweavn/prompts/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run pytest tests/test_collaborator_authoring_service.py` — 9 passed
- after Collaborator role/positioning clarification:
  - `uv run ruff check src/taskweavn/prompts/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run mypy src/taskweavn/prompts/collaborator.py tests/test_collaborator_authoring_service.py` — passed
  - `uv run pytest tests/test_collaborator_authoring_service.py` — 9 passed
- after `taskweavn plato-dev` one-command local startup:
  - `uv run ruff check src/taskweavn/cli/main.py tests/test_cli.py` — passed
  - `uv run mypy src/taskweavn/cli/main.py tests/test_cli.py` — passed
  - `uv run pytest tests/test_cli.py` — 18 passed
  - `uv run taskweavn plato-dev --help` — passed
  - `uv run ruff check src tests` — passed
  - `uv run mypy src tests` — passed
  - `uv run pytest` — 764 passed
- after switching Main Page sidecar defaults to stable port `52789`:
  - `uv run ruff check src/taskweavn/server/main_page.py src/taskweavn/server/__init__.py src/taskweavn/cli/main.py tests/test_cli.py tests/test_main_page_sidecar_app.py` — passed
  - `uv run mypy src/taskweavn/server/main_page.py src/taskweavn/server/__init__.py src/taskweavn/cli/main.py tests/test_cli.py tests/test_main_page_sidecar_app.py` — passed
  - `uv run pytest tests/test_cli.py tests/test_main_page_sidecar_app.py` — 24 passed
  - `uv run taskweavn plato-dev --help` — passed; default sidecar port shown as `52789`
  - `uv run taskweavn plato-sidecar --help` — passed; default port shown as `52789`
  - `uv run ruff check src tests` — passed
  - `uv run mypy src tests` — passed
  - `uv run pytest` — 765 passed

Remaining before this plan can be marked done:

- complete or explicitly split out frontend runtime convergence from fixture-centric behavior to session snapshot / event invalidation behavior;
- decide whether a manual Vite-to-sidecar smoke is enough for acceptance, or add an automated browser smoke around the sidecar;
- add release record when accepted.
