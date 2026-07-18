# Collaborator Agent And Task Authoring

> Status: fact-calibrated current implementation / high-change authoring path
> Last Updated: 2026-07-10
> Work Stream: Product 1.1 authoring, Plan proposal, and workspace-informed
> Collaborator loop
> Original preserved as:
> `docs/architecture/collaborator-agent-task-authoring.original.md`
> Related Plan:
> [Collaborator Agent](../plans/feature/collaborator-agent-task-authoring.md),
> [Collaborator Workspace-Informed Authoring](../plans/feature/collaborator-workspace-informed-authoring.md),
> [Plan / TaskNode Contract Migration](../plans/feature/plan-tasknode-contract-migration.md)
> Depends On:
> [Authoring Domain](authoring-domain.md),
> [Authoring Command Protocol](authoring-command-protocol.md),
> [Tool Capability Layer](tool-capability-layer.md),
> [Workspace Communication Protocol](workspace-communication-protocol.md),
> [Task Domain/UI ViewModel Separation](task-domain-ui-model-separation.md)

Fact calibration note:

- The current codebase has a real Collaborator authoring implementation. It is
  no longer only a Phase 3C design.
- The current implementation is command-backed and service-shaped. The
  Collaborator template is metadata, while durable mutation flows through
  `AuthoringCommandService`.
- Product 1.1 added flat `Plan -> TaskNode[]` contracts while keeping legacy
  `DraftTaskTree` storage/projection compatibility.
- Workspace-informed authoring is implemented as bounded read/search context,
  evidence records, and a profile runner. It is not a workspace write or shell
  execution capability.
- Some operations named in older design text remain future or partial:
  `remove_node`, `reorder_siblings`, a user-facing waiting-for-context UI flow,
  dedicated option-generation endpoint, and unrestricted dynamic capability
  discovery are not current implemented facts.

---

## 1. Purpose

Collaborator is TaskWeavn's built-in authoring role. It turns user language into
RawTask facts, clarification asks, draft authoring state, and publishable Plans
or legacy DraftTaskTree-compatible data.

It is not an execution Agent that writes files, runs shell commands, or mutates
workspace state directly.

The current boundary is:

```text
user input
  -> Collaborator LLM/profile proposal
  -> validated authoring commands
  -> RawTask / DraftTaskTree / Plan stores and MessageStream
  -> user confirmation or publish command
  -> PlanPublisher or legacy TaskPublisher boundary
  -> published execution Tasks
```

The key invariant remains:

```text
LLM proposes.
AuthoringCommandService validates and persists.
Execution TaskBus receives only published execution Tasks.
```

---

## 2. Current Fact Baseline

| Area | Current Fact |
|---|---|
| Collaborator template | Implemented in `taskweavn.task.collaborator` as `CollaboratorAgentTemplate`. The default template has `template_id="system.collaborator"`, `capability="task_authoring"`, `command_protocol="authoring.v1"`, and `llm_visible_tool_pools=()`. |
| Natural-language service | Implemented as `DefaultCollaboratorAuthoringService`. It supports RawTask creation from a message, draft tree generation, and selected draft-node refinement. |
| Mutation boundary | Implemented as `DefaultAuthoringCommandService`. It applies typed authoring commands to stores and optional message/publish/Plan boundaries. |
| UI/API adapter | Implemented as `DefaultCollaboratorApiAdapter`. It exposes session start, append session message, answer RawTask ask(s), generate task tree, append draft task message, and publish task tree. |
| Command gateway | Main UI command gateway routes global input, task-tree generation, authoring ASK answers, draft task input, and publish through the Collaborator adapter or command services. |
| Authoring stores | In-memory and SQLite stores exist for RawTask and DraftTaskTree facts. SQLite stores also track active authoring state and authoring command idempotency records. |
| Plan migration | Authoring output can create durable Plan records from draft output. UI publish prefers an active durable Plan through `PlanPublisher` and falls back to legacy DraftTaskTree publish when needed. |
| Capability catalog | `CapabilityDescriptor`, `CapabilityCatalog`, and `StaticCapabilityCatalog` are implemented. The default sidecar catalog is static: `general`, `writing`, `coding`, `testing`, `research`. |
| Workspace-informed authoring | Implemented through a bounded profile runner, read/search workspace tools, safe labels, and authoring evidence records. |
| Execution tools | Collaborator does not mount write, shell, command execution, or arbitrary workspace-changing tools by default. |

