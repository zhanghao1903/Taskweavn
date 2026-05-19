# TaskWeavn Project Plan

> Status: active
> Last Updated: 2026-05-17
> Maintained By: planning session
> Phase Baseline: implementation completed through Phase 3.8 plus Phase 3C Task Domain and Collaborator Authoring server-core packages
> Related: [Global Roadmap](../roadmap.md), [Gap Registry](../gaps/), [Planning Workflow](../planning_workflow.md), [Architecture](../architecture/), [Phase 3 Release Record](../releases/phase-3-interaction-layer-through-3-8.md), [Collaborator Authoring Release](../releases/collaborator-agent-task-authoring.md), [User Traceability](../user_model/traceability.md)

---

## 1. Current Project Shape

TaskWeavn is being rebuilt from an early ReAct code agent into a Task-first collaboration system.

The original technical path came from [Interaction Layer Design](../architecture/interaction-layer.md). That path is still valid through Phase 3.8, but the next project plan is now adjusted by newer architecture work:

- Task is the core user interaction object.
- The UI should show Task Tree Lists, Task cards, confirmations, messages, and file summaries.
- RawTask and feasibility belong to Authoring Domain before Task Tree drafting.
- Collaborator plans against a read-only CapabilityCatalog and mutates authoring state through Authoring Commands, not the full concrete tool pool.
- Collaborator Agent becomes the system role that drafts and edits Task Trees with the user.
- TaskPublisher becomes the single boundary from user/collaborator/pipeline/scheduler/API/custom trees into TaskBus.
- Reliability and logging must be strengthened before large user tests.

The immediate authoring work is grounded in:

- [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md): task fit, feasibility, and capability boundary disclosure.
- [UN-101](../user_model/needs/UN-101-photo-curation-batch-screening.md): batch task trees with human review checkpoints.
- [UN-102](../user_model/needs/UN-102-courseware-html-generation.md): editable content-generation task trees.
- [UN-103](../user_model/needs/UN-103-car-purchase-decision-support.md): clarification/evaluation before high-risk information work.

Planning now uses a lightweight routing model:

```text
Architecture facts
  -> Gap Registry
  -> Plan package
  -> Implementation
  -> Release record
```

Do not convert every unplanned gap into a plan. Create a plan only when the gap
is selected for current or near-term execution, or when detailed technical
design is needed before implementation.

---

## 2. Completed Foundation

### Phase 1 — Core ReAct Agent

Status: done.

Delivered:

- Typed `Action` / `Observation`.
- EventStream abstraction.
- LLMClient facade.
- Basic tools and local runtime.
- ReAct loop and CLI entry.

### Phase 2 — CodeAction, Sandbox, Audit, Thought Store

Status: done.

Delivered:

- `CodeAction`.
- Docker sandbox execution.
- AuditAgent.
- SQLite ThoughtStore.
- Phase 2 user tests and examples.

### Phase 3.1-3.8 — Interaction Layer Foundation

Status: done.

| Slice | Delivered |
|---|---|
| 3.1 | Session, WorkspaceLayout, SQLite EventStream. |
| 3.2 | RiskScore, RiskAssessment, BaselineOnlyAssessor, AutonomyBehavior, action baseline risks. |
| 3.3 | AgentMessage, MessageStream, SQLite MessageStream, task_id correlation across events and messages. |
| 3.4 | InProcessMessageBus and Subscription. |
| 3.5 | AutonomyGate and WaitCoordinator. |
| 3.6a | AgentLoop gate/wait integration. |
| 3.6b | Async autonomy drain via pending decisions. |
| 3.6c | Minimum interactive CLI surface for autonomy gating. |
| 3.7 | LLMRiskAssessor and CompositeAssessor. |
| 3.8 | Derived Session.status from EventStream + MessageStream; `archived` remains stored override. |

See [Phase 3 release record](../releases/phase-3-interaction-layer-through-3-8.md).

---

## 3. Replanned Work Streams

The next project plan is organized as work streams instead of continuing the old linear Phase 3.9-3.13 order. Each stream can produce one or more implementation branches.

### P3B — Reliability And Observability

