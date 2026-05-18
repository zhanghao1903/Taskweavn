# Release: API Publish Server Transport

> Status: done / server-core release candidate
> Date: 2026-05-17
> Accepted: 2026-05-17
> Work Stream: Phase 3D — Task Publishing And Pipeline
> Related: [Task Publisher 使用说明](../project/task-publishers.md), [Publish Persistence Foundation](publish-persistence-foundation.md)

---

## 1. Summary

This release adds a framework-neutral HTTP/RPC adapter for API Task publishing.

It wraps `DefaultApiTaskPublisher` without introducing a concrete web framework
dependency. A future FastAPI, Starlette, desktop, or RPC binding can translate
its native request/response objects into the small transport models shipped here.

---

## 2. Shipped

- `taskweavn.server.ApiPublishHttpTransport`
- `taskweavn.server.HttpApiRequest`
- `taskweavn.server.HttpApiResponse`
- `taskweavn.server.ApiErrorBody`

Supported routes:

```text
POST /sessions/{session_id}/api-publish/preview
POST /sessions/{session_id}/api-publish
```

Transport behavior:

- path `session_id` is the request authority;
- body `session_id`, if present, must match the path;
- `x-taskweavn-actor-id` creates `ApiAuthContext.actor_id`;
- `x-request-id` can provide request id;
- `idempotency-key` can provide idempotency key;
- allowlist headers can narrow sessions, capabilities, and agents;
- success responses use a stable JSON envelope;
- transport/auth/body/path errors return 4xx with `ok=false`;
- business-level rejection remains in `PublishPreview` / `PublishResult`.

---

## 3. Validation

Focused validation:

- `uv run pytest tests/test_api_publish_transport.py tests/test_task_api_publisher.py tests/test_task_publisher.py tests/test_sqlite_publish_stores.py tests/test_task_publish_service.py tests/test_task_scheduler_publisher.py tests/test_task_pipeline.py tests/test_sqlite_task_bus.py` — 101 passed
- `uv run ruff check src/taskweavn/server src/taskweavn/task tests/test_api_publish_transport.py tests/test_task_publisher.py tests/test_sqlite_publish_stores.py tests/test_task_api_publisher.py`
- `uv run mypy src/taskweavn/server src/taskweavn/task tests/test_api_publish_transport.py tests/test_task_publisher.py tests/test_sqlite_publish_stores.py tests/test_task_api_publisher.py`
- `git diff --check`

The single warning is the existing OpenHands/Authlib deprecation warning from
the test environment.

---

## 4. Follow-ups

- Concrete FastAPI/ASGI binding if UI/API integration needs a running local server.
- Publish audit query/debug API.
- SSE or polling transport for UI events.
- Completion-time `task_after` orchestration.
