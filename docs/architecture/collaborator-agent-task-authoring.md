# Collaborator Agent And Task Authoring

> Status: draft
> Last Updated: 2026-05-14
> Work Stream: Phase 3C — Task Authoring Foundation
> Related Plan: [Collaborator Agent](../plans/feature/collaborator-agent-task-authoring.md)
> Depends On: [Task Domain/UI ViewModel Separation](task-domain-ui-model-separation.md), [Authoring Domain](authoring-domain.md), [Authoring Command Protocol](authoring-command-protocol.md), [Tool Capability Layer](tool-capability-layer.md), [Workspace Communication Protocol](workspace-communication-protocol.md)
> Related Docs: [Agent](agent.md), [Task](task.md), [TaskBus](bus.md), [UI API Interfaces](../plans/ui/ui-api-interfaces.md)
> User Needs: [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md), [UN-101](../user_model/needs/UN-101-photo-curation-batch-screening.md), [UN-102](../user_model/needs/UN-102-courseware-html-generation.md), [UN-103](../user_model/needs/UN-103-car-purchase-decision-support.md)

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

All durable state lives in `RawTaskStore`, `DraftTaskStore`, `MessageStream`, publish mappings, and future TaskBus/EventStream facts.

The Collaborator implementation is expected to change frequently while product behavior is explored. Therefore prompts and proposal parsing should be easy to replace, while command handlers and storage contracts stay more stable.

### 1.1 User-Need Traceability

Collaborator Agent is the first product-facing implementation of Authoring Domain.

| Need | Collaborator Responsibility |
|---|---|
| [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md) | Produce RawTask feasibility, clarification asks, and capability boundary messages before execution. |
| [UN-101](../user_model/needs/UN-101-photo-curation-batch-screening.md) | Convert batch screening goals into editable review/checkpoint Task Trees. |
| [UN-102](../user_model/needs/UN-102-courseware-html-generation.md) | Convert teaching goals and constraints into editable content-generation Task Trees. |
| [UN-103](../user_model/needs/UN-103-car-purchase-decision-support.md) | Keep high-risk decision-support prompts in clarification/evaluation mode until constraints and source expectations are explicit. |

---

## 2. Current Baseline

The previous Phase 3C package already introduced the boundary objects this feature should reuse:

| Area | Existing Contract |
|---|---|
| Authoring boundary | `Authoring Domain` separates RawTask/DraftTaskTree from Execution TaskBus |
| Draft facts | `DraftTaskNode`, `DraftTaskTree`, `DraftToPublishedMapping` |
| Published facts | `TaskDomain` |
| References | `TaskRef(kind="draft"|"published", id=...)` |
| Store protocols | `DraftTaskStore`, `TaskStore`; `RawTaskStore` is added by this package |
| UI projection | `TaskProjectionService`, `TaskTreeView`, `TaskCardView`, `TaskDetailView` |
| Commands | `TaskCommandService`, `TaskPublisher`, `CommandResult`; Authoring commands are added by this package |
| Replay | `TaskInteractionTimelineService` |
| User-visible messages | `MessageStream`, `MessageBus`, `AgentMessage` |

Therefore this feature should not redefine Task models. It should add the missing authoring layer:

