# Authoring Command Protocol

> Status: design baseline / high-change area
> Last Updated: 2026-05-14
> Related Architecture: [Authoring Domain](authoring-domain.md), [Collaborator Agent](collaborator-agent-task-authoring.md), [Tool Capability Layer](tool-capability-layer.md), [Workspace Communication Protocol](workspace-communication-protocol.md)
> Related ADR: [ADR-0008](../decisions/ADR-0008-authoring-domain-execution-boundary.md)
> User Needs: [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md), [UN-101](../user_model/needs/UN-101-photo-curation-batch-screening.md), [UN-102](../user_model/needs/UN-102-courseware-html-generation.md), [UN-103](../user_model/needs/UN-103-car-purchase-decision-support.md)

---

## 1. Purpose

Authoring Domain changes TaskWeavn's own state: RawTasks, feasibility reports, clarification asks, DraftTaskTrees, publish mappings, messages, and replay facts.

Those mutations should not primarily be modeled as LLM tool calls.

The better boundary is:

```text
Workspace / external world changes -> Workspace Requests / Tool adapters
TaskWeavn system-state changes      -> Authoring Commands
```

LLM calls should generate proposals. Code should validate proposals, turn them into commands, and persist state through strongly typed command handlers.

This reduces:

- LLM tool-call count;
- failure points inside long authoring turns;
- accidental system-state mutation by ordinary Agents;
- schema drift across many small tools;
- audit noise for exploratory RawTask work.

---

## 2. Motivation And Concern

RawTask authoring is exploratory. Users may type rough natural language, revise intent, answer clarifying questions, reject directions, and try again.

This is different from published execution tasks.

| Area | RawTask / Draft Authoring | Published Task Execution |
|---|---|---|
| User mental state | exploring | committing |
| Audit strength | lighter | strong |
| Required guarantee | traceable and recoverable | validated, auditable, executable |
| Error tolerance | should avoid interrupting flow | should fail safely |
| LLM calls | minimize repeated calls | acceptable when tied to execution |
| State mutation | command protocol | TaskBus / runtime protocol |

The authoring layer should be traceable, but not ceremonially heavy. A user should not feel punished for thinking in natural language.

---

## 3. Core Principle

```text
LLM produces proposals.
AuthoringCommandService validates and persists commands.
Stores and messages are mutated only by command handlers.
```

Bad long-term shape:

```text
LLM -> CreateRawTaskTool
LLM -> AssessRawTaskFeasibilityTool
LLM -> AskRawTaskQuestionTool
LLM -> GenerateDraftTaskTreeTool
LLM -> UpdateDraftTaskNodeTool
```

Preferred shape:

```text
LLM -> AuthoringProposal / AuthoringCommandBatch draft
Code -> validate + normalize
Code -> AuthoringCommandService.submit(batch)
Code -> write stores/messages/events
```

---

## 4. Command Granularity

Commands should be grouped by object, not by tiny action.

### 4.1 RawTask Command

One command can mutate several RawTask-related fields atomically.

```python
class MutateRawTaskCommand(BaseModel):
    command_id: str
    session_id: str
    raw_task_id: str | None = None
    actor: ActorRef
    causation_message_id: str | None = None
    expected_version: int | None = None
    idempotency_key: str | None = None

    operations: tuple[RawTaskOperation, ...]
```

Example operations:

```python
class RawTaskOperation(BaseModel):
    op: Literal[
        "create",
        "set_intent_summary",
        "record_feasibility",
        "add_clarification_ask",
        "apply_answer",
        "update_constraints",
        "update_assumptions",
        "set_status",
    ]
    payload: dict[str, object]
```

This allows one LLM turn to create RawTask, record feasibility, add an ask, and emit a user-visible message through one validated command.

### 4.2 DraftTaskTree Command

Draft tree edits are object-scoped and can batch multiple node operations.

```python
class MutateDraftTaskTreeCommand(BaseModel):
    command_id: str
    session_id: str
    draft_tree_id: str | None = None
    raw_task_id: str | None = None
    actor: ActorRef
    causation_message_id: str | None = None
    expected_version: int | None = None
    idempotency_key: str | None = None

    operations: tuple[DraftTaskTreeOperation, ...]
```

Example operations:

```python
class DraftTaskTreeOperation(BaseModel):
    op: Literal[
        "create_tree",
        "patch_node",
        "add_node",
        "remove_node",
        "reorder_siblings",
        "attach_options",
        "mark_ready",
        "mark_accepted",
    ]
    payload: dict[str, object]
```

### 4.3 Publish Command

Publishing stays separate because it crosses from Authoring Domain into Execution Domain.

```python
class PublishDraftTaskTreeCommand(BaseModel):
    command_id: str
    session_id: str
    draft_tree_id: str
    actor: ActorRef
    expected_version: int | None = None
    idempotency_key: str
    publish_options: PublishOptions = PublishOptions()
```

Publish command handlers must run stronger validation than RawTask commands.

---

## 5. Batch Submission

Authoring should support batch command submission.

```python
class AuthoringCommandBatch(BaseModel):
    batch_id: str
    session_id: str
    actor: ActorRef
    causation_message_id: str | None = None
    idempotency_key: str | None = None
    mode: Literal["all_or_nothing", "best_effort"] = "all_or_nothing"
    commands: tuple[AuthoringCommand, ...]
```

First-version rules:

1. Default to `all_or_nothing`.
2. Prefer one object scope per batch: one RawTask or one DraftTaskTree.
3. Cross-object batches are allowed only for safe adjacent transitions, such as RawTask `ready_to_plan` plus DraftTaskTree creation.
4. `best_effort` is reserved for UI convenience updates, not publish.
5. Publish batches are always transactional.

