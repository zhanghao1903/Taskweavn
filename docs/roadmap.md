# TaskWeavn Roadmap

> Status: active
> Last Updated: 2026-05-18
> Maintained By: planning session
> Related: [Project Plan](project/roadmap.md), [Docs Operating Model](project/docs-operating-model.md), [Plato 1.0 Overview](product/versions/1.0/overview.md), [Capability Map](capabilities/index.md), [Current Architecture](architecture/current.md), [Release Records](releases/), [Legacy Archive](archive/legacy-2026-05-18/)

---

## 1. Purpose

This is the phase-level route for TaskWeavn and Plato.

It answers:

- what foundation is already implemented;
- what product/architecture baseline is current;
- which capabilities are next;
- where executable plans and release records live.

Executable work now starts from:

- [product version docs](product/versions/1.0/);
- [capability packets](capabilities/);
- [contracts](contracts/);
- [feature plan packages](plans/features/);
- [release plans](plans/release/).

Historical single-file plans and older architecture notes are preserved under [legacy archive](archive/legacy-2026-05-18/). They are reference material, not current workflow entry points.

---

## 2. Current Baseline

TaskWeavn has moved beyond the original single ReAct code-agent shape.

| Area | State | Notes |
|---|---:|---|
| Core Action / Observation / EventStream loop | Done | Phase 1 baseline. |
| CodeAction, Docker sandbox, AuditAgent, ThoughtStore | Done | Phase 2 baseline. |
| Session and workspace persistence | Done | Phase 3.1. |
| Interaction Layer substrate | Done | Phase 3.2-3.5: risk, autonomy, messages, bus, wait coordination. |
| AgentLoop interaction integration | Done | Phase 3.6. |
| LLM risk assessment | Done | Phase 3.7. |
| Derived session status | Done | Phase 3.8. |
| Task authoring foundation | Done as server-core baseline | RawTask, feasibility, DraftTaskTree, Collaborator authoring, authoring commands. |
| Task publishing foundation | Done as server-core baseline | TaskPublisher, SQLite TaskBus publish surfaces, SQLite publish control-plane stores, and framework-neutral API publish transport; full execution lifecycle remains. |
| Plato frontend baseline | Done as product/UI baseline | `frontend/src` contains the Main Page scaffold, state catalog, typed mock/API adapter, shared API types, and UI primitives; real backend integration remains. |
| Plato 1.0 productization | Active | UI/backend contract hardening, local sidecar API, real backend integration, settings, audit, packaging, diagnostics. |

The current product direction is **Task-first personal assistant**:

```text
User intent
  -> RawTask and feasibility assessment
  -> Collaborator drafts Task Tree List
  -> User edits/confirms Task nodes
  -> TaskPublisher publishes Tasks
  -> TaskBus dispatches execution
  -> UI observes topology, messages, confirmations, files, audit, and results
```

---

## 3. Current Control Documents

| Question | Canonical Entry |
|---|---|
| What is Plato 1.0 trying to ship? | [Plato 1.0 Overview](product/versions/1.0/overview.md) |
| What is in/out of 1.0? | [P0 Scope](product/versions/1.0/p0-scope.md) |
| What is missing from current system? | [1.0 Gap Analysis](product/versions/1.0/gap-analysis.md) |
| What can the system do now? | [Capability Map](capabilities/index.md) |
| What architecture version is current? | [Architecture A1](architecture/versions/a1-product-1.0/overview.md) |
| How do UI and backend agree? | [Contracts](contracts/) |
| How should docs and plans be maintained? | [Docs Operating Model](project/docs-operating-model.md) |
| What actually shipped? | [Release Records](releases/) |

---

## 4. Roadmap Principles

1. **Task is the primary user-facing object.** Chat is input and explanation, not the main state model.
2. **Authoring and execution are separate.** RawTask and DraftTaskTree stay outside TaskBus until publish.
3. **Messages remain one session stream.** Task message views are projections by `task_id`.
4. **TaskBus is the execution authority.** User, Collaborator, pipeline, scheduler, API, and custom trees publish through one boundary.
5. **Backend truth and UI viewmodels are separate.** UI Task cards are projections, not storage entities.
6. **Trust is product-facing.** Users need readable task plans, confirmations, file changes, audit evidence, and diagnostics.
7. **Reliability is a product feature.** Provider retry, failure classification, logging, and configuration are part of UX.
8. **Docs are infrastructure.** Current docs must route work; old docs are archived when superseded.

---

## 5. Phase History

