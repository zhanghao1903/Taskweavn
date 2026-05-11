# TaskWeavn Roadmap

> Status: active
> Last Updated: 2026-05-11
> Maintained By: planning session
> Related: [Project Plan](project/roadmap.md), [Planning Workflow](planning_workflow.md), [Architecture Decisions](decisions/), [Release Records](releases/)

---

## 1. Purpose

This document is the phase-level route for TaskWeavn. It answers:

- what is already done;
- what changed in the architecture direction;
- what should be built next;
- which planning documents must be updated when work is completed.

Detailed executable work packages live under [plans/](plans/), [plans/feature/](plans/feature/), and [issues/](issues/). This roadmap stays higher level and should not duplicate every API detail.

---

## 2. Current Baseline

TaskWeavn has moved past the original "single ReAct agent with tools" shape. The current baseline is:

| Area | State | Notes |
|---|---:|---|
| Core Action/Observation/EventStream loop | Done | Phase 1 baseline. |
| CodeAction, Docker sandbox, AuditAgent, ThoughtStore | Done | Phase 2 baseline. |
| Session/workspace persistence | Done | Phase 3.1. |
| Interaction Layer risk/autonomy/message/bus/wait substrate | Done | Phase 3.2-3.5. |
| AgentLoop autonomy integration and minimum CLI surface | Done | Phase 3.6. |
| LLMRiskAssessor and CompositeAssessor | Done | Phase 3.7. |
| Derived Session.status | Done | Phase 3.8; stored status is a hint except `archived`. |
| Task-first architecture plans | Planned | UI, Collaborator Agent, Task ViewModel, Pipeline, Publisher. |
| Reliability and observability plans | Planned | LLM provider/retry/thinking; configurable logging. |

The project is now re-baselined around **Task-first interaction**:

```text
User intent
  -> Collaborator Agent drafts Task Tree List
  -> User edits/confirms Task nodes
  -> TaskPublisher publishes normal Tasks
  -> TaskBus dispatches to Agents
  -> UI observes Task topology, messages, confirmations, files, and summaries
```

This is a larger shift than the original Interaction Layer plan. The Interaction Layer remains the foundation, but the next major work should strengthen reliability, observability, Task modeling, and publish flows before returning to RAG and summarization.

---

## 3. Roadmap Principles

1. **Task is the primary user-facing object.** The UI should organize work around Task Tree Lists and Task Nodes, not files or raw chat turns.
2. **Messages remain one session stream.** Messages carry `session_id`, `agent_id`, and `task_id`; Task views are projections over the same stream, not a separate Task message table.
3. **TaskBus is the execution authority.** User, Collaborator, pipeline, scheduler, API, and custom tree inputs all publish normal Tasks through a publisher layer.
4. **Domain model and UI model are separate.** Backend Task stays small and stable; UI Task cards are projections with temporary view state.
5. **Interactions must be replayable.** Confirmation actions, user guidance, Task patches, publish decisions, and file summaries must be reconstructible from backend facts.
6. **Reliability and observability are now product features.** LLM failures, retry behavior, provider routing, and logging must be first-class before complex long-running tasks become usable.
7. **Docs are part of the system control plane.** When a plan is completed, update the plan file, this roadmap if phase direction changes, ADRs if decisions changed, and releases if a phase/work package is completed.

---

## 4. Completed Phase History

