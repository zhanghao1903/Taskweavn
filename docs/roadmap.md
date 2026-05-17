# TaskWeavn Roadmap

> Status: active
> Last Updated: 2026-05-17
> Maintained By: planning session
> Related: [Project Plan](project/roadmap.md), [Planning Workflow](planning_workflow.md), [Architecture Decisions](decisions/), [Release Records](releases/), [User Traceability](user_model/traceability.md)

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
| Task-first architecture plans | In progress | Task domain/UI ViewModel separation, Collaborator authoring, and TaskPublisher server-core packages are done; publish-time pipeline expansion is done, while completion-time task_after orchestration remains. |
| Reliability and observability plans | Accepted baseline | LLM provider/retry/thinking and configurable logging are done; centralized runtime config remains a follow-up control-plane plan. |

The project is now re-baselined around **Task-first interaction**:

```text
User intent
  -> RawTask and feasibility assessment
  -> Collaborator Agent drafts Task Tree List
  -> User edits/confirms Task nodes
  -> TaskPublisher publishes normal Tasks
  -> TaskBus dispatches to Agents
  -> UI observes Task topology, messages, confirmations, files, and summaries
```

This is a larger shift than the original Interaction Layer plan. The Interaction Layer remains the foundation, but the next major work should strengthen reliability, observability, Task modeling, and publish flows before returning to RAG and summarization.

Current user-need drivers:

| Need | Roadmap Impact |
|---|---|
| [UN-105](user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md) | Makes RawTask feasibility and Authoring Domain a near-term P0, because users need to judge task fit before execution. |
| [UN-101](user_model/needs/UN-101-photo-curation-batch-screening.md) | Validates Task-first authoring for batch workflows with review checkpoints. |
| [UN-102](user_model/needs/UN-102-courseware-html-generation.md) | Validates editable Task Trees for content-generation workflows. |
| [UN-103](user_model/needs/UN-103-car-purchase-decision-support.md) | Keeps high-risk information tasks in clarification/evaluation flow until constraints and evidence expectations are explicit. |

---

## 3. Roadmap Principles

1. **Task is the primary user-facing object.** The UI should organize work around Task Tree Lists and Task Nodes, not files or raw chat turns.
2. **Authoring and execution are separate domains.** RawTask, feasibility, clarification asks, and DraftTaskTree stay in Authoring Domain; only PublishedTasks enter Execution TaskBus.
3. **Planning is capability-first; system state is command-first.** Collaborator should see a read-only CapabilityCatalog and submit Authoring Commands for RawTask/DraftTaskTree changes, not mount the full workspace/external tool pool.
4. **Messages remain one session stream.** Messages carry `session_id`, `agent_id`, and `task_id`; Task views are projections over the same stream, not a separate Task message table.
5. **TaskBus is the execution authority.** User, Collaborator, pipeline, scheduler, API, and custom tree inputs all publish normal Tasks through a publisher layer.
6. **Domain model and UI model are separate.** Backend Task stays small and stable; UI Task cards are projections with temporary view state.
7. **Interactions must be replayable.** Confirmation actions, user guidance, Task patches, publish decisions, and file summaries must be reconstructible from backend facts.
8. **Reliability and observability are now product features.** LLM failures, retry behavior, provider routing, and logging must be first-class before complex long-running tasks become usable.
9. **Docs are part of the system control plane.** When a plan is completed, update the plan file, this roadmap if phase direction changes, ADRs if decisions changed, and releases if a phase/work package is completed.
10. **User-need traceability is required for major changes.** Architecture and plan docs should cite `UN-*` records when they introduce or change boundaries, priorities, or product-facing behavior.

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
| Phase 3C.1 | Done | Task domain/UI ViewModel separation. | [Task Domain and UI ViewModel Separation](releases/task-domain-ui-model-separation.md) |
| Phase 3C.2 | Done | Collaborator Agent, RawTask feasibility, Authoring Commands, DraftTaskTree authoring, and publish boundary. | [Collaborator Agent And Task Authoring](releases/collaborator-agent-task-authoring.md) |

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

