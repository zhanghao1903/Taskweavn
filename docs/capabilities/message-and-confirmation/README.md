# Message And Confirmation Capability

> Status: current / active
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: full-stack

## User Problem

Users need to see what Plato is doing, answer confirmations in context, and understand whether an input applies to the whole session or a selected TaskNode.

## Current System Capability

- AgentMessage, MessageStream, SQLite message persistence, task_id aggregation, MessageBus, AutonomyGate, and WaitCoordinator exist.
- Session Message Stream and task-scoped projection are defined as product/architecture requirements.
- Frontend baseline includes session message and confirmation view types plus Main Page panels, but these still run on fixtures/mocks.

## Target Capability

One session message stream is the source of truth. Task views project relevant messages by task_id. Confirmations are attached to Task context and resolved through commands.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| No real UI subscription to message events | unplanned | open | Needs SSE/event contract. |
| Confirmation command not connected to backend | unplanned | open | Needs frontend command surface and backend transport. |
| Task-scoped input contract incomplete | unplanned | open | Need clear session vs task input commands. |
| Late/async response UI semantics need product pass | unplanned | open | Backend can defer; UI needs user-facing states. |

## Related Architecture Docs

- [Current Architecture](../../architecture/current.md)
- [Architecture A1](../../architecture/versions/a1-product-1.0/overview.md)
- [UI Backend Contracts](../../contracts/ui-backend/)

## Legacy Sources

- [Interaction Layer](../../archive/legacy-2026-05-18/architecture/interaction-layer.md)
- [UI Backend Communication](../../archive/legacy-2026-05-18/architecture/ui-backend-communication.md)

## Related Code

- `src/taskweavn/interaction/message.py`
- `src/taskweavn/interaction/sqlite_message_stream.py`
- `src/taskweavn/interaction/bus.py`
- `src/taskweavn/interaction/wait.py`
- `frontend/src/entities/message/model.ts`
- `frontend/src/shared/api/types.ts`
- `frontend/src/pages/main-page/SessionMessagePanel.tsx`

## Open Questions

- Should confirmations always appear both in Session Stream and Task detail, or only once with projection highlighting?
- What is the exact UX for timeout default decisions?