---

## 3. Current Authoring Domain Objects

`src/taskweavn/task/authoring.py` defines the current authoring contracts.

### 3.1 RawTask And Feasibility

Implemented objects:

- `RawTask`
- `RawTaskAsk`
- `RawTaskAnswer`
- `RawTaskAnswerOption`
- `FeasibilityReport`

Implemented `RawTask.status` values:

- `created`
- `assessing`
- `awaiting_user`
- `ready_to_plan`
- `converted`
- `rejected`
- `cancelled`

Implemented `FeasibilityReport.status` values:

- `ready`
- `needs_clarification`
- `needs_user_permission`
- `partially_feasible`
- `not_supported`
- `unsafe`

Current validators enforce facts such as:

- `awaiting_user` requires at least one unanswered required ask.
- `ready_to_plan` requires a feasibility report whose status is `ready` or
  `partially_feasible`.
- `rejected` with feasibility requires `not_supported` or `unsafe`.
- answers must reference asks on the same RawTask.

### 3.2 Draft And Plan Proposal Contracts

Implemented proposal contracts include:

- `DraftTaskNodeProposal`
- `DraftTaskTreeProposal`
- `DraftTaskPatchProposal`
- `TaskNodeOption`
- `TaskNodeOptionSet`
- `PlanTaskNodeProposal`
- `PlanProposal`

Current Product 1.1 behavior is important:

- `PlanProposal` is the flat `Plan -> TaskNode[]` LLM contract.
- `PlanProposal.schema_version` is `plato.plan.proposal.v1`.
- `PlanProposal` rejects hierarchy and role fields that belong to deferred
  designs.
- `depends_on` may reference proposal-local `client_task_id` or `task_index`
  values and is validated for unknown references, self-dependency, and cycles.
- Legacy `DraftTaskTreeProposal` input is still accepted, but collaborator
  mapping flattens nested draft proposals before persisting through the current
  draft store path.

### 3.3 Authoring Commands

Implemented command contracts include:

- `MutateRawTaskCommand`
- `MutateDraftTaskTreeCommand`
- `PublishDraftTaskTreeCommand`
- `AuthoringCommandBatch`
- `AuthoringCommandResult`
- `AuthoringMessageEffect`
- `AuthoringCommandError`
- `AuthoringCommandWarning`

`AuthoringCommandBatch` defaults to `all_or_nothing`.
`best_effort` exists for non-publish batches, but publish batches are rejected
when marked best-effort.

Current RawTask operations supported by `DefaultAuthoringCommandService`:

- `create`
- `set_intent_summary`
- `record_feasibility`
- `add_clarification_ask`
- `apply_answer`
- `update_constraints`
- `update_assumptions`
- `set_status`

Current DraftTaskTree operations supported by `DefaultAuthoringCommandService`:

- `create_tree`
- `patch_node`
- `add_node`
- `attach_options`
- `mark_accepted`

Partial or non-current DraftTaskTree operations:

- `mark_ready` is accepted as a no-op warning.
- `remove_node` is declared in the operation literal but is not handled by the
  current command service.
- `reorder_siblings` is declared in the operation literal but is not handled by
  the current command service.

### 3.4 Validation And Capability Checks

`DraftTaskTreeValidator` is implemented and deterministic. It validates:

- node count limits;
- root parent constraints;
- duplicate node ids;
- session/tree mismatches;
- duplicate sibling order;
- empty title or intent;
- missing required capability;
- unknown capability;
- cancelled node status;
- publishable status;
- proposal depth and node count.

The validator uses `CapabilityCatalog`, and the current local sidecar catalog is
static unless a dependency override supplies another catalog.

---

## 4. Collaborator Template, Service, And Profile

### 4.1 Template

The default Collaborator template is implemented as metadata:

