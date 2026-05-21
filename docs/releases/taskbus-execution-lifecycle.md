# TaskBus Execution Lifecycle

> Status: done
>
> Date: 2026-05-21
>
> Related: [Gap Registry](../gaps/), [Roadmap](../roadmap.md),
> [Project Plan](../project/roadmap.md), [Task Architecture](../architecture/task.md)

## Summary

TaskBus now owns the minimal published Task execution lifecycle:

```text
publish
  -> claim_next
  -> running
  -> complete / fail / skip
```

This closes the first server-core lifecycle gap after publishing. Published
Tasks can now move beyond `pending` through the TaskBus boundary and remain
visible to existing Task projection and Main Page snapshot paths.

## What Shipped

- `TaskDomain` records `claimed_by` alongside `started_at`, `completed_at`,
  `result_ref`, and `error_ref`.
- `TaskBus` protocol now includes:
  - `claim_next(session_id, capability, agent_id)`;
  - `complete(session_id, task_id, result_ref)`;
  - `fail(session_id, task_id, error_ref)`;
  - `skip(session_id, task_id, reason)`.
- `InMemoryTaskBus` implements lifecycle transitions for tests and server-core
  composition.
- `SqliteTaskBus` persists lifecycle transitions by updating both indexed
  status and serialized Task payload.
- Task claiming respects:
  - session isolation;
  - `pending` status;
  - required capability match;
  - parent completion before child claim.
- Retry remains correctly modeled as a new Task through the existing
  `TaskPublisher.retry_task` boundary.
- Skip is represented as a terminal `failed` Task with an `error_ref` prefixed
  by `skipped:`. This preserves the current four-state architecture while
  giving the command path an explicit skip operation.

## Validation

Focused validation:

```text
uv run pytest tests/test_sqlite_task_bus.py tests/test_task_bus_lifecycle.py tests/test_task_projection.py tests/test_task_publisher.py tests/test_task_commands.py
uv run ruff check src tests
uv run mypy src tests
```

Result:

- 56 focused tests passed.
- Ruff passed.
- Mypy passed.

## Follow-Ups

- Wire lifecycle events into the UI event projection / sidecar event source
  when Main Page needs live task-status updates beyond snapshot refresh.
- Add Routing Agent assignment semantics on top of the current lifecycle
  boundary: router submits assignment commands, TaskBus validates and records
  assignment, and Execution Agent claims only tasks assigned to itself.
- Add cooperative task interruption: TaskBus records stop intent while
  Agent/runtime owns safe-point behavior.
- Decide later whether product needs an explicit `skipped` or `cancelled`
  published Task status. The current architecture intentionally keeps Product
  1.0 execution at four states.
