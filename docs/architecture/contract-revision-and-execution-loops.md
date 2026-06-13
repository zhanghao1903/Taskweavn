# Contract Revision And Execution Loops

> Status: active architecture baseline
>
> Last Updated: 2026-06-13
>
> Related Product Model:
> [Plato Contract Loop Product Model](../product/plato-contract-loop-model.md)
>
> Related:
> [Architecture Overview](overview.md),
> [Authoring Domain](authoring-domain.md),
> [Authoring Command Protocol](authoring-command-protocol.md),
> [Task](task.md),
> [TaskBus](bus.md),
> [UI/backend communication](ui-backend-communication.md),
> [Tool Capability Layer](tool-capability-layer.md),
> [Context Manager](context-manager.md)

This document defines the core system answer to user natural-language input:
Plato separates contract revision from contract execution.

Every Product 1.1+ feature that handles user input, task structure, workspace
mutation, skills, MCP, recovery, inquiry, or context must state which loop it
belongs to and how it crosses the boundary.

---

## 1. Core Model

Plato has two primary loops:

```text
Contract Revision Loop
  understands user intent and revises the product contract

Contract Execution Loop
  executes an accepted contract and may change the workspace
```

The contract is the durable product agreement between the user and Plato. It is
not just an LLM prompt.

Contract facts include:

- Session intent and typed Session content;
- Plan and TaskNode structure;
- TaskNode title, intent, instructions, constraints, and acceptance criteria;
- guidance facts;
- ASK answers;
- confirmation responses;
- execution policy and selected context refs;
- recovery or follow-up requests.

Workspace files, shell commands, external side effects, provider payloads, raw
logs, and SQLite rows are not contract facts. They may become evidence or
diagnostics, but they are not the contract itself.

---

## 2. Contract Revision Loop

The Contract Revision Loop owns user-facing interpretation and product-state
revision before workspace execution.

Responsibilities:

- classify runtime input intent;
- resolve collaboration scope: Session, Plan, or TaskNode;
- answer read-only inquiries without mutating product or workspace state;
- record guidance as typed product state;
- create, patch, reorder, or delete Plan/TaskNode facts through commands;
- resolve ASK and confirmation lifecycles;
- create execution requests that can enter TaskBus;
- emit command results, events, and audit-friendly records for product-state
  changes.

It may use internal tools or skills for interpretation and product-state
commands:

```text
classify_intent
resolve_scope
answer_read_only_inquiry
record_guidance
patch_task_node
create_task_node
delete_task_node
resolve_ask
resolve_confirmation
create_execution_task
```

These tools are Router-owned capabilities, not unrestricted Agent tools. They
must preserve command boundaries when they mutate product state.

The Contract Revision Loop must not:

- write workspace files directly;
- run workspace commands directly;
- claim or complete TaskBus work directly;
- silently mutate Plan or TaskNode state on low-confidence interpretation;
- treat every user utterance as Collaborator input;
- use raw LLM prose as the source of truth for product-state changes.

---

## 3. Contract Execution Loop

The Contract Execution Loop owns execution of accepted work.

Responsibilities:

- claim executable PublishedTasks through TaskBus;
- assemble TaskExecutionContext through Context Manager;
- run Execution Agent loops;
- use workspace tools, precision file tools, shell adapters, or future MCP
  tools according to task policy;
- change workspace state only through approved execution tools;
- produce result, file evidence, audit facts, diagnostics, and TaskBus terminal
  outcomes.

The execution loop may change workspace state because it is operating under an
accepted contract. Its authority comes from TaskBus and the TaskNode/PublishedTask
contract, not from ordinary chat.

The Contract Execution Loop must not:

- directly edit Plan or TaskNode structure;
- silently reinterpret user goals;
- convert ambiguous runtime text into workspace mutation;
- bypass ASK or confirmation lifecycles;
- hide workspace changes behind Agent prose;
- treat tool observations as product-state commands.

If execution discovers that the contract is incomplete or wrong, it must cross
back to the Contract Revision Loop through one of these shapes:

```text
ASK
confirmation
recovery request
plan revision proposal
follow-up task proposal
failure with recovery actions
```

---

## 4. Interaction Router Boundary

The Interaction Router is the entrypoint into the Contract Revision Loop.