Status: accepted baseline, follow-up hardening planned. Priority: P0/P1.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| LLM provider/retry/thinking | [LLM provider plan](../plans/feature/llm-provider-retry-thinking.md) | Done: provider abstraction, retry policy, DeepSeek provider, thinking metadata, OpenRouter provider pinning. |
| Configurable logging | [Logging plan](../plans/feature/configurable-logging-system.md) | Done: global/session/category rules, JSONL + pretty display, same-process hot update, archives. |
| Centralized runtime configuration | [Runtime configuration plan](../plans/feature/centralized-runtime-configuration.md) | Follow-up: global/workspace/session/task config, effective snapshots, config store, config bus, hot updates. |

Acceptance:

- Temporary LLM failures do not immediately collapse long-running sessions.
- DeepSeek thinking can be enabled without losing reasoning/tool-call continuity.
- Testers can raise log level for a session/category and locate archived logs.
- Config changes should later be resolved, audited, and hot-applied through one shared control plane.

### P3C — Task Authoring Foundation

Status: server-core authoring foundation done; TaskPublisher bridge done in P3D. Priority: P0.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| Task domain/UI model separation | [Task model/UI separation](../plans/feature/task-domain-ui-model-separation.md) | Done: stable backend Task plus TaskCard/TaskNode ViewModel projection. |
| Collaborator Agent | [Collaborator Agent plan](../plans/feature/collaborator-agent-task-authoring.md) | Done: mock-LLM draft Task Tree generation, selected-node refinement, validation, publish boundary, and UI/API adapter. |
| RawTask and feasibility authoring flow | [Collaborator Agent plan](../plans/feature/collaborator-agent-task-authoring.md) | Done: RawTask, FeasibilityReport, RawTaskAsk, RawTaskAnswer, and Authoring Domain boundary before DraftTaskTree generation. |
| CapabilityCatalog, tool-pool boundary, and Authoring Command Protocol | [Tool Capability Layer](../architecture/tool-capability-layer.md), [Authoring Command Protocol](../architecture/authoring-command-protocol.md) | Done as first server-core boundary: capability-first planning, no workspace tool pool on Collaborator, command-first system-state mutation. |
| UI API contracts | [UI API interfaces](../plans/ui/ui-api-interfaces.md) | Done for authoring adapter surface; concrete transport and UI integration remain follow-ups. |

Acceptance:

- Natural language can be transformed into a draft Task Tree List.
- Ambiguous, unsupported, unsafe, or partially feasible user input can be represented as RawTask without entering TaskBus.
- User edits and confirmations are recorded as replayable facts.
- UI can render Task cards from projections without owning backend truth.
- Current server-core satisfies these through services, in-memory stores, mock LLM tests, and `CommandResult` adapter contracts. User-facing end-to-end validation waits for API transport and UI.

### P3D — Task Publishing And Pipeline

Status: TaskPublisher server-core release candidate done; pipeline loading partially implemented at publish-time. Priority: P0.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| TaskPublisher abstraction | [Task Publisher plan](../plans/feature/task-publishers-schedule-api.md), [release](../releases/task-publishers-schedule-api.md) | Done: TaskBus-backed publisher, SQLite TaskBus, custom tree parser, idempotent publish service, scheduler/API adapters, publish-time pipeline expansion. |
| Pipeline task loading | [Pipeline loading plan](../plans/feature/pipeline-task-loading.md) | Partial: task_before/task_begin publish-time expansion done; task_after completion-time orchestration remains. |
| Agent assignment constraints | [Pipeline loading plan](../plans/feature/pipeline-task-loading.md) | Task can require/prefer an Agent Template while preserving capability validation. |

Acceptance:

- All publish sources go through one validation and publish boundary.
- Pipeline tasks are normal Tasks with publisher metadata.
- API and scheduled publishing are idempotent and auditable.

### P3E — Task-first UI