```text
template_id: system.collaborator
capability: task_authoring
display_name: Collaborator
command_protocol: authoring.v1
capability_catalog: execution.capabilities.readonly
llm_visible_tool_pools: ()
```

The empty tool-pool tuple is a current safety fact. Collaborator plans with
capability descriptors and authoring proposals; it does not receive the full
execution tool universe by default.

### 4.2 Natural-Language Authoring Service

`DefaultCollaboratorAuthoringService` is the current LLM proposal mapper.

Implemented service methods:

- `create_raw_task_from_message(...)`
- `generate_task_tree(...)`
- `refine_task_node(...)`

Current behavior:

- builds read-only context through `AuthoringContextBuilder`;
- runs a bounded `CollaboratorAuthoringProfileRunner`;
- accepts raw JSON responses or terminal tool calls;
- normalizes common RawTask proposal shapes;
- accepts Product 1.1 flat Plan proposals and legacy draft tree proposals;
- turns proposals into `MutateRawTaskCommand` or
  `MutateDraftTaskTreeCommand`;
- submits all durable changes through `AuthoringCommandService`;
- returns structured `AuthoringCommandResult` errors when proposal parsing or
  validation fails.

Not current on this service protocol:

- a separate public `assess_raw_task` method;
- a separate `answer_raw_task_ask` method;
- a separate `propose_task_options` method;
- a separate `validate_task_tree` method;
- a direct service-level publish method.

Those operations are currently handled through command services, the API
adapter, or remain future extension points.

### 4.3 Collaborator Authoring Profile

The current profile constants and runner are implemented in:

- `src/taskweavn/task/collaborator_loop.py`
- `src/taskweavn/task/collaborator_profile_runner.py`

Allowed profile tool names:

- `authoring_read_workspace`
- `authoring_search_workspace`
- `ask_authoring`
- `finish_authoring`

Forbidden tool names are declared and enforced by the context dispatcher:

- `write_file`
- `run_command`
- `shell`
- `execute_code`

Current runner behavior:

- one request uses a bounded loop with `max_context_steps`;
- workspace read/search tools are exposed only when a workspace context source
  is configured;
- terminal tool calls must be the only tool call in the assistant turn;
- read/search observations are appended as tool messages;
- evidence refs from observations are forwarded to terminal results;
- parser, validation, forbidden-tool, and step-limit failures are mapped to a
  rejected profile result.

`CollaboratorAuthoringLoopResult` includes a `waiting_for_context` shape, and
tests validate that shape. The current default runner and
`DefaultCollaboratorAuthoringService` do not expose a complete user-facing
waiting-for-context flow. In the current service, any non-finished profile
result is treated as a proposal failure before command submission.

---

## 5. Authoring Context And Workspace Evidence

### 5.1 DefaultAuthoringContextBuilder

`DefaultAuthoringContextBuilder` is implemented and read-only.

It reads:

- `RawTaskStore`
- `DraftTaskStore`
- `MessageStream`
- `CapabilityCatalog`

It builds:

- session context with raw tasks, selected RawTask, draft trees, recent
  messages, unresolved asks, capabilities, and constraints;
- task context for draft `TaskRef` only, including selected node, ancestors,
  children, recent task messages, and relevant capabilities.

It does not mutate RawTask, DraftTaskTree, MessageStream, or TaskBus.

### 5.2 Workspace-Informed Authoring

`LocalCollaboratorWorkspaceContextSource` is implemented for bounded read/search
workspace context.

Current read facts:

- accepts relative paths or `workspace://current/...` labels;
- rejects raw absolute path requests;
- uses `Workspace` path resolution and protected metadata checks;
- returns bounded UTF-8 snippets, content hashes, safe path labels, and evidence
  refs;
- records denied and omitted reads with explicit reasons.

Current search facts:

- default guidance scope includes README, AGENTS, docs/plans, docs/architecture,
  docs/decisions, and docs/engineering;
- full-workspace globs are skipped;
- protected globs and protected metadata paths are skipped;
- candidate files larger than the read limit or non-UTF-8 files are skipped;
- results include safe labels, snippets, scores, hashes, and evidence refs.