Status: accepted baseline, with follow-up control-plane hardening planned.

Why now: user testing and long-running task execution need stable LLM behavior and debuggable system state.

Work packages:

| Work | Plan | Priority |
|---|---|---:|
| LLM Provider abstraction, retry, DeepSeek thinking, OpenRouter routing | [LLM provider plan](plans/feature/llm-provider-retry-thinking.md) | Done |
| Configurable hierarchical logging, JSONL/pretty sinks, session inheritance, hot reload | [Logging plan](plans/feature/configurable-logging-system.md) | Done |
| Centralized hierarchical runtime configuration and hot updates | [Runtime configuration plan](plans/feature/centralized-runtime-configuration.md) | Follow-up |
| Architecture/reference docs sync after rename and Phase 3.8 | Follow-up doc maintenance | P1 |

Exit criteria:

- LLM requests have provider-level retry and structured failure records. Done.
- DeepSeek official provider supports thinking mode and preserves reasoning metadata. Done.
- OpenRouter can pin provider routing. Done.
- Logs can be configured globally and per session. Done.
- Testers can turn up logging for selected categories through same-process control APIs and inspect session archives. Done.
- Global/workspace/session/task configuration should later be resolved into immutable effective snapshots through the centralized runtime configuration plan.
- Hot-updatable config changes should eventually share a ConfigBus instead of feature-local control APIs.

### Phase 3C — Task Authoring Foundation

Status: server-core authoring foundation done; TaskPublisher bridge is done in Phase 3D.

Why now: Task-first UI requires the backend to represent draft Tasks, UI projections, user confirmations, and task-scoped guidance.

Work packages:

| Work | Plan | Priority |
|---|---|---:|
| Split backend Task domain model from UI ViewModel/projection | [Task model/UI separation](plans/feature/task-domain-ui-model-separation.md) | Done |
| Collaborator Agent and Authoring Command Protocol | [Collaborator Agent plan](plans/feature/collaborator-agent-task-authoring.md), [Authoring Command Protocol](architecture/authoring-command-protocol.md) | Done |
| RawTask, feasibility assessment, and authoring-domain clarification flow | [Collaborator Agent plan](plans/feature/collaborator-agent-task-authoring.md) | Done |
| Minimal CapabilityCatalog, tool-pool boundary, and Authoring Command Protocol | [Tool Capability Layer](architecture/tool-capability-layer.md), [Authoring Command Protocol](architecture/authoring-command-protocol.md) | Done as server-core boundary; future tool platform remains reserved |
| Task-first UI API contracts | [UI API interfaces](plans/ui/ui-api-interfaces.md) | Done for authoring surface; transport pending |
| Task interaction replay model | Covered by Task model and Collaborator plans | P0 |

Exit criteria:

- User natural language can produce a draft Task Tree List.
- Ambiguous or impossible user input can produce a RawTask with feasibility status and clarification asks instead of a forced Task Tree.
- Task Node updates and confirmations are modeled before execution.
- Backend can replay confirmation actions, guidance, and Task patches.
- UI can render Task cards without depending on raw backend Task internals.
- The first server-core authoring package satisfies these as local protocols/services with mock LLM tests; UI transport and persistent authoring stores remain follow-ups.

### Phase 3D — Task Publishing And Pipeline

Status: TaskPublisher server-core release candidate done; pipeline loading partially implemented at publish-time.

Why now: after Task authoring exists, every publish source needs one safe path into TaskBus.

Work packages:

| Work | Plan | Priority |
|---|---|---:|
| TaskPublisher abstraction for user/collaborator/pipeline/scheduler/API/custom tree | [Task Publisher plan](plans/feature/task-publishers-schedule-api.md), [release](releases/task-publishers-schedule-api.md) | Done, including SQLite TaskBus |
| Pipeline task auto-loading and agent assignment constraints | [Pipeline loading plan](plans/feature/pipeline-task-loading.md) | Partial: task_before/task_begin publish-time expansion done; task_after and assignment semantics remain P0 |
| TaskBus publish/claim state authority hardening | Future implementation plan | P0 |

Exit criteria:

