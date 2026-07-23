# Contract Revision And Execution Loops

> Status: fact-calibrated Product 1.1 P0 runtime input baseline
> Last Updated: 2026-07-10
> Original preserved as:
> `docs/architecture/archive/original/contract-revision-and-execution-loops.original.md`
> Related Product Model:
> [Plato Contract Loop Product Model](../product/plato-contract-loop-model.md),
> [Plato Runtime Input Model](../product/plato-runtime-input-model.md),
> [Plato Session Content Model](../product/plato-session-content-model.md)
> Related Architecture:
> [Authoring Domain](authoring-domain.md),
> [Authoring Command Protocol](authoring-command-protocol.md),
> [Task](task.md),
> [TaskBus](bus.md),
> [UI/backend communication](ui-backend-communication.md),
> [Context Manager](context-manager.md)
> Related Plans:
> [Runtime Input And Contract Revision Program](../plans/feature/runtime-input-and-contract-revision-program.md),
> [Plan / TaskNode Contract Migration](../plans/feature/plan-tasknode-contract-migration.md)

Fact calibration note:

- The Product 1.1 P0 runtime input path is implemented. Main Page and HTTP can
  route through `/runtime-input/route`.
- `DefaultRuntimeInputRouter` is implemented with deterministic routing plus
  an optional LLM route planner.
- `ContractRevisionCommandService` is implemented for guidance, ASK,
  confirmation, Plan/TaskNode mutation, and execution handoff command kinds.
- Read-only inquiry is implemented as a no-mutation service over UI query
  projections, optional workspace inspection context, diagnostic support, and
  an optional answer provider.
- Runtime Input Router decisions and outcomes can be persisted as durable
  Conversation / Activity messages, projected into Audit, and exported in a
  redacted diagnostic summary.
- Broader natural-language plan editing is not a general free-form agent loop.
  The current implemented mutation surface is command-backed and bounded by
  explicit command kinds.
- Outcome review and follow-up Plan cycles remain adjacent product model work,
  not complete generic autonomous loop behavior.

---

## 1. Core Model

Plato separates two loops:

```text
Contract Revision Loop
  interprets user input and mutates Plato product-state through commands

Contract Execution Loop
  executes accepted contract work and may mutate the workspace through TaskBus
```

The contract is durable product state. It is not raw LLM prose.

Current contract facts include:

- Session selection and runtime input scope;
- active Plan and PlanTaskNode rows;
- legacy DraftTaskTree compatibility facts;
- guidance facts;
- ASK answers;
- confirmation responses;
- command results, Activity descriptors, Audit descriptors, and diagnostics;
- execution handoff TaskNodes and later TaskBus lifecycle sync.

Workspace files, shell commands, tool payloads, provider logs, and raw SQLite
rows are evidence or diagnostics, not contract facts by themselves.

The stable rule is:

```text
Contract revision may create or change product contract facts.
Workspace mutation must enter the execution loop through accepted executable work.
```

---

## 2. Current Contract Revision Loop

The implemented Contract Revision Loop consists of:

- `RuntimeInputRouteRequest` / `RuntimeInputRouteResult` contract models;
- `DefaultRuntimeInputRouter`;
- `DefaultReadOnlyInquiryService`;
- `ContractRevisionCommandService`;
- command-specific handlers for interaction and PlanTaskNode work;
- durable guidance, idempotency, Conversation / Activity, Audit, and diagnostic
  projections.

Current router modes:

- `auto`
- `ask`
- `guide`
- `change`

Current router intents:

- `question`
- `guidance`
- `command`
- `ask_answer`
- `confirmation_response`
- `execution_request`
- `clarification`
- `unsupported`

Current dispatch targets:

- `read_only_inquiry`
- `record_guidance`
- `resolve_ask`
- `resolve_confirmation`
- `existing_command`
- `execution_handoff`
- `clarification`
- `unsupported`

The Router is the entrypoint into the revision loop. It is not the source of
truth for RawTask, DraftTaskTree, Plan, PlanTaskNode, ASK, confirmation, or
TaskBus state.

---

## 3. Current Router Order

`DefaultRuntimeInputRouter.route(...)` applies this current order:

1. If an active execution ASK is selected or uniquely active, answer it.
2. If an active confirmation is selected or uniquely active, require a clear
   yes/no answer and resolve it.
3. Route deterministic stop phrases to existing task stop command handling.
4. Route deterministic retry phrases to existing task retry command handling.
5. Ask an optional route planner when configured.
6. Route explicit `ask` mode or question-shaped text to read-only inquiry.
7. Route explicit `guide` mode to guidance recording.
8. Route explicit `change` mode or simple workspace-change markers to execution
   handoff.
9. Otherwise return an unsupported no-effect outcome.

The optional `RuntimeInputRoutePlanner` is currently constrained to these
planner dispatch targets:

- `read_only_inquiry`
- `record_guidance`
- `execution_handoff`
- `clarification`
- `unsupported`

