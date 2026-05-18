# ADR-0003: Task Publishers Use TaskBus

> Status: accepted
> Date: 2026-05-11
> Related: [Task Execution Capability](../../capabilities/task-execution/), [Task Publishers Release](../../releases/task-publishers-schedule-api.md), [Legacy Task Publisher Plan](../../archive/legacy-2026-05-18/plans/feature/task-publishers-schedule-api.md), [Legacy Pipeline Plan](../../archive/legacy-2026-05-18/plans/feature/pipeline-task-loading.md)

---

## Context

TaskWeavn will have multiple ways to create Tasks:

- user-confirmed Task Trees from the UI;
- Collaborator Agent draft publication;
- pipeline before/begin/after tasks;
- scheduled tasks;
- API-published tasks;
- user-supplied custom Task Trees;
- future agent-created follow-up tasks.

These sources should not each invent a separate execution path. If they bypass TaskBus, Task state, audit, idempotency, and UI replay will fragment quickly.

---

## Decision

All Task publication paths must normalize into Task Trees and publish through TaskBus.

Introduce a TaskPublisher layer:

```text
source-specific input
  -> parse / normalize
  -> validate
  -> preview if needed
  -> publish normal Tasks through TaskBus
```

TaskPublisher is an adapter and policy boundary, not an executor.

Pipeline tasks are normal Tasks:

- `task_before`;
- `task_begin`;
- `task_after`.

Scheduled and API tasks are also normal Tasks. They require additional publisher metadata, idempotency keys, and permission checks, but they do not create a new execution primitive.

Agent assignment should be represented as dispatch constraints on Task:

- required capability stays the primary key;
- preferred/required Agent Template can narrow selection;
- Agent Instance identity should not be hard-coded into ordinary Task definitions.

---

## Consequences

Positive:

- TaskBus remains the single state authority.
- UI can observe all Tasks through one model.
- Publish flows can share validation, audit, idempotency, and preview behavior.
- Pipeline/scheduler/API features become new publishers, not new runtimes.

Trade-offs:

- TaskPublisher must be designed carefully because many features depend on it.
- TaskBus APIs must become stricter before external publishers are safe.
- Some publish sources need extra metadata that ordinary user-created Tasks do not require.