| Phase | Status | Summary | Release Record |
|---|---:|---|---|
| Phase 1 | Done | Typed Action/Observation, EventStream, LLMClient, tools, ReAct loop, CLI. | Backfill if needed. |
| Phase 2 | Done | CodeAction, Docker sandbox, audit, SQLite ThoughtStore. | Backfill if needed. |
| Phase 3.1-3.8 | Done | Session/workspace persistence and Interaction Layer foundation. | [Phase 3 Interaction Layer through 3.8](releases/phase-3-interaction-layer-through-3-8.md) |
| Phase 3B | Done / follow-up | LLM provider reliability and configurable logging; centralized config remains planned. | [LLM provider](releases/llm-provider-reliability.md), [logging](releases/configurable-logging-system.md) |
| Phase 3C | Done as server-core | Task domain/UI viewmodel separation and Collaborator authoring foundation. | [Task model](releases/task-domain-ui-model-separation.md), [Collaborator authoring](releases/collaborator-agent-task-authoring.md) |
| Phase 3D | Partial | TaskPublisher, publish-time pipeline expansion, publish persistence, and API publish transport are done; task execution lifecycle remains. | [Task publishers](releases/task-publishers-schedule-api.md), [Publish persistence](releases/publish-persistence-foundation.md), [API publish transport](releases/api-publish-server-transport.md) |
| Phase 3E | Active | Plato 1.0 productization: UI, contracts, settings, audit, diagnostics, packaging. | Pending |

---

## 6. Active Productization Plan

The immediate roadmap is organized by Plato 1.0 capabilities.

| Capability | Status | Priority | Entry |
|---|---:|---:|---|
| Main Page real backend | active gap | P0 | [capability](capabilities/main-page-real-backend/) |
| UI/backend contract baseline | active | P0 | [contract](contracts/ui-backend/) |
| Settings and first run | planned gap | P0 | [capability](capabilities/settings-and-first-run/) |
| Task authoring | current / active | P0 | [capability](capabilities/task-authoring/) |
| Task execution | planned gap | P0 | [capability](capabilities/task-execution/) |
| Message and confirmation | current / active gap | P0 | [capability](capabilities/message-and-confirmation/) |
| Audit trust | planned gap | P0 | [capability](capabilities/audit-trust/) |
| File change summary | planned gap | P0 | [capability](capabilities/file-change-summary/) |
| Diagnostic bundle | planned gap | P0 | [capability](capabilities/diagnostic-bundle/) |
| Product error handling | planned gap | P0 | [capability](capabilities/product-error-handling/) |
| Packaging and distribution | planned | P0 | [capability](capabilities/packaging-and-distribution/) |
| Configuration control plane | planned | P1 / P0 dependency | [capability](capabilities/configuration-control-plane/) |

Every P0 gap should eventually route to a package under `docs/plans/features/<feature>/` or `docs/plans/release/`.

---

## 7. Later Phases

| Future Phase | Status | Notes |
|---|---:|---|
| Multi-agent task execution | planned | Agent templates, routing, claim/complete/fail lifecycle, shared workspace collaboration. |
| Memory / RAG / summarization | planned | Should operate over task/message/event/log archives after 1.0 foundations stabilize. |
| Third-party capability/tool platform | not_now | Architecture reserves room for MCP-like adapters, but 1.0 avoids marketplace complexity. |
| Multi-user collaboration | not_now | Personal assistant scope; multi-user would add heavy permission and interaction complexity. |

---

## 8. Immediate Sequencing Notes

The next work should not restart the UI from zero. `frontend/src` is now a tracked baseline. The remaining productization blocker is making the baseline real:

1. harden the UI/backend contract into specific contract files under [contracts/ui-backend/](contracts/ui-backend/);
2. build the local sidecar API shell for snapshot, command, and event surfaces;
3. connect Main Page to real session/task/message projections;
4. complete TaskBus claim/execute/complete/fail lifecycle;
5. integrate message/confirmation commands and SSE updates;
6. build File Change Summary, Audit Trust, product error handling, diagnostics, and packaging.

Publish persistence and API publish transport are complete enough for the next backend round. Completion-time `task_after`, agent assignment, and execution lifecycle remain backend blockers.

---

## 9. Maintenance Rules

When a plan completes:

1. update the plan package;
2. update the relevant capability packet;
3. update product gap analysis if P0/P1 changed;
4. update contracts if boundaries changed;
5. add or update a decision record if a costly choice changed;
6. add a release record for meaningful milestones;
7. update this roadmap only when sequencing, scope, or baseline changes.