`AuthoringEvidenceRecord` requires `workspace://current` labels and rejects raw
absolute path exposure. Current tests verify safe labels, metadata protection,
absolute path redaction, omitted/denied evidence, and sidecar acceptance for
forced read/search/finish and read/ask flows.

---

## 6. Persistence And Active State

Current store protocols and implementations are in:

- `src/taskweavn/task/stores.py`
- `src/taskweavn/task/sqlite_authoring.py`
- `src/taskweavn/task/authoring_idempotency.py`

Implemented protocols:

- `RawTaskStore`
- `DraftTaskStore`
- `AuthoringStateStore`
- `AuthoringCommandIdempotencyStore`

Implemented in-memory stores:

- `InMemoryRawTaskStore`
- `InMemoryDraftTaskStore`
- `InMemoryAuthoringCommandIdempotencyStore`

Implemented SQLite stores:

- `SqliteRawTaskStore`
- `SqliteDraftTaskStore`
- `SqliteAuthoringStateStore`
- `SqliteAuthoringCommandIdempotencyStore`

The main sidecar runtime uses SQLite authoring stores by default when no
dependency override supplies stores. Authoring facts are stored in the workspace
authoring database.

`ActiveAuthoringState` tracks one session's active authoring pointer:

- no active authoring state;
- active RawTask;
- active DraftTaskTree;
- published draft tree;
- cancelled flow.

It also carries `active_plan_id` in the current schema. This is part of the
Product 1.1 Plan migration path.

Authoring command idempotency is implemented by session and idempotency key.
The current service replays the first cached terminal result for the same key
and request hash path instead of creating duplicate authoring side effects.

---

## 7. UI/API And Command Gateway Alignment

Current UI command gateway facts live in
`src/taskweavn/server/ui_contract/command_gateway.py`.

Implemented command gateway paths:

- global session input calls `collaborator.append_session_message`;
- `generate_task_tree` validates RawTask readiness when a RawTask id is
  supplied;
- prompt-driven generation may first create a RawTask and then generate a tree
  if the RawTask is ready;
- draft task input calls `collaborator.append_task_message`;
- published task input uses normal task command handling;
- authoring ASK batch answers call `collaborator.answer_raw_task_asks`;
- when all RawTask asks are answered, the gateway attempts task tree generation;
- stale authoring asks are rejected when an active TaskTree already superseded
  the RawTask;
- publish first tries active durable Plan publishing; if unavailable it falls
  back to legacy DraftTaskTree publishing through the Collaborator API adapter.

`DefaultCollaboratorApiAdapter` returns the stable `CommandResult` surface. It
does not expose raw LLM proposal payloads to callers by default.

---

## 8. Plan / TaskNode Migration Boundary

The old design centered RawTask -> DraftTaskTree -> published Task. That storage
path still exists, but Product 1.1 has added durable Plan facts.

Current migration facts:

- `PlanProposal` is the flat LLM proposal contract.
- `DefaultCollaboratorAuthoringService` maps Plan proposals into draft tree
  commands for compatibility.
- `DefaultAuthoringCommandService` can create a durable Plan from a draft tree
  when a `PlanStore` is configured.
- main sidecar runtime wires `SqlitePlanStore`, `DefaultPlanPublisher`, and
  authoring state active Plan identity.
- UI publish prefers `DefaultPlanPublisher.publish_plan(...)` for an active
  durable Plan.
- legacy DraftTaskTree publish remains as fallback compatibility.

This means future docs should not describe DraftTaskTree as the only current
contract. It is still an implementation and compatibility substrate, but the
canonical Product 1.1 user-facing contract is moving to `Plan -> TaskNode[]`.

---

## 9. Publish Boundary

Two publish paths currently coexist.

### 9.1 Durable Plan Publish

`DefaultPlanPublisher` publishes durable Plans by adapting PlanTaskNodes to the
existing `TaskPublisher` request path.

Current behavior:

- rejects or skips plans with no TaskNodes;
- skips cancelled or archived Plans;
- reuses existing lineage when a Plan was already published;
- writes published task ids and mappings back to the Plan store.