| Phase | Status | Summary | Release Record |
|---|---:|---|---|
| Phase 1 | Done | Typed Action/Observation, EventStream, LLMClient, tools, ReAct loop, CLI. | Later backfill if needed. |
| Phase 2 | Done | CodeAction, Docker sandbox, audit, SQLite ThoughtStore. | Later backfill if needed. |
| Phase 3.1 | Done | Session, workspace layout, SQLite EventStream. | [Phase 3 through 3.8](releases/phase-3-interaction-layer-through-3-8.md) |
| Phase 3.2 | Done | Risk model, AutonomyBehavior, baseline action risks. | [Phase 3 through 3.8](releases/phase-3-interaction-layer-through-3-8.md) |
| Phase 3.3 | Done | AgentMessage, MessageStream, SQLite messages, task_id correlation. | [Phase 3 through 3.8](releases/phase-3-interaction-layer-through-3-8.md) |
| Phase 3.4 | Done | InProcessMessageBus and Subscription. | [Phase 3 through 3.8](releases/phase-3-interaction-layer-through-3-8.md) |
| Phase 3.5 | Done | AutonomyGate and WaitCoordinator. | [Phase 3 through 3.8](releases/phase-3-interaction-layer-through-3-8.md) |
| Phase 3.6 | Done | AgentLoop gating, async response drain, minimum CLI autonomy surface. | [Phase 3 through 3.8](releases/phase-3-interaction-layer-through-3-8.md) |
| Phase 3.7 | Done | LLMRiskAssessor and CompositeAssessor. | [Phase 3 through 3.8](releases/phase-3-interaction-layer-through-3-8.md) |
| Phase 3.8 | Done | Derived Session.status from EventStream + MessageStream. | [Phase 3 through 3.8](releases/phase-3-interaction-layer-through-3-8.md) |

---

## 5. Revised Phase Plan

### Phase 3A — Interaction Substrate

Status: done.

Scope:

- Session/workspace persistence.
- EventStream and MessageStream persistence.
- Risk/autonomy model.
- MessageBus and wait coordination.
- AgentLoop interaction integration.
- LLM risk assessment.
- Derived session status.

This phase created the protocol substrate needed by Task-first UI and TaskBus work.

### Phase 3B — Reliability And Observability

Status: planned.

Why now: user testing and long-running task execution need stable LLM behavior and debuggable system state.

Work packages:

| Work | Plan | Priority |
|---|---|---:|
| LLM Provider abstraction, retry, DeepSeek thinking, OpenRouter routing | [LLM provider plan](plans/feature/llm-provider-retry-thinking.md) | P0 |
| Configurable hierarchical logging, JSONL/pretty sinks, session inheritance, hot reload | [Logging plan](plans/feature/configurable-logging-system.md) | P0 |
| Architecture/reference docs sync after rename and Phase 3.8 | Follow-up doc maintenance | P1 |

Exit criteria:

- LLM requests have provider-level retry and structured failure records.
- DeepSeek official provider supports thinking mode and preserves reasoning metadata.
- OpenRouter can pin provider routing.
- Logs can be configured globally and per session.
- Testers can turn up logging for selected categories without restarting the whole mental model.

### Phase 3C — Task Authoring Foundation

Status: planned.

Why now: Task-first UI requires the backend to represent draft Tasks, UI projections, user confirmations, and task-scoped guidance.

Work packages:

| Work | Plan | Priority |
|---|---|---:|
| Split backend Task domain model from UI ViewModel/projection | [Task model/UI separation](plans/feature/task-domain-ui-model-separation.md) | P0 |
| Collaborator Agent and Task authoring tools | [Collaborator Agent plan](plans/feature/collaborator-agent-task-authoring.md) | P0 |
| Task-first UI API contracts | [UI API interfaces](plans/ui/ui-api-interfaces.md) | P0 |
| Task interaction replay model | Covered by Task model and Collaborator plans | P0 |

Exit criteria:

- User natural language can produce a draft Task Tree List.
- Task Node updates and confirmations are modeled before execution.
- Backend can replay confirmation actions, guidance, and Task patches.
- UI can render Task cards without depending on raw backend Task internals.

### Phase 3D — Task Publishing And Pipeline

Status: planned.

Why now: after Task authoring exists, every publish source needs one safe path into TaskBus.

Work packages:

| Work | Plan | Priority |
|---|---|---:|
| TaskPublisher abstraction for user/collaborator/pipeline/scheduler/API/custom tree | [Task Publisher plan](plans/feature/task-publishers-schedule-api.md) | P0 |
| Pipeline task auto-loading and agent assignment constraints | [Pipeline loading plan](plans/feature/pipeline-task-loading.md) | P0 |
| TaskBus publish/claim state authority hardening | Future implementation plan | P0 |

Exit criteria:

