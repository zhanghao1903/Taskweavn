# Task Execution Capability

> Status: planned
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: backend

## User Problem

After users publish tasks, Plato must execute them, update TaskNode states, and produce observable results without making users understand the internal Agent loop.

## Current System Capability

- AgentLoop exists with action execution, autonomy gate, wait coordination, and event/message streams.
- TaskPublisher and SQLite TaskBus publish/read surfaces exist.
- Task domains include status fields and dispatch constraints.
- Pipeline publish-time expansion exists for some pipeline stages.

## Target Capability

Published Tasks enter TaskBus, are claimed by an appropriate agent/runtime, execute, update status, emit messages/events, and feed result/file/audit projections back to UI.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| TaskBus claim/complete/fail lifecycle incomplete | unplanned | open | Publish exists, execution authority lifecycle remains. |
| Agent assignment not productized | partial | open | Dispatch constraints exist; runtime assignment needs implementation. |
| AgentLoop not fully task-native | unplanned | open | Loop has task_id correlation but needs Task execution service wrapper. |
| UI state updates from execution incomplete | unplanned | open | Needs event contract and projection. |

## Related Architecture Docs

- [Current Architecture](../../architecture/current.md)
- [Architecture A1](../../architecture/versions/a1-product-1.0/overview.md)

## Related Plans

- Needs new feature package under `docs/plans/features/task-execution/`.

## Legacy Sources

- [Task](../../archive/legacy-2026-05-18/architecture/task.md)
- [TaskBus](../../archive/legacy-2026-05-18/architecture/bus.md)
- [TaskBus v2](../../archive/legacy-2026-05-18/architecture/bus-v2.md)
- [Agent](../../archive/legacy-2026-05-18/architecture/agent.md)
- [Legacy Task Publishers Plan](../../archive/legacy-2026-05-18/plans/feature/task-publishers-schedule-api.md)
- [Legacy Pipeline Task Loading Plan](../../archive/legacy-2026-05-18/plans/feature/pipeline-task-loading.md)

## Related Code

- `src/taskweavn/core/loop.py`
- `src/taskweavn/task/bus.py`
- `src/taskweavn/task/sqlite_bus.py`
- `src/taskweavn/task/publisher_service.py`
- `src/taskweavn/task/pipeline.py`

## Open Questions

- Should 1.0 support one local execution agent only, with multi-agent deferred?
- What is the minimum safe retry/recovery model for failed Task execution?