- All publish sources normalize into a Task Tree and call TaskBus.
- Pipeline tasks are normal Tasks, not special runtime objects.
- Tasks can specify required or preferred Agent templates without bypassing capability checks.
- Publish operations are auditable and idempotent where required.

### Phase 3E — Task-first UI System

Status: active planning; frontend implementation should restart from Figma UI baseline 1.0.

Why now: CLI has reached its usefulness ceiling. The product value is in Task topology, Task cards, confirmations, and real-time message streams.

Work packages:

| Work | Plan | Priority |
|---|---|---:|
| Plato MVP product requirements | [Plato MVP PRD](product/plato-mvp-prd.md) | Done as product baseline |
| Main Page UX flow and screen states | [Main Page UX Flow](product/plato-main-page-ux-flow.md) | Done as UX baseline |
| Figma UI baseline 1.0 | [Figma UI Baseline](product/plato-figma-ui-baseline.md) | Done as visual/source baseline |
| Frontend restart technical design | [Plato Frontend Technical Design](product/plato-frontend-technical-design.md) | Done as implementation design |
| Early UI interaction overview | [Task-first UI plan](plans/task-first-ui-interaction.md) | Superseded as implementation plan; retained as concept seed |
| Early UI sub-designs | [UI plan directory](plans/ui/) | Superseded unless explicitly referenced by new frontend work |
| Result Packaging Agent and card-based result presentation | [Result packaging plan](plans/feature/result-packaging-agent-cards.md) | P1 |
| Clean frontend scaffold and Figma-state stories | [Plato Frontend Technical Design](product/plato-frontend-technical-design.md) | P0 |
| UI API Contract | Future document: `docs/product/plato-ui-api-contract.md` | P0 |
| API-backed prototype | Future implementation plan after UI API Contract | P0 |

Exit criteria:

- User can enter natural language and inspect a generated Task Tree List.
- Selecting a Task Node switches to task-scoped interaction.
- Task cards show confirmations, status, messages, and file change summary.
- Information-style results can be rendered as card sets when the result shape benefits from structure.
- Session message stream and Task projections stay consistent over the same message source.
- Frontend components are built from Figma UI baseline 1.0 through stories/fixtures, not from the deprecated experimental frontend.

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

1. **Plato frontend engineering reset** — clean `frontend/` scaffold, design tokens, primitives, and Figma-state stories from [Frontend Technical Design](product/plato-frontend-technical-design.md).
2. **UI API Contract** — define `plato-ui-api-contract.md` around snapshot/query/command/event shapes before real backend integration.
3. **Persistent publish stores and server transport** — SQLite TaskBus is done; remaining work is durable publisher/scheduler stores and exposing API publisher semantics through a real transport.
4. **Pipeline task loading completion** — completion-time `task_after`, pipeline config persistence, and agent assignment semantics.
5. **Result packaging and card presentation** — richer result display for information-style answers.
6. **Persistent authoring stores** — make RawTask/DraftTaskTree authoring durable beyond in-memory tests.
7. **TaskBus multi-agent execution hardening** — execution semantics after publish model stabilizes.
8. **Centralized runtime configuration** — shared control plane for logging/autonomy/audit/LLM/Task/UI behavior once the Task-facing server model is concrete enough to avoid overfitting.

LLM Provider reliability, configurable logging, Task domain/UI separation, Collaborator authoring, and TaskPublisher are complete enough for the next round. The immediate product blocker is now the Plato frontend engineering reset plus UI API Contract; server transport and pipeline completion remain the next backend blockers.

---

## 8. Maintenance Rules

When a plan is completed:

1. Update the original plan file status, implementation references, actual result, tests, and follow-ups.
2. Update [Project Plan](project/roadmap.md) if the completed work changes the phase status or next priority.
3. Update this roadmap if the completion changes phase direction or milestone sequencing.
4. Add or update an ADR under [decisions/](decisions/) if an architectural decision was made or reversed.
5. Add or update a release record under [releases/](releases/) if a phase, milestone, or important feature slice completed.

This rule keeps the planning session useful as a global overview rather than a pile of stale plans.