- All publish sources normalize into a Task Tree and call TaskBus.
- Pipeline tasks are normal Tasks, not special runtime objects.
- Tasks can specify required or preferred Agent templates without bypassing capability checks.
- Publish operations are auditable and idempotent where required.

### Phase 3E — Task-first UI System

Status: planned.

Why now: CLI has reached its usefulness ceiling. The product value is in Task topology, Task cards, confirmations, and real-time message streams.

Work packages:

| Work | Plan | Priority |
|---|---|---:|
| UI interaction overview | [Task-first UI plan](plans/task-first-ui-interaction.md) | P0 |
| UI sub-designs | [UI plan directory](plans/ui/) | P0 |
| Visual reference iteration | [Visual reference](plans/ui/visual-reference.md) | P1 |
| API-backed prototype | Future implementation plan | P0 |

Exit criteria:

- User can enter natural language and inspect a generated Task Tree List.
- Selecting a Task Node switches to task-scoped interaction.
- Task cards show confirmations, status, messages, and file change summary.
- Session message stream and Task projections stay consistent over the same message source.

### Phase 4 — Multi-Agent Task Execution

Status: planned.

Why later: the Interaction Layer has multi-agent pre-wiring, but full multi-agent execution should wait until Task authoring, publishing, logging, and UI projection are stable.

Scope:

- Agent templates and capabilities.
- TaskBus claim/complete/fail lifecycle.
- Agent assignment constraints.
- Cross-session/shared workspace collaboration.
- Parallel execution policies.
- Stronger audit and replay views.

### Phase 5 — Memory, RAG, Summarization, And Evaluation

Status: planned / postponed from original Phase 3.11-3.13.

Scope:

- In-session retrieval over EventStream/MessageStream.
- Cross-session retrieval with privacy boundaries.
- Conversation and Task summarization.
- Long-running evaluation sets.
- Cost/quota-aware context packing.

These remain valuable, but they should not be the next immediate build target because Task-first interaction and reliability are now more foundational.

---

## 6. Replanning From The Old Interaction Layer Slices

| Original Slice | New Treatment |
|---|---|
| 3.9 PlanTool | Superseded by Collaborator Agent + draft Task authoring. A simple plan file tool may return later as a support tool, not the main UX object. |
| 3.10 shared/ append-only collaboration | Moved to Phase 4 after TaskBus and multi-agent execution are concrete. |
| 3.11 in-session RAG | Moved to Phase 5 after stable Task/message/log archives exist. |
| 3.12 cross-session RAG | Moved to Phase 5 and remains optional pending privacy design. |
| 3.13 conversation summarization | Moved to Phase 5; should summarize Tasks, messages, logs, and file changes, not only chat turns. |

---

## 7. Near-Term Execution Order

Recommended order for upcoming implementation sessions:

1. **LLM Provider reliability** — retry, DeepSeek thinking, provider routing.
2. **Configurable logging** — global/session config, category levels, hot update, archives.
3. **Task model and UI ViewModel separation** — data boundary before UI implementation.
4. **Collaborator Agent and Task authoring tools** — natural language to draft Task Tree.
5. **TaskPublisher abstraction** — one publish path for every source.
6. **Pipeline task loading** — before/begin/after Task auto-publication.
7. **Task-first UI prototype** — after backend projection APIs exist.
8. **TaskBus multi-agent execution hardening** — execution semantics after publish model stabilizes.

The first two items are operationally important: without reliable LLM calls and configurable logs, user testing will be noisy and hard to diagnose.

---

## 8. Maintenance Rules

When a plan is completed:

1. Update the original plan file status, implementation references, actual result, tests, and follow-ups.
2. Update [Project Plan](project/roadmap.md) if the completed work changes the phase status or next priority.
3. Update this roadmap if the completion changes phase direction or milestone sequencing.
4. Add or update an ADR under [decisions/](decisions/) if an architectural decision was made or reversed.
5. Add or update a release record under [releases/](releases/) if a phase, milestone, or important feature slice completed.

This rule keeps the planning session useful as a global overview rather than a pile of stale plans.
