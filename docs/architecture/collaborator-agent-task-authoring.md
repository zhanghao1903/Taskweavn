# Collaborator Agent And Task Authoring

> Status: draft
> Last Updated: 2026-05-14
> Work Stream: Phase 3C — Task Authoring Foundation
> Related Plan: [Collaborator Agent](../plans/feature/collaborator-agent-task-authoring.md)
> Depends On: [Task Domain/UI ViewModel Separation](task-domain-ui-model-separation.md), [Authoring Domain](authoring-domain.md)
> Related Docs: [Agent](agent.md), [Task](task.md), [TaskBus](bus.md), [UI API Interfaces](../plans/ui/ui-api-interfaces.md)

---

## 1. Purpose

The Collaborator Agent is the system role that turns user language into editable Task Trees.

It is not a normal execution Agent that writes files or runs commands. It is the user's Task authoring partner:

```text
user intent
  -> RawTask
  -> feasibility / clarification / enrichment
  -> draft Task Tree
  -> selected Task Node refinement
  -> validation
  -> user-confirmed publish request
```

This design defines how that role should fit into the current TaskWeavn server-core architecture.

The important constraint is that the Collaborator must not become a hidden stateful actor. It follows the same mental model as other Agents:

```text
Collaborator invocation = function(input, session/task context) -> draft facts/messages/commands
```

All durable state lives in `DraftTaskStore`, `MessageStream`, publish mappings, and future TaskBus/EventStream facts.

---

## 2. Current Baseline

The previous Phase 3C package already introduced the boundary objects this feature should reuse:

| Area | Existing Contract |
|---|---|
| Authoring boundary | `Authoring Domain` separates RawTask/DraftTaskTree from Execution TaskBus |
| Draft facts | `DraftTaskNode`, `DraftTaskTree`, `DraftToPublishedMapping` |
| Published facts | `TaskDomain` |
| References | `TaskRef(kind="draft"|"published", id=...)` |
| Store protocols | `DraftTaskStore`, `TaskStore` |
| UI projection | `TaskProjectionService`, `TaskTreeView`, `TaskCardView`, `TaskDetailView` |
| Commands | `TaskCommandService`, `TaskPublisher`, `CommandResult` |
| Replay | `TaskInteractionTimelineService` |
| User-visible messages | `MessageStream`, `MessageBus`, `AgentMessage` |

Therefore this feature should not redefine Task models. It should add the missing authoring layer:

```text
CollaboratorAuthoringService
  + RawTask creation
  + feasibility assessment
  + clarification asks
  + prompt/context builder
  + authoring tools
  + validation
  + message publishing
  + task publisher boundary
```

---

## 3. Design Goals

1. Create `RawTask` from task-like session-level natural language.
2. Assess feasibility before forcing DraftTaskTree generation.
3. Ask RawTask-scoped clarification questions when information is missing.
4. Generate a `DraftTaskTree` from a `ready_to_plan` RawTask.
5. Refine a selected `DraftTaskNode` from task-scoped natural language or option selection.
6. Produce user-visible collaborator messages and confirmation/options through the single `MessageStream`.
7. Validate draft trees before publish.
8. Publish only through an injected `TaskPublisher` boundary.
9. Preserve replayability for raw create/ask/answer, draft create/update/validate, and publish actions.
10. Keep the Collaborator Agent stateless across invocations.
11. Keep the implementation testable with mock LLM responses and in-memory stores.

---

## 4. Non-goals

- Do not build the frontend UI.
- Do not implement full TaskBus v2.
- Do not let the Collaborator Agent write workspace files or run shell commands.
- Do not introduce DAG Task topology.
- Do not make Collaborator a long-lived actor with internal memory.
- Do not require real LLM calls in unit tests.
- Do not implement cross-user collaborative editing.
- Do not put RawTask, clarification asks, or DraftTaskTree into Execution TaskBus.
- Do not require a separate Feasibility Agent in the first version; feasibility can be a Collaborator tool/service.

---

## 5. Core Decision

### 5.1 Collaborator Is A System Agent Template, Not A Persistent Actor

The system should register a built-in template:

```python
CollaboratorAgentTemplate(
    template_id="system.collaborator",
    capability="task_authoring",
    display_name="Collaborator",
    tools=(...task authoring tools...),
    system_prompt=COLLABORATOR_SYSTEM_PROMPT,
)
```

