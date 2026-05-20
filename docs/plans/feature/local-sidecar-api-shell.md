# Feature Plan: Local Sidecar API Shell

> Status: done
> Last Updated: 2026-05-21
> Gap: [Local sidecar API shell](../../gaps/README.md)
> Architecture: [UI And Backend Communication](../../architecture/ui-backend-communication.md), [Task Domain/UI Model Separation](../../architecture/task-domain-ui-model-separation.md), [LLM Provider Reliability](../../architecture/llm-provider-reliability.md)
> Product: [Plato UI API Contract](../../product/plato-ui-api-contract.md), [Plato Frontend Technical Design](../../product/plato-frontend-technical-design.md)
> Technical Design: [中文详细技术方案](local-sidecar-api-shell-technical-design.zh-CN.md)
> Release Record: [Local Sidecar API Shell](../../releases/local-sidecar-api-shell.md)

---

## 1. Problem / Gap

Plato frontend already has:

- typed API client and `createHttpPlatoApi`;
- documented `/api/v1/sessions/...` paths;
- `EventSource`-based session event subscription;
- backend-generated JSON fixture parity for snapshot, command, and event contracts.

The backend now has:

- `taskweavn.server.ui_contract` models;
- `DefaultUiQueryGateway`;
- `DefaultUiCommandGateway`;
- `UiEvent` constructors;
- prior framework-neutral publish HTTP transport.

This plan closes the previous missing layer: a **local sidecar API shell** that turns frontend HTTP/SSE calls into backend UI gateway calls without exposing internal Task, MessageStream, SQLite, Tool, or Agent objects.

```text
Plato Electron UI
  -> local HTTP/SSE sidecar
  -> Plato UI transport adapter
  -> UiQueryGateway / UiCommandGateway / UiEventSource
  -> server-core services
```

Before this shell, Main Page real backend integration had no stable local target.

---

## 2. Architecture References Reviewed

| Document / Code | Relevant Constraint |
|---|---|
| [UI And Backend Communication](../../architecture/ui-backend-communication.md) | Query / Command / Event split; HTTP + SSE first; transport adapter must not operate on raw domain/store objects. |
| [Plato UI API Contract](../../product/plato-ui-api-contract.md) | Canonical paths and envelopes for Main Page. |
| [Plato Frontend Technical Design](../../product/plato-frontend-technical-design.md) | Frontend expects local API endpoints and EventSource subscription. |
| `taskweavn.server.ui_contract` | Stable Python contract models and gateway protocols. |
| `taskweavn.server.api_publish` | Existing project style: framework-neutral transport first, concrete web framework can bind later. |
| [LLM Provider Reliability](../../architecture/llm-provider-reliability.md) | Sidecar must be debuggable and not hide provider/runtime failures behind opaque transport errors. |

---

## 3. Scope

This plan creates the minimum local API shell for Plato UI integration.

In scope:

1. Framework-neutral Plato UI HTTP transport adapter.
2. Route matching for documented Main Page query/command endpoints.
3. Stable HTTP status mapping around `QueryResponse`, `CommandResponse`, and `ApiError`.
4. Request validation and JSON decode/encode rules.
5. Session-scoped SSE event stream shell with thin `UiEvent` frames.
6. Local sidecar lifecycle and security rules for Electron development and packaged app.
7. Tests for route/method/body/session mismatch/error handling.
8. Documentation updates tying this gap to the next Main Page real-backend integration plan.

Out of scope for this plan:

- full durable `UiEventStore`;
- real TaskBus execution lifecycle;
- full Main Page live integration;
- production packaging/signing;
- multi-user auth;
- remote network deployment;
- complete Project/Workflow management API;
- WebSocket.

---

## 4. Non-goals

- Do not expose raw `TaskDomain`, `DraftTaskNode`, `AgentMessage`, `MessageStream` rows, or TaskBus internal events.
- Do not make frontend call Python service objects directly.
- Do not add durable event replay as hidden scope.
- Do not require all command side effects to emit perfect realtime events in the first shell.
- Do not use sidecar as a general public API server.

---

## 5. Proposed Design

### 5.1 Keep framework-neutral transport first

Follow the existing `ApiPublishHttpTransport` style:

```python
HttpApiRequest
  -> PlatoUiHttpTransport.handle()
  -> HttpApiResponse
```

The first implementation can reuse or extract common request/response models from `taskweavn.server.api_publish`.

Concrete server binding is a separate layer:

```text
stdlib local HTTP binding
  -> HttpApiRequest
  -> PlatoUiHttpTransport
  -> HttpApiResponse
```