```text
CollaboratorAuthoringService
  + RawTask creation
  + feasibility assessment
  + clarification asks
  + prompt/context builder
  + AuthoringCommandService
  + command handlers
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
- Do not require a separate Feasibility Agent in the first version; feasibility can live in Collaborator-owned service logic.
- Do not rely on many LLM-visible system tools for RawTask/DraftTaskTree state mutation.
- Do not use execution-style strong audit for every exploratory RawTask edit.

---

## 5. Core Decision

### 5.1 Collaborator Is A System Agent Template, Not A Persistent Actor

The system should register a built-in template:

```python
CollaboratorAgentTemplate(
    template_id="system.collaborator",
    capability="task_authoring",
    display_name="Collaborator",
    command_protocol="authoring.v1",
    capability_catalog="execution.capabilities.readonly",
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

### 5.2 System State Changes Use Commands, Not Ordinary Tools

Task authoring changes TaskWeavn's own state. These changes should go through [Authoring Command Protocol](authoring-command-protocol.md), not through many LLM-visible tool calls.

Authoring command handlers operate on:

- `DraftTaskStore`;
- `RawTaskStore`;
- `MessageBus` / `MessageStream`;
- `TaskPublisher`;
- capability registry / validation policy.

They do not operate on:

- workspace files;
- shell commands;
- sandbox;
- arbitrary runtime tools.

The LLM should produce structured proposals. Code validates and commits those proposals with object-scoped commands:

```text
Collaborator LLM -> AuthoringProposal
DefaultCollaboratorAuthoringService -> AuthoringCommandBatch
AuthoringCommandService -> stores/messages/events
```

Compatibility tools can exist as thin adapters over command handlers, but they are not the source of truth.

Ordinary execution Agents must not submit authoring commands.

### 5.3 Publish Is A Boundary, Not Direct TaskBus Access

The Collaborator should not call TaskBus internals directly. It should call `TaskPublisher.publish_draft_tree(...)`.

That lets the next roadmap package implement one safe publish path for:

- Collaborator;
- user custom Task Trees;
- pipeline loader;
- scheduled publishers;
- API publishers.

### 5.4 Collaborator Plans With Capabilities, Not Full Tool Pools

Collaborator needs to understand the system's execution capability range, but it should not mount every workspace-changing or external tool.

The intended split:

```text
Collaborator
  sees: read-only CapabilityCatalog
  submits: AuthoringCommandBatch through service-owned commands
  does not mount: workspace.basic / external.connectors by default
```

Task Nodes should reference `required_capability`. Execution Agents later bind that capability to workspace operations under policy. Current Tool classes can implement those operations as adapters while [Workspace Communication Protocol](workspace-communication-protocol.md) matures.

This keeps RawTask and clarification coherent while preventing Collaborator from becoming an overloaded agent with the full tool universe in context.

### 5.5 Collaborator Is One Role, Internally Split By Services

Do not split Collaborator into multiple user-facing Agents in the first version. Splitting too early would fragment RawTask ownership and make clarification state harder to explain.

Internally, keep replaceable service boundaries:

| Component | Responsibility |
|---|---|
| `RawTaskService` | Create/update RawTask and answers. |
| `FeasibilityAssessor` | Evaluate feasibility and missing inputs. |
| `CapabilityCatalog` | Provide read-only capability descriptors. |
| `TaskTopologyPlanner` | Generate DraftTaskTree proposals. |
| `TopologyQualityGate` | Validate capability coverage and topology quality. |
| `AuthoringCommandService` | Validate and commit authoring state changes. |
| `TaskPublisher` | Publish confirmed draft trees. |

Future specialist Agents can be introduced behind these protocols if evidence shows the single Collaborator role is too loaded.

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
    ) -> AuthoringCommandResult: ...
```

The default implementation coordinates LLM calls, proposal parsing, command creation, and command submission. Command handlers remain independently testable.

### 6.2 AuthoringCommandService

The command service is the authoritative mutation boundary for RawTask and DraftTaskTree state.

```python
class AuthoringCommandService(Protocol):
    def submit(
        self,
        batch: AuthoringCommandBatch,
    ) -> AuthoringCommandResult: ...
```

Command batches are intentionally coarse-grained:

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

Primary command types:

| Command | Scope | Purpose |
|---|---|---|
| `MutateRawTaskCommand` | RawTask | Create/update RawTask, feasibility, asks, answers, assumptions, and status. |
| `MutateDraftTaskTreeCommand` | DraftTaskTree | Create tree, patch nodes, reorder, attach options, and mark accepted. |
| `PublishDraftTaskTreeCommand` | DraftTaskTree -> PublishedTask | Validate and publish confirmed draft tree. |

First version should default to `all_or_nothing` and usually keep one object scope per batch. Cross-object batches are allowed only for safe adjacent transitions, such as RawTask `ready_to_plan` plus DraftTaskTree creation.

### 6.3 AuthoringContextBuilder

Builds prompt context from server facts.

Inputs:

- session id;
- optional `RawTask`;
- current feasibility report and unresolved asks;
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
    raw_task_id: str | None = None
    feasibility_status: FeasibilityStatus | None = None
    unresolved_asks: tuple[RawTaskAsk, ...] = ()
    selected_task_ref: TaskRef | None = None
    mode: Literal["session", "task"]
    draft_trees: tuple[DraftTaskTree, ...] = ()
    selected_node: DraftTaskNode | None = None
    ancestors: tuple[DraftTaskNode, ...] = ()
    children: tuple[DraftTaskNode, ...] = ()
    recent_messages: tuple[AgentMessage, ...] = ()
    capabilities: tuple[CapabilityDescriptor, ...] = ()
    constraints: dict[str, object] = {}
```

