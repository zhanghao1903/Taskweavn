# ADR-0008: Authoring Domain And Execution TaskBus Boundary

> Status: accepted
> Date: 2026-05-14
> Related: [Authoring Domain](../architecture/authoring-domain.md), [Authoring Command Protocol](../architecture/authoring-command-protocol.md), [RawTask discussion](../discussion/2026-05-14-raw-task-authoring-domain.md), [Collaborator Agent plan](../plans/feature/collaborator-agent-task-authoring.md), [TaskBus](../architecture/bus.md)
> User Needs: [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md), [UN-101](../user_model/needs/UN-101-photo-curation-batch-screening.md), [UN-102](../user_model/needs/UN-102-courseware-html-generation.md), [UN-103](../user_model/needs/UN-103-car-purchase-decision-support.md)

---

## Context

TaskWeavn's core product workflow starts with natural language:

```text
User input
  -> Collaborator Agent
  -> Task Tree List
  -> user confirmation
  -> TaskBus execution
```

This exposed an architectural gap: some user inputs are not immediately plannable or executable.

Examples:

- information is missing;
- the request is partially feasible;
- the system lacks capability;
- the task needs user permission;
- the request is unsafe;
- the user wants discussion rather than execution.

If every user input becomes a TaskBus item, Execution TaskBus must support raw intent, draft trees, clarification asks, fixed routing to Collaborator, and non-executable lifecycles. That would overload a core execution primitive.

---

## Decision

Introduce a formal **Authoring Domain** before Execution TaskBus.

Authoring Domain owns:

- `RawTask`;
- `FeasibilityReport`;
- `RawTaskAsk`;
- `RawTaskAnswer`;
- `DraftTaskTree`;
- `DraftTaskNode`;
- `TaskPatch`;
- `CollaboratorProposal`.

Execution Domain owns:

- `PublishedTask`;
- `TaskClaim`;
- `TaskResult`;
- `TaskFailure`;
- `PipelineTask`;
- `ResultPackagingTask`.

The boundary rule is:

```text
Authoring objects do not enter Execution TaskBus.
Only published execution Tasks enter TaskBus.
```

The bridge is `TaskPublisher`:

```text
RawTask
  -> DraftTaskTree
  -> user confirmation
  -> TaskPublisher
  -> PublishedTask
  -> Execution TaskBus
```

Feasibility is modeled as a structured report, not a yes/no gate:

```text
ready
needs_clarification
needs_user_permission
partially_feasible
not_supported
unsafe
```

Authoring state mutation is command-first:

```text
Collaborator LLM
  -> AuthoringProposal
  -> AuthoringCommandBatch
  -> AuthoringCommandService
  -> RawTaskStore / DraftTaskStore / MessageStream / trace events
```

This keeps RawTask exploration and DraftTaskTree editing out of ordinary execution tools. Tool adapters may exist later for compatibility, but they must be thin wrappers over command handlers rather than independent mutation paths.

---

## Consequences

Positive:

- TaskBus remains focused on executable Tasks and execution state.
- Raw or ambiguous user input can still become a visible, replayable object.
- Clarification asks have a clear parent object.
- Collaborator Agent is less overloaded because feasibility and draft state have explicit contracts.
- UI can show RawTask Cards, feasibility state, asks, draft trees, and published tasks as related but distinct stages.
- Replay can reconstruct the path from natural language to published Task.

Trade-offs:

- The system gains a second domain and more object types.
- Plans and architecture docs must distinguish RawTask, DraftTask, and PublishedTask consistently.
- Future APIs need to expose authoring commands separately from execution TaskBus APIs.
- Collaborator implementation can change often, but command handlers and stores should remain stable.
- RawTask authoring uses lighter audit than published execution Tasks, while preserving command/message/version traceability.
- If future demand requires asynchronous authoring workers, we may need an AuthoringBus or a generic WorkBus. That is deferred until there is a concrete need.

Rejected alternatives:

| Alternative | Reason Rejected |
|---|---|
| Put RawTask into Execution TaskBus | Pollutes TaskBus with non-executable lifecycle and fixed collaborator routing. |
| Add a mandatory Feasibility Agent before Collaborator | Feasibility is contextual and should be part of authoring command-backed service logic; a fixed gate actor makes UX rigid. |
| Expose every authoring mutation as an LLM-visible tool | Expands tool count, increases call/failure surface, and gives ordinary Agents too much access to TaskWeavn internal state. |
| Let Collaborator keep all authoring state internally | Breaks stateless Agent principle and weakens replayability. |
| Treat RawTask only as a message | Loses a stable parent for asks, feasibility, draft generation, and replay. |

---

## Follow-up

- Update Collaborator Agent plan to include RawTask, feasibility, and Authoring Command Protocol.
- Update Task architecture docs to distinguish Authoring Task objects from Published execution Tasks.
- Update TaskBus docs to clarify it is the authority for published execution Tasks only.
- Consider RawTaskStore persistence shape during Collaborator implementation.