But runtime invocation should be service-shaped:

```text
CollaboratorAuthoringService.generate_task_tree(...)
CollaboratorAuthoringService.refine_task_node(...)
CollaboratorAuthoringService.propose_task_options(...)
CollaboratorAuthoringService.validate_task_tree(...)
CollaboratorAuthoringService.publish_task_tree(...)
```

This keeps the existing Agent principle:

```text
Template is stable identity.
Invocation is one function call.
State is external and replayable.
```

### 5.2 Authoring Tools Are Domain Tools

Task authoring tools operate on:

- `DraftTaskStore`;
- `MessageBus` / `MessageStream`;
- `TaskPublisher`;
- capability registry / validation policy.

They do not operate on:

- workspace files;
- shell commands;
- sandbox;
- arbitrary runtime tools.

### 5.3 Publish Is A Boundary, Not Direct TaskBus Access

The Collaborator should not call TaskBus internals directly. It should call `TaskPublisher.publish_draft_tree(...)`.

That lets the next roadmap package implement one safe publish path for:

- Collaborator;
- user custom Task Trees;
- pipeline loader;
- scheduled publishers;
- API publishers.

---

## 6. Main Components

### 6.1 CollaboratorAuthoringService

The service is the primary server-side entrypoint behind UI/API commands.

```python
class CollaboratorAuthoringService(Protocol):
    def create_raw_task(
        self,
        session_id: str,
        source_message_id: str,
        user_input: str,
    ) -> AuthoringCommandResult: ...

    def assess_raw_task(
        self,
        session_id: str,
        raw_task_id: str,
    ) -> AuthoringCommandResult: ...

    def answer_raw_task_ask(
        self,
        session_id: str,
        raw_task_id: str,
        ask_id: str,
        answer: str,
    ) -> AuthoringCommandResult: ...

    def generate_task_tree(
        self,
        session_id: str,
        raw_task_id: str,
        *,
        context: AuthoringContext | None = None,
    ) -> AuthoringCommandResult: ...

    def refine_task_node(
        self,
        session_id: str,
        task_ref: TaskRef,
        instruction: str,
        *,
        expected_version: int | None = None,
    ) -> AuthoringCommandResult: ...

    def propose_task_options(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        question: str | None = None,
    ) -> TaskNodeOptionSet: ...

    def validate_task_tree(
        self,
        session_id: str,
        draft_tree_id: str,
    ) -> DraftTaskTreeValidation: ...

    def publish_task_tree(
        self,
        session_id: str,
        draft_tree_id: str,
    ) -> CommandResult: ...
```

The default implementation coordinates LLM calls and tools. Individual tools remain independently testable.

### 6.2 AuthoringContextBuilder

Builds prompt context from server facts.

Inputs:

- session id;
- optional selected `TaskRef`;
- current draft trees;
- selected node, ancestors, children;
- recent session messages;
- recent task-scoped messages;
- registered capabilities;
- optional workspace summary;
- current constraints from configuration.

Output:

```python
class AuthoringContext(BaseModel):
    session_id: str
    selected_task_ref: TaskRef | None = None
    mode: Literal["session", "task"]
    draft_trees: tuple[DraftTaskTree, ...] = ()
    selected_node: DraftTaskNode | None = None
    ancestors: tuple[DraftTaskNode, ...] = ()
    children: tuple[DraftTaskNode, ...] = ()
    recent_messages: tuple[AgentMessage, ...] = ()
    capabilities: tuple[str, ...] = ()
    constraints: dict[str, object] = {}
```

The context builder is intentionally read-only.

### 6.3 CapabilityCatalog

The Collaborator must not hallucinate `required_capability`.

First version can be a small protocol:

```python
class CapabilityCatalog(Protocol):
    def all(self) -> tuple[str, ...]: ...
    def contains(self, capability: str) -> bool: ...
```

Early implementation can use a static in-memory catalog. Later this should read Agent templates.

### 6.4 DraftTaskTreeValidator

Validation should be deterministic and not LLM-based.

Checks:

- tree exists;
- root nodes have no parent;
- node ids are unique;
- parent ids resolve inside the tree;
- `order_index` is unique among siblings;
- required capability exists;
- intent/title/capability are non-empty;
- status is publishable (`draft` or `accepted`, depending on publish policy);
- no cancelled node is published;
- max depth / max node count constraints are respected.