The context builder is intentionally read-only.

### 6.4 CapabilityCatalog

The Collaborator must not hallucinate `required_capability`.

First version can be a static catalog, but the protocol should be descriptor-based so future tool supply does not force a redesign:

```python
class CapabilityDescriptor(BaseModel):
    capability_id: str
    display_name: str
    summary: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    preconditions: tuple[str, ...] = ()
    cost_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    latency_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    risk_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    reliability_score: float | None = None
    applicable_domains: tuple[str, ...] = ()
    anti_patterns: tuple[str, ...] = ()
```

```python
class CapabilityCatalog(Protocol):
    def all(self) -> tuple[CapabilityDescriptor, ...]: ...
    def get(self, capability_id: str) -> CapabilityDescriptor | None: ...
    def contains(self, capability_id: str) -> bool: ...
    def query(
        self,
        intent: str,
        *,
        domains: tuple[str, ...] = (),
        limit: int = 20,
    ) -> tuple[CapabilityDescriptor, ...]: ...
```

Early implementation can use a static in-memory catalog. Later this should read Agent templates, `WorkspaceManifest` / `WorkspaceCapabilityDescriptor`, Tool adapter metadata, validation results, and runtime reliability signals.

### 6.5 DraftTaskTreeValidator

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

### 6.6 Authoring Command Handlers And Optional Tool Adapters

Command handlers are the low-level system-state mutation boundary. They should be called by `CollaboratorAuthoringService` and UI/API command endpoints.

Optional tool adapters can be added later for compatibility, but they must call the same command handlers. They should not become a second mutation path.

Minimum command handlers:

| Handler | Primary Store/Boundary | Purpose |
|---|---|---|
| `MutateRawTaskHandler` | `RawTaskStore` / `MessageStream` | Persist user intent, feasibility, clarification asks, answers, and RawTask status. |
| `MutateDraftTaskTreeHandler` | `DraftTaskStore` | Persist generated roots, node patches, reorder operations, options, and accepted state. |
| `ValidateDraftTaskTreeHandler` | validator / CapabilityCatalog | Return deterministic validation and topology warnings. |
| `PublishDraftTaskTreeHandler` | `TaskPublisher` | Publish validated draft tree through publisher boundary. |

Deferred:

- Tool adapters such as `CreateRawTaskTool` or `UpdateDraftTaskNodeTool` should be deferred unless AgentLoop integration requires them.
- `ProposeTaskNodeOptions` can be an LLM proposal type first, not a separate system tool.

---

## 7. LLM Output Contracts

The LLM should produce structured authoring proposals. Persistent writes should be performed by command handlers/services after validation.

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

The proposal does not include final ids. The command handler assigns ids and tree metadata.

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
  -> if missing info: MutateRawTaskCommand adds clarification ask + actionable message
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
  -> MutateDraftTaskTreeCommand persists DraftTaskTree
  -> command handler publishes assistant summary
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
  -> MutateDraftTaskTreeCommand applies patch
  -> command handler publishes assistant response
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
  -> PublishDraftTaskTreeCommand calls TaskPublisher.publish_draft_tree
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
| `updateTaskNode` | explicit patch uses `AuthoringCommandService`; natural language update uses `refine_task_node` |
| `appendTaskMessage` | appends task-scoped message; may trigger `refine_task_node` |
| `resolveConfirmation` | `TaskCommandService.resolve_confirmation` |
| `publishTaskTree` | `CollaboratorAuthoringService.publish_task_tree` |