### 9.2 Legacy DraftTaskTree Publish

`PublishDraftTaskTreeCommand` still exists and is handled by
`DefaultAuthoringCommandService`.

Current behavior:

- requires a configured `TaskPublisher`;
- rejects empty draft trees;
- does not support partial root publish through this boundary;
- rejects already published or cancelled draft nodes;
- requires every draft node to be `accepted` before publish;
- optionally runs `DraftTaskTreeValidator`;
- requires publisher mappings for every draft node;
- marks DraftTaskTree published and updates authoring active state when
  configured;
- emits an informational message effect for successful publish.

`DefaultCollaboratorApiAdapter.publish_task_tree(...)` first marks the draft
tree accepted, then submits the publish command.

---

## 10. Current Non-Goals And Guardrails

Current Collaborator authoring does not:

- write workspace files;
- run shell commands;
- expose execution tools by default;
- mutate RawTask or DraftTaskTree state outside command services;
- publish RawTask to Execution TaskBus;
- treat ordinary execution Agents as authoring command submitters;
- provide a complete multi-user collaborative editing model;
- provide a dedicated Feasibility Agent;
- provide a dedicated option-generation endpoint;
- provide a public dynamic capability catalog sourced from all tools,
  workspace manifests, and telemetry.

Current implementation is compatible with future extensions, but those
extensions should preserve the command-first mutation boundary.

---

## 11. Current Test Coverage

Direct tests cover the current implementation in these areas:

- authoring contracts and validators;
- RawTask status/ask/answer invariants;
- Plan proposal validation and flat task ordering/dependency rules;
- StaticCapabilityCatalog query and duplicate handling;
- AuthoringCommandBatch invariants;
- DefaultAuthoringCommandService command application, rollback,
  idempotency, publish validation, and publisher rejection handling;
- in-memory RawTask and DraftTask stores;
- SQLite RawTask, DraftTaskTree, active state, mapping, migration, and
  idempotency stores;
- DefaultAuthoringContextBuilder session and draft task contexts;
- CollaboratorAuthoringProfile allowed tools, terminal tools, ask mapping, and
  waiting-for-context result shape;
- DefaultCollaboratorAuthoringService RawTask proposal mapping, workspace
  read/search dispatch, ask dispatch, Plan proposal acceptance, invalid
  proposal rejection, and draft node refinement;
- DefaultCollaboratorApiAdapter template registration, ask answers, task tree
  generation, draft task refinement, and publish boundary;
- LocalCollaboratorWorkspaceContextSource read/search policy and evidence;
- sidecar acceptance for workspace-informed read/search/finish and read/ask
  flows.

---

## 12. Future Work

Future work should be described as future, not current fact:

1. Implement command service support for `remove_node` and `reorder_siblings`,
   or remove those operation literals until they are needed.
2. Decide whether `mark_ready` should become a real lifecycle operation or stay
   absent.
3. Promote `waiting_for_context` from a model/tested result shape into an
   end-to-end UI/API flow if product wants context selection before authoring.
4. Decide whether option generation is a separate Collaborator endpoint or
   remains `attach_options` plus task message flow.
5. Continue migrating new Product 1.1 work to durable Plan / TaskNode identity.
6. Replace the static local capability catalog only when a validated dynamic
   catalog design exists.
7. Add explicit diagnostics/read models for authoring evidence if in-memory
   evidence is insufficient for release-readiness.

---

## 13. Summary

Collaborator authoring is now implemented as a controlled LLM proposal layer
over typed command services, stores, and publish boundaries.

The current architecture is not "a persistent Collaborator Agent with tools".
It is:

```text
metadata template
  + bounded LLM/profile runner
  + read-only context builder and optional workspace evidence
  + structured proposal normalization
  + AuthoringCommandService mutation boundary
  + RawTask / DraftTaskTree / Plan stores
  + PlanPublisher or legacy TaskPublisher publish boundary
```

Any future extension should preserve that separation and avoid reintroducing
direct LLM-visible system-state mutation or unrestricted workspace tools.