Result:

```python
class DraftTaskTreeValidation(BaseModel):
    valid: bool
    draft_tree_id: str
    errors: tuple[DraftTaskValidationIssue, ...] = ()
    warnings: tuple[DraftTaskValidationIssue, ...] = ()
```

### 6.5 Task Authoring Tools

Tools are the low-level executable boundary. They can be used by `AgentLoop` later, but the first implementation can call them from `CollaboratorAuthoringService`.

Minimum tools:

| Tool | Primary Store/Boundary | Purpose |
|---|---|---|
| `CreateRawTaskTool` | `RawTaskStore` | Persist user intent as RawTask. |
| `AssessRawTaskFeasibilityTool` | feasibility assessor | Produce structured feasibility and next action. |
| `AskRawTaskQuestionTool` | `MessageBus` / `RawTaskStore` | Publish RawTask-scoped clarification asks and record answers. |
| `GenerateDraftTaskTreeTool` | `DraftTaskStore` | Persist generated root nodes from a ready RawTask as a draft tree. |
| `ReadDraftTaskTreeTool` | `DraftTaskStore` | Read tree or selected node context. |
| `UpdateDraftTaskNodeTool` | `DraftTaskStore` | Apply `TaskNodePatch` with version guard. |
| `ValidateDraftTaskTreeTool` | validator | Return deterministic validation result. |
| `AppendTaskAuthoringMessageTool` | `MessageBus` | Publish collaborator/user-visible authoring messages. |
| `PublishDraftTasksTool` | `TaskPublisher` | Publish validated draft tree through publisher boundary. |

Deferred:

- `ProposeTaskNodeOptionsTool` can be implemented after the basic refine flow works. It is useful for UI, but not required for the first authoring service.

---

## 7. LLM Output Contracts

The LLM should produce structured authoring proposals. Store writes should be performed by tools/services after validation.

### 7.1 Generate Tree Proposal

```python
class DraftTaskTreeProposal(BaseModel):
    roots: tuple[DraftTaskNodeProposal, ...]
    assistant_message: str
```

```python
class DraftTaskNodeProposal(BaseModel):
    title: str
    intent: str
    required_capability: str
    constraints: tuple[str, ...] = ()
    rationale: str | None = None
    children: tuple[DraftTaskNodeProposal, ...] = ()
```

The proposal does not include final ids. The tool assigns ids and tree metadata.

### 7.2 Patch Proposal

```python
class DraftTaskPatchProposal(BaseModel):
    patch: TaskNodePatch
    assistant_message: str
    affected_scope: Literal["selected_node", "subtree"]
```

### 7.3 Option Proposal

```python
class TaskNodeOption(BaseModel):
    option_id: str
    label: str
    description: str | None = None
    patch: TaskNodePatch | None = None
    message: str | None = None
```

Options should be written as actionable `AgentMessage` objects when user confirmation is needed.

---

## 8. Workflows

### 8.1 Session-Level RawTask Creation And Feasibility

```text
appendSessionMessage(user prompt)
  -> CollaboratorAuthoringService.create_raw_task
  -> CollaboratorAuthoringService.assess_raw_task
  -> if missing info: AskRawTaskQuestionTool publishes actionable message
  -> if ready: RawTask.status = ready_to_plan
```

Properties:

- creates RawTask facts only;
- does not publish to TaskBus;
- does not force a DraftTaskTree when feasibility is unclear;
- every clarification ask is attached to `raw_task_id`;
- user answers patch the RawTask and can trigger reassessment.

### 8.2 RawTask To Draft Task Tree

```text
generateTaskTree(raw_task_id)
  -> require RawTask.status == ready_to_plan
  -> ContextBuilder builds session context
  -> LLM returns DraftTaskTreeProposal
  -> Validate proposal shape and capabilities
  -> GenerateDraftTaskTreeTool persists DraftTaskTree
  -> AppendTaskAuthoringMessageTool publishes assistant summary
  -> UI refreshes TaskTreeView
```

Properties:

- creates draft facts only;
- does not publish to TaskBus;
- every generated node has capability and intent;
- returned command result references the root draft task refs.