For the first sidecar shell we choose **stdlib local HTTP binding**. It avoids adding a framework dependency before the Main Page integration proves the shape, is easy to test with real localhost requests, and can still be replaced later by FastAPI/Starlette/uvicorn because the binding only converts HTTP into `HttpApiRequest`.

### 5.2 Route surface

Minimum routes:

```text
GET   /api/v1/health
GET   /api/v1/sessions/{sessionId}/snapshot
POST  /api/v1/sessions/{sessionId}/input
POST  /api/v1/sessions/{sessionId}/task-tree/generate
PATCH /api/v1/sessions/{sessionId}/tasks/{taskNodeId}
POST  /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/input
POST  /api/v1/sessions/{sessionId}/task-tree/publish
POST  /api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond
GET   /api/v1/sessions/{sessionId}/events?cursor=...
```

The path names match the current frontend `createHttpPlatoApi` implementation.

### 5.3 Query handling

`GET /snapshot` calls:

```python
UiQueryGateway.get_session_snapshot(session_id, request_id=None)
```

Transport rules:

- `200` if a `QueryResponse` envelope is produced, even when `ok=false` for business/not-found errors.
- malformed path / unsupported method / invalid JSON uses transport-level 4xx/5xx.
- response body is always JSON and uses camelCase contract keys.

### 5.4 Command handling

Command routes validate `CommandRequest[payload]` and call `UiCommandGateway`.

Transport must:

- require `request.sessionId` to match path `sessionId`;
- pass through `commandId`, `idempotencyKey`, and `expectedVersion`;
- return `CommandResponse` as-is;
- never convert command `accepted` into final UI state;
- include stable transport errors for invalid path/body/method.

### 5.5 Event handling

First event shell should define:

```python
class UiEventSource(Protocol):
    def subscribe(self, session_id: str, cursor: str | None) -> Iterator[UiEvent]: ...
```

SSE frame:

```text
id: <event.cursor>
event: <event.event_type>
data: <UiEvent JSON>

```

First version may use in-memory/volatile event source and send `session.resync_required` when it cannot replay from a cursor.

Durable replay belongs to a follow-up plan unless implementation discovers a cheap integration point that does not broaden scope.

### 5.6 Local sidecar security

This is a local product surface, but it still needs basic boundaries:

- bind to loopback only by default (`127.0.0.1`);
- random per-process token or Electron-provided bearer token;
- reject non-loopback origins unless explicitly configured;
- no remote listen in MVP;
- structured logs for request id, route, status, latency, and error code.

### 5.7 Process lifecycle

Target lifecycle:

```text
Electron main process starts
  -> choose available localhost port
  -> create random sidecar token
  -> start Python sidecar process
  -> wait for /api/v1/health
  -> pass baseUrl + token to renderer
  -> renderer creates HttpPlatoApi
  -> on app quit, Electron terminates sidecar
```

This plan documents the lifecycle. Packaging and process management implementation can stay in a later packaging plan if needed.

---

## 6. Implementation Slices

### Slice 1 — Framework-neutral Plato UI HTTP transport

Output:

- `PlatoUiHttpTransport`;
- common `HttpApiRequest` / `HttpApiResponse` model reuse or extraction;
- route matching and URL decoding;
- route tests for snapshot and command endpoints.

Acceptance:

- no web server dependency required;
- all JSON output uses UI contract camelCase;
- path `sessionId` controls authority;
- method mismatch returns stable 405.

### Slice 2 — Command request validation

Output:

- typed body parsing for all command routes;
- session mismatch checks;
- invalid body/error response mapping;
- tests for malformed JSON/body and gateway exceptions.

Acceptance:

- frontend `CommandRequest<T>` shapes round-trip into backend payload models;
- `ApiError` is stable and visible;
- gateway exceptions become `internal_error` without stack traces in response.

### Slice 3 — SSE event shell

Output:

- `UiEventSource` Protocol;
- SSE frame serializer;
- volatile in-memory event source or stub source;
- `session.resync_required` fallback.

Acceptance:

- `UiEvent` serializes into valid SSE frames;
- cursor is treated as opaque;
- no durable replay claim is made.

### Slice 4 — Stdlib local binding

Output:

- `LocalSidecarServer` backed by Python stdlib HTTP server;
- loopback-only default binding;
- malformed JSON rejection before transport dispatch;
- basic CORS/origin checks for local renderer use;
- real localhost tests for health, commands, SSE, auth, and origin rejection.

Acceptance:

- sidecar can be started locally for manual UI testing;
- no new runtime web framework dependency is added;
- the binding remains replaceable because `PlatoUiHttpTransport` is still the only route/business adapter.

### Slice 5 — Frontend live adapter smoke

Output:

- optional frontend integration test against mocked transport responses;
- documentation of `baseUrl` and sidecar token injection.

Acceptance:

