# Release: Local Sidecar API Shell

> Status: done
> Date: 2026-05-21
> Work Stream: Plato Main Page backend integration
> Related Plan: [Local Sidecar API Shell](../plans/feature/local-sidecar-api-shell.md)
> Technical Design: [Local Sidecar API Shell Technical Design](../plans/feature/local-sidecar-api-shell-technical-design.zh-CN.md)
> Architecture: [UI And Backend Communication](../architecture/ui-backend-communication.md), [Task Domain/UI Model Separation](../architecture/task-domain-ui-model-separation.md)

---

## 1. Summary

This release adds the first local Plato sidecar API shell.

The backend now has a framework-neutral UI HTTP transport, SSE event framing, optional local token auth, and a stdlib loopback HTTP binding that can serve the documented Plato UI routes. This gives the frontend a real local target while keeping route handling behind `UiQueryGateway`, `UiCommandGateway`, and `UiEventSource`.

The sidecar remains a shell: it does not implement durable event replay, TaskBus execution, or Main Page real backend composition.

---

## 2. Shipped

### 2.1 Shared Transport Models

Added `taskweavn.server.transport` with:

- `HttpApiRequest`;
- `HttpApiResponse`;
- `ApiErrorBody`.

`ApiPublishHttpTransport` now reuses these shared models instead of carrying a private duplicate transport shape.

### 2.2 Plato UI HTTP Transport

Added `PlatoUiHttpTransport` with route dispatch for:

- `GET /api/v1/health`;
- `GET /api/v1/sessions/{sessionId}/snapshot`;
- `POST /api/v1/sessions/{sessionId}/input`;
- `POST /api/v1/sessions/{sessionId}/task-tree/generate`;
- `PATCH /api/v1/sessions/{sessionId}/tasks/{taskNodeId}`;
- `POST /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/input`;
- `POST /api/v1/sessions/{sessionId}/task-tree/publish`;
- `POST /api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond`;
- `GET /api/v1/sessions/{sessionId}/events?cursor=...`.

The transport handles URL decoding, method mismatch, session mismatch, invalid command bodies, gateway exceptions, and optional bearer-token auth. SSE routes also allow query-token auth for `EventSource`.

### 2.3 SSE Event Shell

Added:

- `UiEventSource`;
- `StaticUiEventSource`;
- `ResyncOnlyEventSource`;
- `sse_frame`;
- `sse_stream`.

The first shell can produce valid SSE frames and explicitly returns `session.resync_required` when durable replay is not available.

### 2.4 Stdlib Local Binding

Chose方案 A for the first concrete binding: Python stdlib local HTTP server.

Added `LocalSidecarServer` and `LocalSidecarConfig` with:

- loopback-only binding by default;
- dynamic port allocation with port `0`;
- `serve_forever`, `start_in_thread`, `shutdown`, and context-manager lifecycle;
- JSON decode and non-object body rejection before transport dispatch;
- SSE response content-type handling;
- CORS preflight and loopback-origin checks;
- real localhost tests through `http.client`.

The binding is intentionally thin, so a future FastAPI/Starlette/uvicorn or Electron main-process bridge can replace it without changing the transport contract.

---

## 3. Validation

Final validation:

- `uv run ruff check src/taskweavn/server tests/test_local_sidecar_server.py tests/test_ui_http_transport.py tests/test_ui_sse_transport.py`
- `uv run mypy src/taskweavn/server tests/test_local_sidecar_server.py tests/test_ui_http_transport.py tests/test_ui_sse_transport.py tests/test_api_publish_transport.py`
- `uv run pytest tests/test_local_sidecar_server.py tests/test_ui_http_transport.py tests/test_ui_sse_transport.py tests/test_api_publish_transport.py` — 27 passed
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run pytest` — 749 passed
- `npm test` from `frontend/` — 49 passed
- `npm run build` from `frontend/`
- `npm run lint` from `frontend/`
- `git diff --check`

---

## 4. Follow-ups

- Connect Main Page to real backend gateway facts instead of fixture/mock adapters.
- Add durable SSE cursor/replay when the product needs replay across process boundaries.
- Decide packaged sidecar ownership and startup diagnostics in the Electron packaging plan.
- Consider a future binding upgrade only after stdlib HTTP becomes a real constraint.