### 8.3 Selected Task Node Refinement

```text
appendTaskMessage(selected draft node, instruction)
  -> CollaboratorAuthoringService.refine_task_node
  -> ContextBuilder builds selected-node context
  -> LLM returns DraftTaskPatchProposal
  -> Validate patch against selected node/version
  -> UpdateDraftTaskNodeTool applies patch
  -> AppendTaskAuthoringMessageTool publishes assistant response
  -> UI refreshes selected card/detail/timeline
```

Properties:

- defaults to local selected-node scope;
- does not rebuild the whole tree unless the command explicitly requests subtree edits;
- uses `expected_version` to avoid overwriting newer edits.

### 8.4 Option Proposal And Selection

```text
User selects Task Node
  -> propose_task_options
  -> actionable message with options
  -> user selects option
  -> resolveConfirmation writes response
  -> refine_task_node applies mapped patch
```

First implementation may skip option proposal as a separate tool and use direct natural-language refinement. The data model should keep space for it because UI cards need options.

### 8.5 Validation

```text
validate_task_tree
  -> deterministic validator
  -> validation result message
  -> UI displays blocking errors or warnings
```

Validation failures do not mutate the tree unless the user asks Collaborator to fix them.

### 8.6 Publish

```text
publish_task_tree
  -> validate_task_tree
  -> if invalid: reject with validation message
  -> PublishDraftTasksTool calls TaskPublisher.publish_draft_tree
  -> DraftTaskStore.mark_published with mappings
  -> MessageStream assistant publish summary
```

The first authoring package can publish through the `TaskPublisher` protocol without implementing a concrete TaskBus-backed publisher. The concrete publisher is the next roadmap package.

---

## 9. Event And Message Rules

### 9.1 MessageStream

All user-visible Collaborator output goes to the single Session Message Stream.

Recommended message contexts:

| Context Key | Meaning |
|---|---|
| `mode` | `feasibility`, `clarification`, `planning`, `guidance`, `validation`, `publish` |
| `task_ref_kind` | `raw`, `draft`, or `published` when task-scoped |
| `raw_task_id` | related RawTask |
| `draft_tree_id` | related draft tree |
| `command_id` | related command result |
| `authoring_invocation_id` | one Collaborator service call |

Global generation messages have no `task_id`.

Task-scoped refinement messages use `task_id=<draft_task_id>` and `context.task_ref_kind="draft"`.

### 9.2 EventStream

First version can record via messages and draft store history. If/when typed authoring events are added, use:

- `DraftTaskTreeCreated`
- `RawTaskCreated`
- `RawTaskFeasibilityAssessed`
- `RawTaskAskCreated`
- `RawTaskAnswered`
- `DraftTaskNodeUpdated`
- `DraftTaskTreeValidated`
- `DraftTaskTreePublishRequested`
- `DraftTaskTreePublished`

These are authoring/audit events, not TaskBus execution events.

---

## 10. API Alignment

The existing UI API document names these commands:

| UI API | Collaborator Surface |
|---|---|
| `appendSessionMessage` | session message append; may trigger `create_raw_task` and `assess_raw_task` |
| `answerRawTaskAsk` | `CollaboratorAuthoringService.answer_raw_task_ask` |
| `generateTaskTree` | `CollaboratorAuthoringService.generate_task_tree(raw_task_id=...)` |
| `updateTaskNode` | `TaskCommandService.update_task_node` or `refine_task_node` when LLM interpretation is needed |
| `appendTaskMessage` | `TaskCommandService.append_task_message`; may trigger `refine_task_node` |
| `resolveConfirmation` | `TaskCommandService.resolve_confirmation` |
| `publishTaskTree` | `CollaboratorAuthoringService.publish_task_tree` |

The service should not expose raw LLM proposals to UI by default. UI receives `CommandResult` and refreshed ViewModels.

---

## 11. Implementation Slices

### Slice 1 — Authoring Contracts And Validator

Deliver:

- `taskweavn.task.authoring` models:
  - `RawTask`;
  - `FeasibilityReport`;
  - `RawTaskAsk`;
  - `RawTaskAnswer`;
  - `AuthoringContext`;
  - `DraftTaskNodeProposal`;
  - `DraftTaskTreeProposal`;
  - `DraftTaskPatchProposal`;
  - `DraftTaskValidationIssue`;
  - `DraftTaskTreeValidation`;
  - `TaskNodeOption`;