- frontend `createHttpPlatoApi` remains the single HTTP client boundary;
- no UI component reads backend internals.

---

## 7. Frontend Work

Expected frontend changes are small in this plan:

- confirm `createHttpPlatoApi` paths stay canonical;
- add token/header support if sidecar security requires it;
- document Electron renderer configuration: `baseUrl`, token, and EventSource URL;
- keep fixture/mock adapter for Story and offline UI states.

The first live Main Page integration is a separate gap after this shell.

---

## 8. Backend Work

Backend work should stay at the server boundary:

- adapt HTTP-like requests into `UiQueryGateway` and `UiCommandGateway`;
- adapt `UiEventSource` into SSE frames;
- expose health/version route;
- test without real network where possible.

Do not implement missing business services inside the sidecar layer.

---

## 9. Contract / API Changes

This plan should not change core UI contract fields unless implementation reveals a mismatch.

Possible small additions:

- `GET /api/v1/health`;
- optional auth token header, for example `Authorization: Bearer <token>`;
- optional sidecar/version response:

```json
{
  "ok": true,
  "data": {
    "name": "Plato Sidecar",
    "version": "0.1.0"
  }
}
```

---

## 10. Tests And Validation

Backend:

- route matching and URL decode;
- method mismatch;
- session mismatch;
- invalid JSON/body;
- snapshot success/not-found/error envelope;
- all command routes call the expected gateway method;
- SSE frame serialization;
- `resync_required` fallback.

Frontend:

- existing `platoApi` tests stay green;
- token/header test if added;
- EventSource URL shape remains stable.

Validation commands:

```text
uv run ruff check src tests
uv run mypy src tests
uv run pytest
npm test
npm run build
npm run lint
git diff --check
```

---

## 11. Acceptance Criteria

The gap is closed when:

- Plato frontend has a local HTTP/SSE target matching the documented API paths;
- sidecar transport calls UI gateways, not raw domain/store objects;
- command/query/event/error envelopes are stable and tested;
- local security defaults are documented;
- sidecar transport failure modes are visible and debuggable;
- remaining real backend integration work is routed to the Main Page integration gap.

---

## 12. Current Implementation

Started on branch `codex/local-sidecar-api-shell`.

Implemented so far:

- extracted shared `HttpApiRequest`, `HttpApiResponse`, and `ApiErrorBody` into `taskweavn.server.transport`;
- updated existing `ApiPublishHttpTransport` to reuse the shared transport models;
- added `UiEventSource`, `StaticUiEventSource`, `ResyncOnlyEventSource`, `sse_frame`, and `sse_stream`;
- added `PlatoUiHttpTransport` with:
  - `/api/v1/health`;
  - snapshot query route;
  - all Main Page command routes;
  - session event route with SSE frame output;
  - path/body `sessionId` mismatch checks;
  - URL decoding;
  - method mismatch and unknown route errors;
  - optional local bearer-token auth, plus query-token support for SSE.
- chose方案 A: stdlib local HTTP binding for the first sidecar shell;
- added `LocalSidecarServer` with:
  - loopback-only binding by default;
  - port `0` support for dynamic local port allocation;
  - `serve_forever`, `start_in_thread`, `shutdown`, and context-manager lifecycle;
  - JSON decode and non-object body rejection before transport dispatch;
  - SSE content-type handling;
  - CORS preflight and loopback-origin checks;
  - real localhost tests through `http.client`.

Validation so far:

- `uv run ruff check src/taskweavn/server tests/test_local_sidecar_server.py tests/test_ui_http_transport.py tests/test_ui_sse_transport.py`
- `uv run mypy src/taskweavn/server tests/test_local_sidecar_server.py tests/test_ui_http_transport.py tests/test_ui_sse_transport.py tests/test_api_publish_transport.py`
- `uv run pytest tests/test_local_sidecar_server.py tests/test_ui_http_transport.py tests/test_ui_sse_transport.py tests/test_api_publish_transport.py` — 27 passed
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run pytest` — 749 passed
- `npm test` from `frontend/` — 49 passed
- `npm run build` from `frontend/`
- `npm run lint` from `frontend/`

Completed:

- full backend/frontend validation passed after the stdlib binding addition;
- release record added under `docs/releases/local-sidecar-api-shell.md`.

---

## 13. Completion Updates

When implementation completes:

1. mark this plan `done`;
2. update [Gap Registry](../../gaps/README.md);
3. add a release record under `docs/releases/`;
4. update [Plato UI API Contract](../../product/plato-ui-api-contract.md) if route/header fields changed;
5. update [UI And Backend Communication](../../architecture/ui-backend-communication.md) if transport semantics changed;
6. update roadmap only if sequencing changes.