Status: active planning; frontend implementation should restart from Figma UI baseline 1.0. Priority: P0.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| Plato MVP product/UX baseline | [Plato MVP PRD](../product/plato-mvp-prd.md), [Main Page UX Flow](../product/plato-main-page-ux-flow.md) | Product scope, user path, screen states, and Main Page behavior. |
| Figma UI baseline 1.0 | [Figma UI Baseline](../product/plato-figma-ui-baseline.md) | Current visual/layout source for implementation. |
| Frontend technical design | [Plato Frontend Technical Design](../product/plato-frontend-technical-design.md) | Technology choice, architecture, state/API boundaries, implementation slices. |
| Early UI interaction model | [Task-first UI overview](../plans/task-first-ui-interaction.md) | Superseded as implementation plan; retained as concept seed. |
| Early UI sub-designs | [UI plan directory](../plans/ui/) | Historical planning archive unless explicitly pulled into new frontend work. |
| Result packaging cards | [Result packaging plan](../plans/feature/result-packaging-agent-cards.md) | Package suitable information-style answers into UI card sets through normal Tasks. |

Acceptance:

- Users can see the Task topology and interact with Task cards.
- Session message stream and task-scoped projections are consistent.
- Suitable information-style answers can render as card sets without losing the raw text answer.
- Finished Task Nodes are read-only; pending/running nodes expose only valid actions.
- Frontend work starts from a clean scaffold and Figma-state stories, not the deprecated experimental frontend.

### P4 — Multi-Agent Task Execution

Status: planned. Priority: P1 after P3C/P3D.

Focus:

- Agent templates and capabilities.
- TaskBus claim/complete/fail lifecycle.
- Agent assignment constraints and fair dispatch.
- Shared workspace collaboration.
- Multi-agent event/message/log replay.

### P5 — Memory, Retrieval, Summarization, Evaluation

Status: planned. Priority: P1/P2 after UI and TaskBus stabilize.

Focus:

- In-session RAG over events/messages/tasks/logs.
- Cross-session RAG with privacy boundaries.
- Task-aware summarization.
- Long-running user test suites.
- Cost/quota-aware context packing.

---

## 4. Superseded Or Moved Items

| Old Item | New Plan |
|---|---|
| Phase 3.9 PlanTool | Merged into Collaborator Agent and draft Task Tree authoring. A simple file-based plan tool can be revived later as support infrastructure. |
| Phase 3.10 shared/ append-only | Moved to P4 multi-agent/shared workspace work. |
| Phase 3.11 in-session RAG | Moved to P5 after stable Task/message/log archives. |
| Phase 3.12 cross-session RAG | Moved to P5 and remains optional. |
| Phase 3.13 conversation summarization | Moved to P5; should become Task-aware summarization. |

---

## 5. Immediate Next Work Queue

Recommended implementation order:

1. UI/backend contract baseline and frontend/backend snapshot/event boundary.
2. Local sidecar API shell for Plato UI.
3. Main Page real backend integration from the frontend baseline.
4. Pipeline task loading completion-time orchestration and agent assignment.
5. TaskBus execution lifecycle.
6. Publish audit query/debug API and concrete HTTP framework binding, if needed by UI/API integration.
7. Result Packaging Agent and card-based result presentation.
8. Persistent authoring stores.
9. Centralized runtime configuration system.

LLM Provider reliability, configurable logging, the Task-first data model, Collaborator authoring, TaskPublisher, publish persistence, API publish transport, and frontend baseline now have server-core or UI baseline release candidates. The remaining order moves into contract, sidecar, real backend integration, execution lifecycle, and trust surfaces while centralized configuration stays as a control-plane hardening follow-up.

The source of truth for gap status is [Gap Registry](../gaps/).

---

## 6. Project Governance

When an implementation session finishes a package:

1. Update the package plan under `docs/plans/` or `docs/issues/`.
2. Update [Gap Registry](../gaps/) if status, priority, or plan routing changed.
3. Update this file if status or priority changed.
4. Update [Global Roadmap](../roadmap.md) if phase sequencing changed.
5. Add/update an ADR under [../decisions/](../decisions/) if a decision changed.
5. Add/update a release record under [../releases/](../releases/) if a milestone completed.

This project plan is intentionally operational: it should help pick the next branch and understand why that branch matters.