- `CapabilityCatalog` protocol and static implementation;
- feasibility status model and deterministic fallback assessor;
- `DraftTaskTreeValidator`;
- tests for RawTask lifecycle, valid/invalid trees, and capabilities.

No LLM calls and no TaskBus integration in this slice.

### Slice 2 — In-Memory Draft Store

Deliver:

- concrete `InMemoryDraftTaskStore`;
- create/read/update/mark_published behavior;
- version checking;
- tree traversal helpers if needed by context builder;
- tests for stale version, status rules, root/sibling ordering.

This gives the Collaborator tools a usable test store before SQLite.

### Slice 3 — Authoring Tools

Deliver:

- `GenerateDraftTaskTreeTool`;
- `ReadDraftTaskTreeTool`;
- `UpdateDraftTaskNodeTool`;
- `ValidateDraftTaskTreeTool`;
- `AppendTaskAuthoringMessageTool`;
- action/observation types for each tool;
- tests using in-memory store and message bus.

Tools must not include file or shell capabilities.

### Slice 4 — Collaborator Authoring Service

Deliver:

- `CollaboratorAuthoringService` protocol;
- `DefaultCollaboratorAuthoringService`;
- `AuthoringContextBuilder`;
- structured LLM proposal parsing;
- prompt templates;
- tests with stub LLM.

This is the first slice where natural language can generate or refine a draft tree.

### Slice 5 — Publish Boundary

Deliver:

- `PublishDraftTasksTool`;
- integration with existing `TaskPublisher` protocol;
- validation-before-publish flow;
- draft-to-published mapping handoff;
- tests for invalid tree, publisher rejection, and success mapping.

Concrete TaskBus publishing remains owned by the TaskPublisher roadmap package.

### Slice 6 — System Template And API/CLI Adapter

Deliver:

- `CollaboratorAgentTemplate` metadata;
- built-in template registration hook or factory;
- adapter functions for `generateTaskTree`, `appendSessionMessage`, `appendTaskMessage`, and `publishTaskTree`;
- doc updates to UI API and feature plan.

This slice should make the service callable from future UI/server endpoints, without requiring the UI to exist yet.

### Slice 7 — Tests, Docs, And Release Candidate

Deliver:

- full unit/integration test pass;
- release record;
- roadmap/project roadmap updates;
- user-case notes.

End-to-end user-case testing should wait until the Task-first UI can render and operate on draft Task cards.

---

## 12. Validation Strategy

| Test | Expected |
|---|---|
| proposal to draft tree | nested proposal becomes stable `DraftTaskTree` with generated ids |
| invalid capability | validator blocks publish/generation |
| selected-node refinement | patch applies only to selected draft node |
| stale version | update is rejected |
| authoring message | one Session Message Stream receives collaborator output |
| publish invalid tree | no publisher call |
| publish valid tree | publisher boundary called and mappings recorded |
| collaborator tools | no workspace write/run-command actions are registered |
| replay timeline | task-scoped authoring messages appear under draft `TaskRef` |

---

## 13. Open Questions

1. Should the first concrete draft store be SQLite or in-memory? Recommendation: in-memory first for service/tool tests, SQLite later when the UI/server process boundary exists.
2. Should `acceptTaskTree` be distinct from `publishTaskTree`? Recommendation: yes in UI language, but first backend implementation can keep `accepted` as draft status and publish as the irreversible boundary.
3. Should options be generated by a dedicated tool in v1? Recommendation: defer until direct generation/refinement works; keep the data model ready.
4. Should Collaborator see workspace files? Recommendation: only through a future read-only summary provider, not direct file tools.
5. Where should capability catalog come from? Recommendation: static catalog first, Agent template registry later.

---

## 14. Acceptance Criteria

This feature is complete when:

- a system Collaborator template exists;
- natural language can generate a draft Task Tree through mockable LLM flow;
- selected draft Task nodes can be refined through natural language or explicit patches;
- authoring messages are written to the single Session Message Stream;
- draft trees can be deterministically validated;
- publish calls go through `TaskPublisher` only after validation;
- all durable user-visible authoring actions are replayable from backend facts;
- UI/API docs point to the implemented service and command boundaries.
