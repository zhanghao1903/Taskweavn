# Release Record: Phase 3 Interaction Layer Through 3.8

> Status: done
> Date: 2026-05-11
> Scope: Phase 3.1-3.8
> Related: [Legacy Interaction Layer Design](../archive/legacy-2026-05-18/architecture/interaction-layer.md), [Roadmap](../roadmap.md), [Project Plan](../project/roadmap.md)

---

## 1. Summary

Phase 3.1-3.8 delivered the Interaction Layer substrate for TaskWeavn:

- persistent sessions and workspace layout;
- persistent EventStream and MessageStream;
- risk/autonomy model;
- message bus and wait coordination;
- AgentLoop integration for user confirmation and async response drain;
- LLM-based risk assessment;
- derived Session.status.

This release is important because it changes TaskWeavn from a simple single-run CLI agent into a system that can support long-running sessions, user confirmation, message aggregation, and future Task-first UI projections.

---

## 2. Delivered Slices

| Slice | Status | Change Summary | Representative Commit |
|---|---:|---|---|
| 3.1 | done | Session abstraction, workspace layout, SQLite EventStream. | `b545c79` |
| 3.2 | done | Risk model, AutonomyBehavior, baseline action risk calibration. | `dd23250` |
| 3.3 | done | AgentMessage, MessageStream, SQLite MessageStream, task_id correlation. | `825ae8d` |
| 3.4 | done | InProcessMessageBus, Subscription, wait_for_response. | `9624cd8` |
| 3.5 | done | AutonomyGate and WaitCoordinator. | `5eaa864` |
| 3.6a | done | AgentLoop integrates gate/wait coordinator. | `16e3bb3` |
| 3.6b | done | Async autonomy drain for pending decisions. | `ca29b83` |
| 3.6c | done | Minimum CLI autonomy surface. | `92bc64a` |
| 3.7 | done | LLMRiskAssessor and CompositeAssessor. | `7813042` |
| 3.8 | done | Derived Session.status from events and messages; `archived` remains stored override. | `00166c5` on `main` after TaskWeavn rename/merge. |

---

## 3. Key Architecture Outcomes

### 3.1 Two-stream model

TaskWeavn now has two different persisted streams:

- EventStream for audit/replay of Actions and Observations;
- MessageStream for user-visible interaction, confirmations, and responses.

Both can carry `task_id`, which lets future UI and Task views aggregate messages/events by session, agent, task, and time.

### 3.2 Autonomy and user confirmation

The Interaction Layer separates:

- pure decision: `AutonomyGate.check(...)`;
- side effects and waiting: `WaitCoordinator.handle_actionable(...)`;
- transport/persistence: `MessageBus` and `MessageStream`.

This supports both sync wait and async deferral.

### 3.3 Derived session status

`Session.status` is no longer treated as live truth except for `archived`.

Live status is derived from:

- open actionable messages -> `awaiting_user`;
- last event is AgentFinishObservation -> `finished`;
- otherwise -> `active`.

### 3.4 LLM risk assessment

`LLMRiskAssessor` and `CompositeAssessor` allow dynamic risk scoring while preserving the class-level baseline risk floor.

Failures are treated as safe fallback to baseline instead of crashing the loop.

---

## 4. Known Gaps

These are intentionally not solved by this release:

- full TaskBus execution lifecycle;
- Collaborator Agent;
- Task-first UI projection APIs;
- provider-level LLM retry;
- configurable logging;
- RAG and summarization;
- multi-agent shared workspace execution.

They are now tracked in the updated [Roadmap](../roadmap.md) and [Project Plan](../project/roadmap.md).

---

## 5. Follow-ups

Immediate follow-ups:

1. Implement LLM Provider abstraction, retry, DeepSeek thinking, and OpenRouter routing.
2. Implement configurable hierarchical logging.
3. Define Task domain model vs UI ViewModel boundary.
4. Implement Collaborator Agent and Task authoring tools.
5. Implement TaskPublisher and pipeline task loading.
