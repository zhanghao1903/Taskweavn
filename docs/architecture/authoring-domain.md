# Authoring Domain Architecture

> Status: accepted baseline
> Last Updated: 2026-05-14
> Related Discussion: [RawTask、可行性判断与 Authoring Domain](../discussion/2026-05-14-raw-task-authoring-domain.md)
> Related ADR: [ADR-0008](../decisions/ADR-0008-authoring-domain-execution-boundary.md)
> Related Plans: [Collaborator Agent](../plans/feature/collaborator-agent-task-authoring.md), [Task model/UI separation](../plans/feature/task-domain-ui-model-separation.md)
> Related Protocol: [Authoring Command Protocol](authoring-command-protocol.md)
> User Needs: [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md), [UN-101](../user_model/needs/UN-101-photo-curation-batch-screening.md), [UN-102](../user_model/needs/UN-102-courseware-html-generation.md), [UN-103](../user_model/needs/UN-103-car-purchase-decision-support.md)

---

## 1. Purpose

Authoring Domain defines how user intent becomes executable Tasks.

TaskWeavn's product interaction starts with natural language, but natural language is not yet an executable Task. It may be ambiguous, unsupported, unsafe, missing permissions, or only partially feasible. If the system forces every user input directly into TaskBus, TaskBus must handle raw intent, clarification, draft state, fixed routing to Collaborator, and non-executable lifecycles.

This document introduces a formal boundary:

```text
UserMessage
  -> RawTask
  -> FeasibilityReport / RawTaskAsk
  -> DraftTaskTree
  -> user confirmation
  -> TaskPublisher
  -> PublishedTask
  -> Execution TaskBus
```

The key rule is:

```text
Authoring objects do not enter Execution TaskBus.
Only published execution Tasks enter TaskBus.
```

### 1.1 User-Need Traceability

This boundary is not only a technical cleanup. It exists because users need to judge whether a task is suitable before committing to execution.

| Need | How Authoring Domain Responds |
|---|---|
| [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md) | RawTask and FeasibilityReport expose "can we do this, what is missing, what is risky" before TaskBus execution. |
| [UN-101](../user_model/needs/UN-101-photo-curation-batch-screening.md) | Batch screening goals can first become editable RawTask/DraftTaskTree flows with review checkpoints before execution. |
| [UN-102](../user_model/needs/UN-102-courseware-html-generation.md) | Courseware generation can collect teaching constraints before drafting executable content tasks. |
| [UN-103](../user_model/needs/UN-103-car-purchase-decision-support.md) | High-risk information tasks can stay in clarification/evaluation mode when constraints or sources are insufficient. |

---

## 2. Two Domains

TaskWeavn now has two Task-related domains.

| Domain | Responsibility | Core Objects | Bus Boundary |
|---|---|---|---|
| Authoring Domain | Turn fuzzy user intent into a publishable Task Tree. | `RawTask`, `FeasibilityReport`, `RawTaskAsk`, `DraftTaskTree`, `DraftTaskNode`, `TaskPatch`, `CollaboratorProposal` | Does not publish to Execution TaskBus directly. |
| Execution Domain | Execute confirmed Tasks and produce results. | `PublishedTask`, `TaskClaim`, `TaskResult`, `TaskFailure`, `PipelineTask`, `ResultPackagingTask` | TaskBus is state authority. |

The domains are connected by `TaskPublisher`.

```text
Authoring Domain
  RawTask + DraftTaskTree
        |
        | user confirms / publish command
        v
  TaskPublisher
        |
        | validate + normalize + publish
        v
Execution Domain
  PublishedTask -> TaskBus -> Agent execution
```

---

## 3. Core Objects

### 3.1 UserMessage

The original user input in the Session Message Stream.

It remains a message, not a Task. A user message may create one RawTask, multiple RawTasks, or no RawTask if it is pure conversation.

### 3.2 RawTask

RawTask is the first durable object produced from task-like user intent.

It captures:

- original user input;
- inferred intent summary;
- assumptions;
- missing information;
- feasibility status;
- clarification asks and answers;
- readiness for draft Task Tree generation.

Example shape:

```python
class RawTask(BaseModel):
    id: str
    session_id: str
    source_message_id: str
    user_input: str
    status: Literal[
        "created",
        "assessing",
        "awaiting_user",
        "ready_to_plan",
        "converted",
        "rejected",
        "cancelled",
    ]
    intent_summary: str | None = None
    feasibility: FeasibilityReport | None = None
    missing_inputs: tuple[Question, ...] = ()
    constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
```

RawTask is not executable. It has no execution `required_capability`, cannot be claimed by execution Agents, and does not use `pending/running/done/failed`.

### 3.3 FeasibilityReport

FeasibilityReport is a structured answer to:

```text
What can we do?
What is missing?
What is risky?
What should happen next?
```

It is not a yes/no verdict.