The Router may behave like a small agent/tool loop for interpretation, but its
tool set is restricted to read-only interpretation tools and command-backed
product-state tools.

Recommended routing shape:

```text
User input
  -> Router read-only interpretation tools
  -> one primary route decision
  -> optional policy-limited secondary effects
  -> command-backed product-state tool
      OR read-only inquiry answer
      OR TaskBus execution request
```

Default rule:

```text
one user input -> one primary side effect
```

Multiple read-only interpretation tools may run for the same input. Multiple
side effects are not allowed unless the Router explicitly decomposes them and
policy permits the combination.

Examples:

| User input | Primary route | Boundary |
|---|---|---|
| "What changed in this diff?" | Read-only inquiry answer | Revision loop, no mutation |
| "Use Chinese explanations for this session." | Record Session guidance | Revision loop command |
| "Make task 2 stricter." | Patch TaskNode | Revision loop command |
| "Add a step to test the installer." | Create TaskNode | Revision loop command |
| "Delete this step." | Delete TaskNode | Revision loop command, may require confirmation |
| "Change the README now." | Create or update executable Task | Revision loop -> TaskBus |
| "Approve that file write." | Resolve confirmation | Revision loop command -> execution may continue |

---

## 5. Collaborator Boundary

Collaborator is not the owner of all chat.

Collaborator is a contract authoring or revision capability. It may be invoked
by the Contract Revision Loop when plan synthesis, plan repair, or structured
proposal generation needs LLM reasoning.

Collaborator should not own:

- all runtime input;
- direct workspace mutation;
- ASK/confirmation command authority;
- generic read-only inquiry unless explicitly profiled for that mode;
- TaskBus execution.

This keeps Collaborator from growing into an unbounded assistant.

---

## 6. Command And Evidence Requirements

Every product-state mutation in the Contract Revision Loop must be command
shaped:

```text
intent -> command -> validation -> persisted facts -> event -> projection
```

Every workspace mutation in the Contract Execution Loop must be evidence
shaped:

```text
TaskBus claim -> tool/action -> observation -> evidence/result/audit -> terminal state
```

Every routed user input should also be activity shaped:

```text
user input -> interpreted effect -> affected scope -> linked refs -> activity record
```

Activity records are user-facing projections. They explain consequences without
exposing raw prompts, provider payloads, raw tool arguments, raw observations,
EventStream rows, SQLite rows, or diagnostic logs.

Implementation plans must not introduce hidden mutation paths. If a feature
changes product state or workspace state, its plan must identify:

1. owning loop;
2. command or TaskBus boundary;
3. state owner;
4. activity projection;
5. event/audit projection;
6. recovery behavior;
7. tests proving the boundary is not bypassed.

---

## 7. Feature Classification Rule

Future features must be classified before implementation:

| Feature type | Owning loop | Required boundary |
|---|---|---|
| Read-only question over files/diffs/results/audit | Contract Revision Loop | Inquiry profile, no mutation |
| User guidance | Contract Revision Loop | Guidance command and context fact |
| Plan or TaskNode edit | Contract Revision Loop | Plan/TaskNode mutation command |
| ASK answer | Contract Revision Loop | ASK resolve command |
| Confirmation response | Contract Revision Loop | Confirmation resolve command |
| Workspace file edit | Contract Execution Loop | TaskBus + execution tools |
| Shell command | Contract Execution Loop | TaskBus + workspace policy |
| Agent needs plan change | Cross-loop | Revision proposal / ASK / recovery request |
| Result packaging | Usually Execution or post-execution | Must not rewrite contract silently |
| Skills / MCP | Depends on side effect | Must declare revision vs execution authority |

If a feature seems to belong to both loops, split it into:

```text
contract revision slice
execution slice
projection / audit slice
```

---

## 8. Product 1.1 Direction

Product 1.1 should build these foundations in order:

1. accept Plan/TaskNode model and projection boundaries;
2. define Runtime Input Router contract;
3. implement read-only inquiry without mutation;
4. implement guidance as typed contract facts;
5. implement Plan/TaskNode patch/create/delete commands;
6. route workspace-changing requests into TaskBus execution;
7. extend skills/MCP only after each capability declares loop ownership.

This sequencing avoids turning the chat box, Collaborator, or a generic Agent
loop into an unrestricted mutation surface.