The service should not expose raw LLM proposals to UI by default. UI receives `AuthoringCommandResult` and refreshed ViewModels.

---

## 11. Implementation Slices (Revised)

### 11.1 Redesign Review Conclusion

After introducing Authoring Command Protocol, the old slice shape is too coarse.

The critical dependency order should be:

```text
stable facts
  -> command contracts
  -> stores
  -> command handlers
  -> context builder
  -> LLM collaborator proposal mapping
  -> publish boundary
  -> UI/API adapters
```

This keeps the most volatile part, Collaborator prompt/proposal parsing, away from the foundation. It also prevents the first implementation from accidentally turning authoring state mutation into a pile of LLM-visible system tools.

The current first implementation pass, `Draft authoring contracts + validator`, remains valid. It should be treated as a narrower completed slice, not as the full Authoring foundation.

### Slice 1 — Draft Authoring Contracts And Validator

Status: implemented / keep.

Deliver:

- `AuthoringContext`;
- `DraftTaskNodeProposal`;
- `DraftTaskTreeProposal`;
- `DraftTaskPatchProposal`;
- `TaskNodeOption`;
- `TaskNodeOptionSet`;
- `DraftTaskValidationIssue`;
- `DraftTaskTreeValidation`;
- `CapabilityCatalog` minimal protocol and static implementation;
- `DraftTaskTreeValidator`;
- tests for proposal shapes, option shapes, draft validation, and capability lookup.

This slice intentionally does not include RawTask, command handlers, stores, LLM calls, or TaskBus integration.

### Slice 2 — RawTask Contracts And Feasibility Model

Deliver:

- `RawTask`;
- `RawTaskStatus`;
- `FeasibilityReport`;
- `FeasibilityStatus`;
- `RawTaskAsk`;
- `RawTaskAnswer`;
- RawTask version and lifecycle rules;
- deterministic fallback feasibility assessor or helper;
- tests for status transitions, ask/answer linkage, and non-execution boundary.

This slice should answer: "Can the system represent an unclear or impossible user request without pretending it is executable?"

No stores, command handlers, LLM calls, or TaskBus integration in this slice.

### Slice 3 — Authoring Command Protocol Contracts

Deliver:

- `ActorRef`;
- `AuthoringCommandBatch`;
- `MutateRawTaskCommand`;
- `RawTaskOperation`;
- `MutateDraftTaskTreeCommand`;
- `DraftTaskTreeOperation`;
- `PublishDraftTaskTreeCommand`;
- `AuthoringCommandResult`;
- `AuthoringCommandError`;
- `AuthoringMessageEffect`;
- idempotency/version fields;
- tests for command validation, batch invariants, and error/result shape.

This slice defines the stable mutation language. It should still be pure data contracts.

No command handler logic yet.

### Slice 4 — In-Memory Authoring Stores

Deliver:

- `RawTaskStore` protocol;
- `DraftTaskStore` protocol alignment if the existing one needs extension;
- `InMemoryRawTaskStore`;
- `InMemoryDraftTaskStore`;
- version checks;
- draft tree traversal helpers;
- publish mapping persistence in memory;
- tests for stale version, status rules, root/sibling ordering, and read-after-write.

This gives command handlers a deterministic substrate before SQLite or server API work.

SQLite persistence should remain deferred until service semantics settle.

### Slice 5 — Authoring Command Service And Handlers

Deliver:

- `AuthoringCommandService` protocol;
- `DefaultAuthoringCommandService`;
- `MutateRawTaskHandler`;
- `MutateDraftTaskTreeHandler`;
- `ValidateDraftTaskTreeHandler`;
- message effect application through `MessageStream` / `MessageBus`;
- command idempotency and structured errors;
- `all_or_nothing` execution semantics for first version;
- tests using in-memory stores and message stream.

Command handlers must not include file, shell, sandbox, or external connector capabilities.

This is the first slice where TaskWeavn system state actually changes through Authoring Commands.

