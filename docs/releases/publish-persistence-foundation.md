# Release: Publish Persistence Foundation

> Status: done / server-core release candidate
> Date: 2026-05-17
> Accepted: 2026-05-17
> Work Stream: Phase 3D — Task Publishing And Pipeline
> Related Plan: [Publish Persistence Foundation](../plans/feature/publish-persistence-foundation.md)
> Technical Design: [发布持久化基础中文详细技术方案](../plans/feature/publish-persistence-foundation-technical-design.zh-CN.md)
> Usage Guide: [Task Publisher 使用说明](../project/task-publishers.md)

---

## 1. Summary

This release makes the Task publish control plane durable enough for later
server transport work.

The package adds SQLite-backed publish idempotency, publish audit, scheduled
publish config/state, a small service assembly helper, and deterministic Task
ids for idempotent publishes.

---

## 2. Shipped

- `SqlitePublishIdempotencyStore`
- `SqliteTaskPublishAuditSink`
- `SqliteScheduledPublishStore`
- `PublishStoreError`
- `build_sqlite_publish_service(...)`
- `publish.sqlite` schema for idempotency, audit, scheduler configs, and scheduler state
- API publisher integration coverage with `SqliteTaskBus` and SQLite publish stores
- Deterministic Task ids when `PublishRequest.idempotency_key` is present
- Existing TaskBus recovery when tasks exist but the idempotency record is missing
- Partial idempotent publish detection that rejects instead of duplicating Tasks

---

## 3. Persistence Layout

```text
<workspace>/.taskweavn/
  tasks.sqlite       # Published TaskBus facts
  publish.sqlite     # Publish idempotency, audit, scheduler config/state
```

`tasks.sqlite` remains the execution-domain Task truth. `publish.sqlite`
contains publish control-plane facts only.

---

## 4. Validation

Focused validation for this release:

- `uv run pytest tests/test_task_publisher.py tests/test_sqlite_publish_stores.py tests/test_task_publish_service.py tests/test_task_api_publisher.py tests/test_task_scheduler_publisher.py tests/test_task_pipeline.py tests/test_sqlite_task_bus.py` — 92 passed
- `uv run ruff check src/taskweavn/task tests/test_task_publisher.py tests/test_sqlite_publish_stores.py tests/test_task_api_publisher.py`
- `uv run mypy src/taskweavn/task tests/test_task_publisher.py tests/test_sqlite_publish_stores.py tests/test_task_api_publisher.py`
- `git diff --check`

The single warning is the existing OpenHands/Authlib deprecation warning from
the test environment.

---

## 5. Follow-ups

- HTTP/RPC transport wrapping `DefaultApiTaskPublisher`.
- Publish audit query/debug API.
- Completion-time `task_after` orchestration.
- TaskBus claim/complete/fail lifecycle.
- Storage Governance for migrations, backups, retention, and health checks.
