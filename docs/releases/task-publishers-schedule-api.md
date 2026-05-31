# Release: Task Publishers, Schedule, API, And Pipeline Expansion

> Status: done / server-core release candidate
> Date: 2026-05-16
> Accepted: 2026-05-16
> Work Stream: Phase 3D — Task Publishing And Pipeline
> Related Plan: [Task Publisher 抽象、定时发布与接口发布](../plans/feature/task-publishers-schedule-api.md)
> Usage Guide: [Task Publisher 使用说明](../project/task-publishers.md)
> Related ADR: [ADR-0003](../decisions/ADR-0003-task-publishers-use-taskbus.md)

---

## 1. Summary

This release establishes the first concrete Task publishing package behind TaskWeavn's TaskBus boundary.

The core rule is now implemented in server code:

```text
all publish sources
  -> normalize / validate / preview
  -> TaskPublishService
  -> DefaultTaskPublisher
  -> TaskBus.publish(TaskDomain)
```

The package covers custom Task Tree input, idempotent publish service semantics, scheduler publishing, API publishing, and publish-time pipeline expansion.

---

## 2. Shipped

### 2.1 TaskBus-backed Publisher

- `TaskBus` protocol.
- `InMemoryTaskBus`.
- `TaskPublisher` protocol.
- `DefaultTaskPublisher`.
- `PublisherRef`, `PublishSource`, `TaskPublishOptions`.
- `NormalizedTaskNode`, `NormalizedTaskTree`.
- `PublishRequest`, `PublishPreview`, `PublishResult`.
- Draft publish compatibility through `publish_draft_tree(...)`.
- Retry compatibility through `retry_task(...)`, now backed by TaskBus in-place
  retry rather than publishing a new retry root Task.

### 2.2 Custom Task Tree Input

- `parse_task_tree_input(...)`.
- `normalize_task_tree_input(...)`.
- JSON and YAML support.
- Nested `children` tree input.
- Flat `parent_id` tree input.
- `TaskTreeInputValidator`.
- `AgentCapabilityCatalog` and `StaticAgentCapabilityCatalog`.

### 2.3 Publish Service And Idempotency

- `TaskPublishService`.
- `PublishIdempotencyStore`.
- `InMemoryPublishIdempotencyStore`.
- `PublishIdempotencyRecord`.
- `PublishIdempotencyConflictError`.
- `TaskPublishAuditSink`.
- `InMemoryTaskPublishAuditSink`.
- `PublishAuditEvent`.

Behavior:

- same idempotency key + same payload returns the original result;
- same idempotency key + different payload returns skipped conflict;
- publish metadata is preserved on `TaskDomain.dispatch_constraints.metadata`;
- audit hooks are ready for EventStream / MessageStream / observability adapters.

### 2.4 Scheduler Publisher

- `ScheduledPublishConfig`.
- `ScheduleExpression`.
- `SessionSelector`.
- `IdempotencyPolicy`.
- `ScheduledPublishState`.
- `ScheduledPublishTickResult`.
- `ScheduledPublishStore`.
- `InMemoryScheduledPublishStore`.
- `SchedulerPublisher`.

Supported now:

- interval schedules;
- daily schedules;
- fixed/current session selector;
- enable/disable;
- stable idempotency key per schedule tick;
- custom idempotency key template.

Reserved:

- cron schedule shape exists but does not execute until a cron evaluator is added.

### 2.5 API Publisher

- `ApiAuthContext`.
- `ApiPublishPolicy`.
- `ApiPublishRequest`.
- `ApiRateLimiter`.
- `ApiRateLimitDecision`.
- `AllowAllApiRateLimiter`.
- `ApiTaskPublisher`.
- `DefaultApiTaskPublisher`.

The API layer is transport-neutral. It returns existing `PublishPreview` / `PublishResult` models and can later be wrapped by HTTP/RPC endpoints.

### 2.6 Pipeline Expansion

- `PipelineStage`.
- `PipelineContextPolicy`.
- `PipelineTaskSpec`.
- `PipelineConfig`.
- `PipelineTaskLoader`.
- `DefaultPipelineTaskLoader`.

Publish-time behavior:

- `task_before` and `task_begin` specs become ordinary root `NormalizedTaskNode` entries.
- `TaskPublishService` can use a loader before preview/publish.
- `TaskPublishOptions.allow_pipeline=false` disables expansion.
- Pipeline-generated Tasks retain pipeline metadata.
- `task_after` is modeled but remains a follow-up for completion-time orchestration.

---

## 3. Validation

Final validation for this release candidate:

- `uv run ruff check src tests`
- `uv run mypy src tests` — no issues in 143 source files
- `uv run pytest` — 648 passed, 1 warning
- `git diff --check`

The single warning is the existing OpenHands/Authlib deprecation warning from the test environment.

Focused coverage added:

- `tests/test_task_publisher.py`
- `tests/test_task_publisher_input.py`
- `tests/test_task_publish_service.py`
- `tests/test_task_scheduler_publisher.py`
- `tests/test_task_api_publisher.py`
- `tests/test_task_pipeline.py`

---

## 4. Acceptance Notes

- This is a server-core release candidate.
- No HTTP/RPC transport is included.
- No persistent SQLite TaskBus or publisher store is included.
- Scheduler is single-process and deterministic.
- Pipeline expansion is publish-time only; completion-time `task_after` orchestration remains separate.
- Pipeline Tasks are normal TaskBus Tasks, not a new runtime object.

---

## 5. Follow-ups

- Persistent TaskBus and publish stores.
- HTTP/RPC API endpoints wrapping `DefaultApiTaskPublisher`.
- Cron evaluator for `ScheduleExpression(type="cron")`.
- Completion-time orchestration for `task_after`.
- Full Pipeline loading plan continuation, especially Agent assignment semantics.
- UI preview/confirm surfaces for custom Task Trees, scheduler configs, API dry-run results, and pipeline badges.