### Slice 6 — Authoring Context Builder And Capability Catalog v1

Deliver:

- `AuthoringContextBuilder`;
- selected-node context reconstruction;
- recent session/task message selection;
- RawTask + draft tree context assembly;
- descriptor-based `CapabilityCatalog` v1 or an adapter from the current minimal catalog;
- tests for session mode, task mode, and capability filtering.

The context builder is read-only. It should never mutate RawTask, DraftTaskTree, MessageStream, or TaskBus.

### Slice 7 — Collaborator Proposal Mapping Service

Deliver:

- `CollaboratorAuthoringService` protocol;
- `DefaultCollaboratorAuthoringService`;
- prompt templates;
- structured proposal parsing;
- proposal-to-command-batch mapping;
- stub-LLM tests for:
  - RawTask feasibility proposal;
  - DraftTaskTree proposal;
  - selected-node patch proposal;
  - invalid proposal repair diagnostics.

This is the first slice where natural language can generate or refine draft authoring state, but durable writes still go through `AuthoringCommandService`.

### Slice 8 — Publish Boundary

Deliver:

- `PublishDraftTaskTreeCommand` handler completion;
- integration with `TaskPublisher`;
- validation-before-publish flow;
- draft-to-published mapping handoff;
- tests for invalid tree, publisher rejection, duplicate publish, and success mapping.

Concrete TaskBus-backed publishing remains owned by the TaskPublisher roadmap package unless it is already available.

### Slice 9 — System Template And UI/API Adapter

Deliver:

- `CollaboratorAgentTemplate` metadata;
- built-in template registration hook or factory;
- adapter functions for:
  - `appendSessionMessage`;
  - `answerRawTaskAsk`;
  - `generateTaskTree`;
  - `appendTaskMessage`;
  - `publishTaskTree`;
- UI API doc alignment.

This slice makes the service callable from future UI/server endpoints without requiring the frontend to exist.

### Slice 10 — Hardening, Docs, And Release Candidate

Deliver:

- full unit/integration test pass;
- updated architecture docs;
- updated feature plan;
- release record;
- roadmap/project roadmap status update;
- user-case notes.

End-to-end user-case testing should wait until the Session UI can render and operate on RawTask and DraftTask authoring cards.

### Deferred From This Package

- LLM-visible authoring tool adapters;
- AuthoringBus;
- SQLite authoring stores;
- typed EventStream authoring events beyond message/store traceability;
- dedicated Feasibility Agent;
- separate option-generation tool.
- WorkspaceGateway / WorkspaceRequest execution binding.

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
| command handlers | no workspace write/run-command actions are registered |
| replay timeline | task-scoped authoring messages appear under draft `TaskRef` |

---

## 13. Open Questions

1. Should the first concrete draft store be SQLite or in-memory? Recommendation: in-memory first for service/tool tests, SQLite later when the UI/server process boundary exists.
2. Should `acceptTaskTree` be distinct from `publishTaskTree`? Recommendation: yes in UI language, but first backend implementation can keep `accepted` as draft status and publish as the irreversible boundary.
3. Should options be generated by a dedicated tool in v1? Recommendation: defer until direct generation/refinement works; keep the data model ready.
4. Should Collaborator see workspace files? Recommendation: only through a future read-only summary provider, not direct file tools.
5. Where should capability catalog come from? Recommendation: static catalog first, then Agent template registry and WorkspaceManifest-derived descriptors later.
6. Should authoring commands be exposed as LLM tools? Recommendation: no for v1; if needed later, expose thin adapters over command handlers.

---

## 14. Acceptance Criteria

This feature is complete when:

- a system Collaborator template exists;
- natural language can generate a draft Task Tree through mockable LLM flow;
- selected draft Task nodes can be refined through natural language or explicit patches;
- RawTask and DraftTaskTree mutations go through command handlers, not direct LLM tool calls;
- authoring messages are written to the single Session Message Stream;
- draft trees can be deterministically validated;
- publish calls go through `TaskPublisher` only after validation;
- all durable user-visible authoring actions are replayable from backend facts;
- UI/API docs point to the implemented service and command boundaries.