Planner validation rejects low-confidence mutation and rejects read-only refs
on mutating dispatches.

---

## 4. Read-Only Inquiry

Read-only inquiry is implemented by `DefaultReadOnlyInquiryService`.

Current behavior:

- reads a `MainPageSnapshot` through `UiQueryGateway`;
- answers session, Plan, and Task status questions from projection facts;
- can summarize explicit refs such as audit records, results, workspace file
  refs, diffs, and diagnostic support refs when the needed providers are
  configured;
- can use an injected answer provider, including the guarded LLM provider path;
- returns evidence refs and warnings;
- creates answer Activity when answered.

Read-only inquiry must not mutate product or workspace state. Router decisions
for answered questions use:

```text
intent = question
dispatch_target = read_only_inquiry
side_effect = no_effect
outcome = answered
```

If inquiry context is unavailable, the Router returns an unsupported or
clarification result with no command response.

---

## 5. Contract Revision Commands

`ContractRevisionCommandService` implements a command-backed mutation boundary.

Current command kinds:

| Command kind | Current behavior |
|---|---|
| `record_guidance` | Persists `GuidanceFact` through `GuidanceFactStore`. |
| `resolve_ask` | Delegates to an interaction handler, usually the UI command gateway ASK answer path with optional execution resume dispatch. |
| `resolve_confirmation` | Delegates to the UI command gateway confirmation resolution path. |
| `patch_task_node` | Delegates versioned TaskNode patching to `UiCommandGateway.update_task_node`. |
| `create_task_node` | Adds a draft PlanTaskNode to an editable Plan through `PlanStore`. |
| `delete_task_node` | Tombstones an unexecuted PlanTaskNode by setting readiness and execution to `cancelled`. |
| `create_execution_task` | Adds an approved execution TaskNode to an editable active Plan or creates an approved Plan when none exists. |

Current command statuses:

- `accepted`
- `rejected`
- `needs_confirmation`
- `conflict`
- `noop`
- `unsupported`

Current command idempotency:

```text
same session + same idempotency key + same request hash
  -> replay cached ContractCommandResult

same session + same idempotency key + different request hash
  -> conflict with reason_code = idempotency_conflict
```

This differs from authoring command idempotency, where the first result is
replayed without request-hash conflict at the authoring service layer.

---

## 6. Guidance Facts

Guidance is implemented as typed contract state.

Current guidance storage:

- `GuidanceFact`
- `InMemoryGuidanceFactStore`
- `SqliteGuidanceFactStore`
- SQLite table `guidance_facts`

Current guidance scopes:

- session
- plan
- task

Current guidance kinds:

- `preference`
- `constraint`
- `instruction`
- `correction`
- `context_note`

`ContractGuidanceContextSource` can map guidance facts into execution context
rules. Task-scoped context includes task guidance plus session guidance.

Guidance is not raw chat history. It is typed context with source command id,
optional router decision id, scope, version, and archival state.

---

## 7. Plan And TaskNode Mutation

The current Plan/TaskNode revision surface is command-backed but bounded.

### 7.1 Patch TaskNode

`patch_task_node` delegates to `UiCommandGateway.update_task_node` and carries:

- task target;
- idempotency key;
- expected version;
- fields such as title, summary, intent/full intent, constraints, and update
  mode.

### 7.2 Create TaskNode

`create_task_node` adds a draft PlanTaskNode to an editable Plan.

Editable Plan statuses:

- `draft`
- `reviewing`
- `approved`

The command computes the next task index and order index, supports
`after_task_node_id`, and increments Plan version through `PlanStore`.

### 7.3 Delete TaskNode

`delete_task_node` does not physically remove current durable rows. It
tombstones a node by setting:

- readiness `cancelled`;
- execution `cancelled`.

It rejects deletion when the node is already published or has execution
evidence such as non-idle execution state, result ref, error ref, file summary
ref, or audit ref.

Repeated delete on an already cancelled node returns `noop`.

### 7.4 Create Execution Task

`create_execution_task` is the current execution handoff command. It does not
run tools or edit files directly.

Current behavior:

- if an editable active Plan exists, append an approved PlanTaskNode;
- if no editable active Plan exists and the command allows new Plan creation,
  create an approved Plan with one approved PlanTaskNode;
- return Activity title `Execution work created`;
- leave workspace mutation to later publish/execution flow.

This implements the architecture rule that workspace-changing runtime input
creates executable contract work rather than directly changing the workspace.

---

## 8. ASK And Confirmation

Runtime input handles active execution ASK and confirmation before ordinary
classification.

ASK path:

```text
active pending AskRequest
  -> Runtime Input Router decision
  -> ContractRevisionCommandService.resolve_ask if configured
  -> UiGatewayContractInteractionCommandHandler
  -> UI command gateway answer_ask path
  -> optional execution resume dispatch
```

When no Contract Revision service is configured, the Router can still fall back
to the existing UI command gateway ASK answer path.

Confirmation path:

```text
active pending confirmation
  -> require clear yes/no
  -> ContractRevisionCommandService.resolve_confirmation if configured
  -> UiGatewayContractInteractionCommandHandler
  -> UI command gateway resolve_confirmation path
```

Ambiguous confirmation input produces a no-effect clarification question card.

---

## 9. Current Execution Loop

The execution loop remains TaskBus-owned.

Current implemented facts:

- publish turns durable PlanTaskNodes or legacy DraftTaskTree nodes into
  executable TaskBus tasks;
- execution services claim and run TaskBus tasks;
- execution ASK uses `AskStore` and `TaskAskCommandService`, not RawTaskAsk;
- stop and retry runtime inputs route to existing task command gateway paths;
- PlanTaskNode lifecycle sync maps TaskBus statuses back into durable
  PlanTaskNode execution state.

`PlanTaskNodeLifecycleSync` maps published task status:

- `pending`
- `running`
- `waiting_for_user`
- `done`
- `failed`

and rolls Plan status to:

- `running` while any node is pending/running/waiting;
- `awaiting_acceptance` when all nodes are done;
- `failed` when any node failed.

The execution loop must not silently rewrite the Plan structure. If execution
discovers the contract is incomplete, it should cross back through ASK,
confirmation, recovery, failure, or future revision/follow-up commands.

---

## 10. Activity, Audit, And Diagnostics

Runtime input and contract revision now have durable user-visible evidence.

Current Router Activity publisher writes:

- user input message;
- Router interpretation trace;
- clarification question card when needed;
- route outcome Activity message.

Current Contract Revision Activity publisher writes command Activity for
accepted and noop command results.

Audit projection can turn Runtime Input Router messages into Audit records and
details. Diagnostic bundle export can include
`router/runtime-input.summary.json`.

The runtime input diagnostic summary is built from safe MessageStream context.
It explicitly excludes:

- model input data;
- LLM provider data;
- raw logs;
- raw SQL rows.

This evidence layer is important because read-only answers, guidance,
execution handoff, unsupported routes, and clarification outcomes must be
inspectable without exposing raw hidden internals.

---

## 11. Current Feature Classification

| Feature type | Current owning loop | Current boundary |
|---|---|---|
| Read-only question over session/plan/task/results/files/audit/diagnostics | Contract Revision Loop | `DefaultReadOnlyInquiryService`, no mutation |
| User guidance | Contract Revision Loop | `record_guidance` command and `GuidanceFactStore` |
| TaskNode field patch | Contract Revision Loop | `patch_task_node` -> UI command gateway update |
| TaskNode creation | Contract Revision Loop | `create_task_node` -> PlanStore |
| TaskNode deletion | Contract Revision Loop | `delete_task_node` tombstone -> PlanStore |
| ASK answer | Contract Revision Loop | `resolve_ask` -> UI command gateway / TaskAsk command |
| Confirmation response | Contract Revision Loop | `resolve_confirmation` -> UI command gateway |
| Stop / retry selected task | Contract Revision Loop command routing to execution controls | existing UI command gateway task commands |
| Workspace-changing text | Cross-loop handoff | `create_execution_task`, then publish/execution path |
| Workspace file edit or shell command execution | Contract Execution Loop | TaskBus execution tools only |
| Runtime route explanation | Evidence layer | durable Conversation / Activity, Audit, diagnostics |

If a future feature seems to belong to both loops, split it into:

```text
contract revision slice
execution slice
projection / audit / diagnostics slice
```

---

## 12. Current Gaps And Follow-Ups

The current implementation is P0-complete for the runtime input route matrix,
but several areas remain follow-up work:

1. Broader natural-language Plan editing is still bounded by explicit command
   kinds and optional planner dispatch. It is not a general unrestricted agent
   loop.
2. Outcome review and follow-up Plan cycle behavior remains product model work
   adjacent to Plan lifecycle and archive.
3. Sidecar restart replay and richer visual screenshot evidence are beta-depth
   validation areas, not first P0 blockers.
4. Program and feature plan readiness text may lag implementation and should
   be reconciled in later documentation slices.
5. Contract Revision command descriptors are implemented, but route-level
   support and diagnostic evidence should continue to be expanded as command
   kinds grow.
6. Legacy DraftTaskTree compatibility remains until frontend, router,
   projection, and audit paths can depend only on durable Plan/TaskNode facts.

---

## 13. Summary

The current architecture is:

```text
Main Page / HTTP runtime input
  -> Runtime Input Router
  -> read-only inquiry
     OR ContractRevisionCommandService
     OR existing UI command gateway stop/retry
     OR unsupported / clarification no-effect outcome
  -> durable Conversation / Activity / Audit / diagnostics
  -> TaskBus only after publish or accepted execution handoff
```

The key boundary is now implemented, not only aspirational:

```text
questions answer without mutation;
guidance becomes typed context;
ASK and confirmation resolve through command handlers;
PlanTaskNode changes are versioned commands;
workspace-changing text creates executable contract work;
workspace mutation remains TaskBus execution authority.
```