```python
class FeasibilityReport(BaseModel):
    status: Literal[
        "ready",
        "needs_clarification",
        "needs_user_permission",
        "partially_feasible",
        "not_supported",
        "unsafe",
    ]
    confidence: float
    reasons: tuple[str, ...] = ()
    missing_inputs: tuple[Question, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    suggested_next_action: Literal[
        "generate_task_tree",
        "ask_user",
        "offer_alternatives",
        "decline",
    ]
```

### 3.4 RawTaskAsk And RawTaskAnswer

ASK actions in authoring attach to RawTask, not only to Session.

```python
class RawTaskAsk(BaseModel):
    id: str
    raw_task_id: str
    question: str
    options: tuple[AnswerOption, ...] = ()
    required: bool
    reason: str
```

```python
class RawTaskAnswer(BaseModel):
    id: str
    raw_task_id: str
    ask_id: str
    value: str
    source_message_id: str
```

In the first implementation, RawTaskAsk should also be represented as an actionable `AgentMessage` so the existing MessageStream and UI confirmation machinery can render and resolve it.

### 3.5 DraftTaskTree And DraftTaskNode

DraftTaskTree is the editable plan produced from a `ready_to_plan` RawTask.

Draft nodes may have titles, intents, constraints, options, and UI-visible explanations. They are still authoring facts, not execution Tasks.

DraftTaskTree becomes executable only after:

1. deterministic validation passes;
2. the user confirms publication;
3. `TaskPublisher` converts it into PublishedTasks.

### 3.6 PublishedTask

PublishedTask is the Execution Domain Task.

It is the object TaskBus can publish, claim, complete, fail, replay, and summarize. It is intentionally smaller than authoring objects because it only needs execution truth.

---

## 4. Lifecycle

### 4.1 RawTask Lifecycle

```text
created
  -> assessing
  -> awaiting_user
  -> assessing
  -> ready_to_plan
  -> converted
```

Alternative terminal paths:

```text
created/assessing/awaiting_user
  -> rejected
  -> cancelled
```

Rules:

- `created`: user input has been captured.
- `assessing`: Collaborator or assessor is evaluating feasibility.
- `awaiting_user`: one or more RawTaskAsk objects need response.
- `ready_to_plan`: enough information exists to generate DraftTaskTree.
- `converted`: a DraftTaskTree has been generated from this RawTask.
- `rejected`: task is unsafe, unsupported, or cannot be meaningfully planned.
- `cancelled`: user or system cancelled authoring.

### 4.2 DraftTaskTree Lifecycle

```text
draft
  -> validating
  -> ready_to_publish
  -> published
```

Alternative paths:

```text
draft -> cancelled
validating -> draft
ready_to_publish -> draft
```

Rules:

- Draft trees can be edited until publication.
- Publication is irreversible for the produced PublishedTasks.
- After publication, follow-up changes create new authoring facts or new Tasks, not mutation of already-published execution Tasks.

### 4.3 Execution Task Lifecycle

Execution Task lifecycle stays owned by TaskBus:

```text
pending -> running -> done
                  -> failed
```

This lifecycle must not absorb authoring-specific states such as `awaiting_user`, `ready_to_plan`, or `ready_to_publish`.

---

## 5. Message, Event, And Store Model

### 5.1 MessageStream

Authoring uses the single Session Message Stream for user-visible communication.

Recommended context keys:

| Key | Meaning |
|---|---|
| `domain` | `authoring` or `execution`. |
| `raw_task_id` | Related RawTask when message is about initial intent or feasibility. |
| `draft_tree_id` | Related DraftTaskTree. |
| `task_ref_kind` | `raw`, `draft`, or `published`. |
| `mode` | `clarification`, `feasibility`, `drafting`, `validation`, `publish`. |

This keeps UI streams unified while preserving queryable authoring context.

### 5.2 EventStream

Authoring events should be append-only and replayable.

Candidate events:

- `RawTaskCreated`
- `RawTaskFeasibilityAssessed`
- `RawTaskAskCreated`
- `RawTaskAnswered`
- `RawTaskReadyToPlan`
- `DraftTaskTreeCreated`
- `DraftTaskNodePatched`
- `DraftTaskTreeValidated`
- `DraftTaskTreePublishRequested`
- `DraftTaskTreePublished`

These are authoring/audit events, not TaskBus state events.

### 5.3 Audit Strength

Authoring audit is intentionally lighter than execution audit.

RawTask is an exploration object. Users may revise intent, answer clarifying questions, abandon paths, or try multiple formulations. The system should preserve traceability without making exploratory language feel like a formal execution commitment.

Recommended audit posture:

| Layer | Audit Posture | Reason |
|---|---|---|
| RawTask | lightweight traceability | exploratory, often revised, not executable |
| DraftTaskTree | medium traceability | user-visible plan that may become execution tasks |
| PublishedTask | strong audit | executable, affects workspace and user outcomes |

For RawTask, prefer command summaries, causation message ids, versions, and compact snapshots. Avoid heavyweight immutable events for every minor text or assumption change.

