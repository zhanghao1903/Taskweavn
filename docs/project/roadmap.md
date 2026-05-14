# TaskWeavn Project Plan

> Status: active
> Last Updated: 2026-05-14
> Maintained By: planning session
> Phase Baseline: implementation completed through Phase 3.8
> Related: [Global Roadmap](../roadmap.md), [Planning Workflow](../planning_workflow.md), [Phase 3 Release Record](../releases/phase-3-interaction-layer-through-3-8.md)

---

## 1. Current Project Shape

TaskWeavn is being rebuilt from an early ReAct code agent into a Task-first collaboration system.

The original technical path came from [Interaction Layer Design](../architecture/interaction-layer.md). That path is still valid through Phase 3.8, but the next project plan is now adjusted by newer architecture work:

- Task is the core user interaction object.
- The UI should show Task Tree Lists, Task cards, confirmations, messages, and file summaries.
- RawTask and feasibility belong to Authoring Domain before Task Tree drafting.
- Collaborator Agent becomes the system role that drafts and edits Task Trees with the user.
- TaskPublisher becomes the single boundary from user/collaborator/pipeline/scheduler/API/custom trees into TaskBus.
- Reliability and logging must be strengthened before large user tests.

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

Status: in progress; first package accepted and Collaborator Agent active. Priority: P0.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| Task domain/UI model separation | [Task model/UI separation](../plans/feature/task-domain-ui-model-separation.md) | Done: stable backend Task plus TaskCard/TaskNode ViewModel projection. |
| Collaborator Agent | [Collaborator Agent plan](../plans/feature/collaborator-agent-task-authoring.md) | In progress: generate draft Task Trees, patch selected Task Nodes, validate/publish draft tasks. |
| RawTask and feasibility authoring flow | [Collaborator Agent plan](../plans/feature/collaborator-agent-task-authoring.md) | Add RawTask, FeasibilityReport, RawTaskAsk, and Authoring Domain boundary before DraftTaskTree generation. |
| UI API contracts | [UI API interfaces](../plans/ui/ui-api-interfaces.md) | Define APIs for Task lists, selected Task detail, messages, confirmations, file summaries. |

Acceptance:

- Natural language can be transformed into a draft Task Tree List.
- Ambiguous, unsupported, unsafe, or partially feasible user input can be represented as RawTask without entering TaskBus.
- User edits and confirmations are recorded as replayable facts.
- UI can render Task cards from projections without owning backend truth.

### P3D — Task Publishing And Pipeline

Status: planned. Priority: P0.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| TaskPublisher abstraction | [Task Publisher plan](../plans/feature/task-publishers-schedule-api.md) | Normalize and publish user/collaborator/pipeline/scheduler/API/custom Task Trees. |
| Pipeline task loading | [Pipeline loading plan](../plans/feature/pipeline-task-loading.md) | Auto-publish before/begin/after tasks as normal TaskBus tasks. |
| Agent assignment constraints | [Pipeline loading plan](../plans/feature/pipeline-task-loading.md) | Task can require/prefer an Agent Template while preserving capability validation. |

Acceptance:

- All publish sources go through one validation and publish boundary.
- Pipeline tasks are normal Tasks with publisher metadata.
- API and scheduled publishing are idempotent and auditable.

### P3E — Task-first UI

Status: planned. Priority: P0.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| UI interaction model | [Task-first UI overview](../plans/task-first-ui-interaction.md) | Overall layout, primary regions, interaction workflows. |
| UI sub-designs | [UI plan directory](../plans/ui/) | Task tree, task detail, session stream, confirmations, file summaries, task-scoped chat. |
| Result packaging cards | [Result packaging plan](../plans/feature/result-packaging-agent-cards.md) | Package suitable information-style answers into UI card sets through normal Tasks. |
| Visual references | [Visual reference](../plans/ui/visual-reference.md) | Use current UI images as non-final layout references. |

Acceptance:

- Users can see the Task topology and interact with Task cards.
- Session message stream and task-scoped projections are consistent.
- Suitable information-style answers can render as card sets without losing the raw text answer.
- Finished Task Nodes are read-only; pending/running nodes expose only valid actions.

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

1. Collaborator Agent and Task authoring tools.
2. TaskPublisher abstraction.
3. Pipeline task loading and agent assignment.
4. Result Packaging Agent and card-based result presentation.
5. API-backed Task-first UI prototype.
6. Centralized runtime configuration system.

LLM Provider reliability and configurable logging are complete enough for the next round of server-core work. The Task-first data model now has a release candidate, so the remaining order moves into authoring, publishing, and UI flows while centralized configuration stays as a control-plane hardening follow-up.

---

## 6. Project Governance

When an implementation session finishes a package:

1. Update the package plan under `docs/plans/` or `docs/issues/`.
2. Update this file if status or priority changed.
3. Update [Global Roadmap](../roadmap.md) if phase sequencing changed.
4. Add/update an ADR under [../decisions/](../decisions/) if a decision changed.
5. Add/update a release record under [../releases/](../releases/) if a milestone completed.

This project plan is intentionally operational: it should help pick the next branch and understand why that branch matters.