This reduces LLM retries and round trips while keeping code-side validation strong.

---

## 6. Validation Model

Command validation happens in code, not by trusting the LLM.

Validation layers:

| Layer | Responsibility |
|---|---|
| Schema validation | command shape, required ids, operation payload type. |
| Version validation | `expected_version` prevents overwriting stale draft state. |
| Policy validation | actor can mutate this object and command type. |
| Domain validation | RawTask/DraftTask lifecycle transitions are legal. |
| Capability validation | Draft nodes reference registered capabilities. |
| Publish validation | ready state, tree shape, capability coverage, topology gate. |

The LLM can propose invalid changes. That is expected. The handler returns structured errors so a following turn can repair them.

---

## 7. Audit And Traceability

Authoring audit should be lighter than execution audit, but not absent.

### 7.1 RawTask Audit

RawTask is exploration. Recommended traceability:

- command id;
- actor;
- causation message id;
- before/after version;
- changed fields summary;
- feasibility status changes;
- asks and answers;
- optional compact snapshot.

Avoid:

- heavyweight event for every minor text tweak;
- strong irreversible audit semantics for exploratory changes;
- blocking user flow for non-critical trace writes.

### 7.2 DraftTaskTree Audit

DraftTaskTree needs stronger traceability than RawTask because it can become PublishedTasks.

Record:

- command id and batch id;
- node ids touched;
- operation summaries;
- validation result;
- publish mapping when published.

### 7.3 PublishedTask Audit

PublishedTask remains strong-audit territory:

- TaskBus events;
- status transitions;
- Agent assignment;
- runtime observations;
- file changes;
- publish mapping from draft.

---

## 8. Error Handling

Authoring failures directly affect interaction quality because LLM response time is high and repeated calls are expensive.

Therefore:

1. Prefer fewer, coarser commands.
2. Return structured partial diagnostics.
3. Do not require a new LLM call for purely mechanical fixups.
4. Keep failed commands replayable from request + validation errors.
5. If a batch fails before persistence, preserve a non-authoritative diagnostic message for UI.

Command result shape:

```python
class AuthoringMessageEffect(BaseModel):
    message_type: Literal["informational", "actionable"]
    content: str
    task_id: str | None = None
    context: dict[str, object] = {}
    action_options: tuple[str, ...] = ()
    requires_response: bool = False


class AuthoringCommandResult(BaseModel):
    ok: bool
    batch_id: str | None = None
    applied_command_ids: tuple[str, ...] = ()
    object_refs: tuple[TaskRef, ...] = ()
    message_effects: tuple[AuthoringMessageEffect, ...] = ()
    emitted_message_ids: tuple[str, ...] = ()
    errors: tuple[CommandError, ...] = ()
    warnings: tuple[CommandWarning, ...] = ()
```

`AuthoringMessageEffect` is a requested side effect, not a pre-built persisted message. The command service should turn it into `AgentMessage` only after command validation succeeds. This keeps failed command proposals from accidentally writing authoritative user-visible state.

---

## 9. Strongly Typed Task Workflow

Natural language authoring is not the only entry point.

TaskWeavn should also support a strong typed workflow:

```text
Structured Task Tree input
  -> validate
  -> preview
  -> publish
```

This path is useful for:

- advanced users;
- APIs;
- pipeline files;
- generated Task Trees from external systems;
- regression tests.

It should skip RawTask exploration when the user already provides a structured Task Tree. Validation and publish audit are still strong.

---

## 10. Relationship To Tools

System-state authoring operations should not be ordinary LLM-visible tools by default.

Tool usage remains appropriate for:

- workspace mutation;
- external data retrieval;
- sandbox execution;
- domain-specific execution actions.

Long term, workspace mutation should be mediated by [Workspace Communication Protocol](workspace-communication-protocol.md). In that model, current Tools become adapters over `WorkspaceRequest` operations.

Authoring commands are appropriate for:

- RawTask mutation;
- DraftTaskTree mutation;
- clarification ask/answer persistence;
- publish request;
- authoring messages and replay facts.

If command handlers are exposed as tools for compatibility, treat them as thin adapters over `AuthoringCommandService`, not as the source of truth.

---

## 11. Collaborator Change Volatility

Collaborator will likely change frequently.

Design implication:

- keep Collaborator prompts replaceable;
- keep proposal parsing isolated;
- keep command handlers stable;
- keep stores and command protocol more stable than the prompt;
- let new internal specialists appear behind service protocols;
- avoid coupling UI directly to LLM output format.

This allows product experimentation without repeatedly rewriting persistence and state transition code.

---

## 12. Open Questions

1. Should `AuthoringCommandBatch` support cross-RawTask batches in v1? Current recommendation: no.
2. Should RawTask store every command event or compact snapshots plus selected events? Current recommendation: selected events + compact snapshots.
3. Should `best_effort` be allowed before UI exists? Current recommendation: no, start with `all_or_nothing`.
4. Should feasibility be one operation inside RawTask command or its own command? Current recommendation: operation inside `MutateRawTaskCommand`.
5. Should command handlers append user-visible messages directly? Current recommendation: yes, but only through structured message effects returned by the handler.

---

## 13. Summary

The stable rule:

```text
Tools change the outside world.
Commands change TaskWeavn state.
LLM proposes; code validates and commits.
RawTask authoring is exploratory and lightly audited.
PublishedTask execution is strongly validated and audited.
```

This gives Collaborator room to evolve quickly without making system state fragile.