### 5.4 Stores

First-class store boundaries:

| Store | Responsibility |
|---|---|
| `RawTaskStore` | RawTask, feasibility, asks, answers, version history. |
| `DraftTaskStore` | DraftTaskTree, DraftTaskNode, patches, publish mapping. |
| `TaskStore` | Published execution Tasks and state views. |

The first implementation can be in-memory for service tests, but the architecture should assume these objects must be durable and replayable.

---

## 6. Authoring Command Protocol

Authoring Domain state changes should go through [Authoring Command Protocol](authoring-command-protocol.md), not through many LLM-visible tools.

The stable rule:

```text
LLM produces proposals.
AuthoringCommandService validates and commits commands.
Stores/messages/events are mutated by command handlers.
```

This is especially important because authoring happens in the interaction path. Repeated LLM tool calls increase latency and error rate. Coarse object-scoped commands reduce failure points while keeping code-side validation strong.

Primary command groups:

| Command | Object Scope | Purpose |
|---|---|---|
| `MutateRawTaskCommand` | RawTask | Create/update RawTask, feasibility, asks, answers, assumptions, status. |
| `MutateDraftTaskTreeCommand` | DraftTaskTree | Create tree, patch nodes, reorder, attach options, mark accepted. |
| `PublishDraftTaskTreeCommand` | DraftTaskTree -> PublishedTask | Validate and cross into Execution Domain. |
| `AuthoringCommandBatch` | One object scope by default | Submit multiple operations with one validation/transaction boundary. |

Natural language authoring uses this protocol after LLM proposal parsing. Strongly typed Task Tree input can skip RawTask exploration and go directly to validate/publish.

---

## 7. Collaborator Responsibility

The Collaborator Agent remains the primary authoring assistant, but Authoring Domain prevents it from becoming an overloaded hidden actor.

Collaborator should coordinate:

- RawTask creation from user input;
- feasibility assessment through command-backed service logic;
- clarification questions;
- DraftTaskTree generation;
- selected-node refinement;
- validation summaries;
- publish requests.

Collaborator should not:

- write workspace files;
- run shell commands;
- bypass TaskPublisher;
- publish RawTask or DraftTaskTree into Execution TaskBus;
- keep hidden long-lived state outside stores/messages/events.

---

## 8. TaskBus Boundary

TaskBus receives only executable PublishedTasks.

Not allowed:

```text
TaskBus.publish(RawTask)
TaskBus.publish(DraftTaskTree)
TaskBus.publish(RawTaskAsk)
TaskBus.publish(CollaboratorProposal)
```

Allowed:

```text
TaskPublisher.publish_draft_tree(...)
  -> validate draft tree
  -> convert draft nodes to PublishedTasks
  -> TaskBus.publish(PublishedTask)
```

This keeps TaskBus clean:

- no fixed routing to Collaborator;
- no authoring lifecycle inside execution state machine;
- no non-executable objects in claim/complete/fail APIs;
- no accidental execution Agent claim of authoring work.

---

## 9. Routing And Future AuthoringBus

The current decision does not require an AuthoringBus.

First implementation can use:

- `AuthoringCommandService`;
- RawTaskStore and DraftTaskStore;
- MessageStream actionables;
- EventStream authoring events.

An AuthoringBus can be introduced later only if there are multiple independent authoring workers that need asynchronous routing. Until then, adding a second bus is premature.

If an AuthoringBus is introduced, it must be separate from Execution TaskBus or explicitly modeled as a future generic WorkBus with domain-specific item kinds.

---

## 10. Complexity Rule

Authoring Domain adds a concept. It is accepted because it prevents pollution of a more central concept.

Use this rule for future growth:

> 复杂度不是敌人，不受控的复杂度才是敌人。

Add a new layer only when it:

1. supports a clear user scenario;
2. avoids contaminating a core object with unrelated lifecycle states;
3. splits context so LLM and UI attention remain manageable;
4. can be explained in UI and replay.

RawTask and Authoring Domain pass this test because they make ambiguous, infeasible, and clarification-heavy input visible without damaging Execution TaskBus.

---

## 11. Open Questions

These are intentionally not locked in the first baseline:

1. Should RawTaskStore be a dedicated table or derived from messages/events first?
2. Should RawTask traceability use selected command events plus snapshots, or full append-only command events?
3. Should RawTaskAsk have a domain table, or can MessageStream actionable plus event facts be sufficient?
4. Should RawTask Card and DraftTaskNode Card share a UI ViewModel base?
5. Should a future generic WorkBus unify Authoring and Execution, or would that reintroduce the same pollution under a new name?

---

## 12. Architecture Summary

The stable mental model:

```text
User speaks in natural language.
Authoring Domain turns intent into a validated draft.
TaskPublisher converts confirmed draft into execution Tasks.
Execution TaskBus runs only executable Tasks.
```

This keeps the user interaction rich and the execution core small. That trade is intentional.
