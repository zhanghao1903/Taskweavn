# Architecture A1 For Plato 1.0

> Status: active architecture version
> Last Updated: 2026-05-18
> Product Version: Plato 1.0
> Related: [Current Architecture](../../current.md), [Plato 1.0 Overview](../../../product/versions/1.0/overview.md), [Capability Map](../../../capabilities/index.md), [Contracts](../../../contracts/)

---

## 1. Architecture Intent

A1 supports Plato 1.0 as a local, Task-first personal assistant.

It is optimized for:

- clear user control through Task Tree and TaskNode;
- replayable authoring and execution facts;
- reliable local desktop delivery;
- separation between user-facing UI viewmodels and backend execution state;
- enough audit, logging, and diagnostics to support trust and early testing.

It is not optimized for:

- multi-user organization workflows;
- marketplace/platform extensibility;
- full multi-agent canvas;
- enterprise compliance.

---

## 2. Core Object Model

```text
Project
  -> Workflow
      -> Session
          -> Session Workspace
          -> RawTask / DraftTaskTree
          -> Published Task Tree
          -> Messages / Events / Logs / File Changes
```

Key rules:

1. Task is the primary user interaction object.
2. Chat is input and explanation, not the system's main state model.
3. Authoring and execution are separate domains.
4. Published Tasks enter TaskBus; RawTask and DraftTaskTree do not.
5. UI Task cards are projections, not backend truth.

---

## 3. Domain Boundaries

| Boundary | Responsibility | Current Authority |
|---|---|---|
| Product scope | Plato 1.0 promise, P0/P1/non-goals, acceptance. | [product version package](../../../product/versions/1.0/) |
| Capability state | What exists, what is planned, what is missing. | [capability map](../../../capabilities/index.md) |
| Authoring domain | RawTask, feasibility, clarification, DraftTaskTree mutation. | [Task Authoring Capability](../../../capabilities/task-authoring/) |
| Execution domain | Published Tasks, TaskBus, Agent execution lifecycle. | [Task Execution Capability](../../../capabilities/task-execution/) |
| Interaction domain | Messages, confirmation, autonomy, waiting, risk. | [Message and Confirmation Capability](../../../capabilities/message-and-confirmation/) |
| UI projection | Task cards, detail views, messages, file summaries. | [Main Page Real Backend](../../../capabilities/main-page-real-backend/) and [contracts](../../../contracts/ui-backend/) |
| Trust / observability | Audit, logs, archives, diagnostics. | [Audit Trust](../../../capabilities/audit-trust/) and [Diagnostic Bundle](../../../capabilities/diagnostic-bundle/) |
| Release runtime | Electron frontend plus Python sidecar. | [Packaging Strategy](../../../plans/release/packaging-and-distribution-strategy.md) |

---

## 4. UI Backend Boundary

A1 uses Query / Command / Event:

```text
Query   -> read snapshot or viewmodel
Command -> mutate system state through validated service boundary
Event   -> notify UI that a projection changed
```

Stable API details live in [contracts](../../../contracts/). Architecture explains why the boundary exists; contracts define exact shapes and behavior.

First 1.0 transport target:

```text
local authenticated HTTP + SSE
```

Electron should start the Python sidecar automatically and hide backend details from users.

---

## 5. Message Model

Messages remain one session stream:

```text
session_id + agent_id + task_id + message_type + parent_message_id
```

Task views are projections over the session stream, not separate task-specific streams.

This keeps:

- chronological session replay;
- task-scoped message filtering;
- confirmation/response threading;
- future multi-agent support.

---

## 6. Storage And Replay

A1 expects replayable facts for:

- EventStream actions/observations;
- MessageStream user/system/agent messages;
- RawTask and DraftTaskTree authoring changes;
- Published Task state;
- file change summaries;
- logging archives and manifests.

The product should prefer append-only or auditable mutation where user trust matters.

---

## 7. Trust Model

Trust in A1 is product-facing:

- user sees Task plan before execution;
- important actions ask for confirmation in Task context;
- results and file changes are visible;
- audit evidence is discoverable;
- diagnostics can be exported safely.

Raw logs and internal events are not the primary trust UI. They are evidence sources behind a user-readable projection.

---

## 8. Reserved But Not Implemented In 1.0

| Area | Reservation |
|---|---|
| Workspace communication protocol | Tool calls can evolve into a higher-level workspace operation protocol compatible with future MCP-like capability adapters. |
| Third-party tool registration | CapabilityCatalog and tool pool boundaries should leave room for later external capabilities. |
| Multi-agent execution | TaskBus and Agent templates should support future routing without forcing 1.0 UI to expose agent complexity. |
| Cross-session memory/RAG | Event/message/task/log archives should keep future retrieval possible. |

---

## 9. Legacy Source Material

Detailed historical architecture notes are archived under:

```text
docs/archive/legacy-2026-05-18/architecture/
```

They should be cited only when mining old reasoning into new plans, contracts, or decisions.

---

## 10. A1 Success Criteria

A1 succeeds if Plato 1.0 can ship without revisiting core boundaries:

- Task remains the UI anchor.
- Authoring and execution remain separate.
- UI/backend contract remains stable enough for split work.
- Trust/audit facts can be projected without changing event/message foundations.
- Local desktop packaging can hide frontend/backend process complexity from users.
