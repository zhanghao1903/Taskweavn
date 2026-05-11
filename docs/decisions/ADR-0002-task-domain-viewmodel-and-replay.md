# ADR-0002: Task Domain Model, UI ViewModel, And Replayable Interactions

> Status: accepted
> Date: 2026-05-11
> Related: [Task model/UI separation](../plans/feature/task-domain-ui-model-separation.md), [Task-first UI plan](../plans/task-first-ui-interaction.md), [UI API interfaces](../plans/ui/ui-api-interfaces.md)

---

## Context

Task is becoming the primary user-facing object in TaskWeavn. The UI needs Task cards, selectable Task Nodes, confirmation options, task-scoped user guidance, message badges, file summaries, and temporary interaction state.

The backend Task object has a different responsibility: it should remain a stable execution and scheduling entity for TaskBus and Agents.

If UI fields are added directly to backend Task, the execution model will become noisy and unstable. If frontend state is treated as the only source of interaction truth, the backend cannot replay how a Task was confirmed, edited, supplemented, or published.

---

## Decision

Separate three concepts:

1. **Task domain entity**
   - backend fact;
   - used by TaskBus and Agents;
   - contains identity, parent relation, intent, required capability, status, result, timestamps, and dispatch constraints.
2. **Task view/projection data**
   - derived from Task + messages + confirmations + file summaries + child status;
   - sent to UI as TaskCard/TaskNode/TaskDetail views;
   - contains badges, available actions, latest message, file summary, child progress, and permissions.
3. **Task UI state**
   - local frontend state such as selected, expanded, editing, hover, optimistic drafts;
   - not part of TaskBus truth.

The backend must preserve replayable interaction facts:

- user confirmation actions;
- user guidance and task-scoped messages;
- Task Node patches;
- Collaborator Agent proposals;
- publish decisions;
- file change summaries.

Messages remain in a single session message stream. Task-specific views are produced by filtering or aggregating by `task_id`; the system does not create a physically separate Task message stream.

File change summary follows tree aggregation:

- each child node owns its direct file changes;
- each parent node can expose a roll-up summary of all descendant changes.

---

## Consequences

Positive:

- UI can evolve without corrupting the backend execution model.
- Backend can reconstruct the user interaction history behind a Task.
- Task cards can be rich while TaskBus stays small and deterministic.
- Parent/child file summaries can be computed consistently.

Trade-offs:

- A projection layer is required.
- Some data appears in multiple views, so cache invalidation and refresh rules must be explicit.
- API contracts must define which fields are backend truth, derived view data, or frontend-only state.
