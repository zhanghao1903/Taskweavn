# Plato Task Semantics

> Status: product semantic baseline
>
> Last Updated: 2026-06-09
>
> Scope: user-facing meaning of Plan-owned TaskNodes, Plan progress, and Task
> lifecycle. This is not a backend status model, not a UI layout spec, and not
> an implementation plan.
>
> Related:
> [Core Product Principles](core-product-principles.md),
> [Workflow, Session, And Task UX Model](workflow-session-task-ux-model.md),
> [Plato Session Content Model](plato-session-content-model.md),
> [Plato Plan Cycle Semantics](plato-plan-cycle-semantics.md),
> [Canonical Status Model](canonical-status-model.md),
> [Plan / TaskNode Model Technical Design](../plans/feature/plan-tasknode-model-technical-design.zh-CN.md)

## 1. Core Definition

A Task is a user-visible work contract between the user and Plato.

Before execution, it is a reviewed plan. During execution, it is delegated work
under user supervision. After execution, it is a result and evidence anchor.

This definition is the core product meaning of Task. It is more important than
the internal status names used by TaskBus, projection code, or API transport.

In Product 1.1 language, Collaborator should not be understood as producing a
loose `TaskTree` list. Collaborator produces a `Plan`, and the Plan owns a flat
ordered `TaskNode` list.

```text
Session
  -> Plan
      -> TaskNode list
```

Every TaskNode is a work contract. The UI may simply call it a Task, but the
contract/model name can remain `TaskNode`. Product 1.1 does not require
parent/child task hierarchy, `node_type`, `execution_role`, or
`children_policy`. What a TaskNode does is expressed through intent,
instructions, constraints, capabilities, and acceptance criteria. The execution
Agent decides how to satisfy that contract within runtime policy and
audit/confirmation gates.

## 2. What A Task Is Not

A Task is not:

- a chat message;
- a raw LLM output;
- a low-level tool call;
- a generic todo item;
- an implementation log row;
- an internal Agent thought.

A Task may produce messages, tool calls, logs, and evidence, but those are not
the Task itself.

## 3. Natural User Semantic Layers

The user-facing Task meaning should be fixed around four layers:

```text
Intent -> Plan -> Execution -> Evidence
```

These layers should be visible in the UI even when the user does not know their
formal names.

| Layer | User question | Product meaning | Example |
|---|---|---|---|
| Intent | Why do this? | The goal or sub-goal the Task exists to satisfy. | Implement ASK Dock frontend. |
| Plan | How will Plato do it? | The proposed work before side effects. This is the core of an unexecuted Task. | Add ASK cards, answer input, submitting state, and error state. |
| Execution | What is Plato doing now? | Delegated active work under user supervision. This is the core of a running Task. | Updating the Main Page detail panel. |
| Evidence | What happened? | The result, changes, and proof after execution. This is the core of a completed or failed Task. | 3 files changed, tests passed, audit warning: none. |

## 4. TaskNode Model

Product 1.1 should use a two-level model:

```text
Plan
  -> TaskNode 1
  -> TaskNode 2
  -> TaskNode 3
```

A TaskNode is a concrete user-visible work contract inside a Plan. It may
involve implementation, research, validation, summary, documentation, or
integration, but the system should not encode those as rigid execution roles in
the Task model.

Recommended TaskNode facts:

| Fact | Meaning |
|---|---|
| `task_index` | Stable user-facing index inside one Plan, such as `1`, `2`, `3`. |
| `title` | Short user-readable work label. |
| `intent` | Why this line exists. |
| `summary` | Compact description shown in the UI. |
| `instructions` | Guidance passed to the execution Agent. |
| `constraints` | What must be preserved or avoided. |
| `acceptance_criteria` | How the result should be judged. |
| `depends_on` | Minimal dependency hints between TaskNodes. |
| `required_capability` | Optional capability hint, not a hard Agent role. |

UI projection rule:

- Task list cards show `title` and short `summary` only.
- Full `intent`, `instructions`, and `acceptance_criteria` belong in the
  selected Task detail panel.
- Collaborator and Gateway code must not concatenate `Summary:`,
  `Instructions:`, or `Acceptance criteria:` marker text into `intent`.
  Legacy marker text may be split during projection for compatibility, but new
  Plan output should remain structured.

### 4.1 Why Not Parent/Child In The First Version

Parent/child task hierarchy can express grouping, rollup, inherited constraints,
and coordination, but it also adds substantial complexity:

- LLM output must reliably distinguish group nodes from executable nodes;
- UI must teach users tree semantics and parent-level selection;
- TaskBus must decide whether parents execute, wait, summarize, or validate;
- Audit and file summaries would need hierarchy-aware attribution if nested
  TaskNodes are introduced later;
- Context Manager must choose between Plan, parent, and child scopes.

The first version should avoid that complexity until real usage proves the
benefit is worth the extra model surface.

### 4.2 Execution Agent Discretion

TaskNode should define the work contract, not a system-owned execution role.

The execution Agent can decide whether satisfying a TaskNode requires:

- modifying workspace files;
- reading and analyzing existing files;
- writing documentation;
- validating previous work;
- summarizing results;
- asking the user for missing information.

Those decisions should be constrained by runtime policy, available tools,
audit, confirmation, and the TaskNode's acceptance criteria rather than by a
large `execution_role` enum.

### 4.3 Plan-Level Summary And Rollup

If the product needs summary, validation, integration, file rollup, or context
compression after all TaskNodes finish, that should be modeled as Plan
finalization.

Plan finalization is not a hidden parent TaskNode in Product 1.1. It is a
Plan-level lifecycle phase that can later be backed by Collaborator, reviewer,
or context-management agents.

### 4.4 LLM Output Requirements

Collaborator output should produce a Plan proposal with a flat TaskNode list.
It should not ask the model to choose parent/child semantics, `node_type`,
`execution_role`, or `children_policy` in the first version.

Raw LLM output should not decide product behavior implicitly. The product model
should validate and normalize LLM output into explicit Plan and TaskNode facts
before the UI or runtime acts on it.

## 5. Unexecuted Task Semantics

An unexecuted Task means:

```text
Plato proposes to do this, but has not started yet.
```

User-facing meaning:

- the system has interpreted the user's goal;
- the work is still reviewable;
- the user can edit, split, delete, reorder, or approve it;
- the workspace has not been changed by this Task yet;
- control still belongs primarily to the user.

The UI should make this feel like a proposed work contract, not an execution
log.

Recommended surface language:

- `Planned`
- `Ready to run`
- `Review before execution`
- `Not started`
- `This step has not changed your workspace yet.`

Recommended actions:

- edit;
- split;
- reorder;
- delete;
- run;
- approve;
- regenerate.

## 6. Running Task Semantics

A running Task means:

```text
Plato is acting on this work contract now.
```

User-facing meaning:

- the Agent has accepted responsibility for this Task;
- the Task may read files, call tools, or modify the workspace;
- the user can supervise, guide, stop, inspect, or answer;
- the Task may pause for ASK or confirmation;
- the Task must eventually produce a result, failure, file summary, or audit
  evidence.

The UI should make this feel like delegated work under supervision, not merely
a spinner.

Recommended surface language:

- `Working`
- `Running`
- `Waiting for your answer`
- `Needs confirmation`
- `Stopping`
- `Retrying`
- `Last action: read src/App.tsx`
- `Changed 2 files`

Recommended actions:

- view activity;
- add guidance;
- stop;
- answer ASK;
- resolve confirmation;
- inspect file or diff when available.

## 7. Completed Or Failed Task Semantics

A terminal Task means:

```text
This work contract reached an outcome.
```

Done Task user-facing meaning:

- the work produced a result;
- file changes, if any, are reviewable;
- audit evidence is available or explicitly unavailable;
- the user can accept, inspect, ask about, or continue from the result.

Failed Task user-facing meaning:

- the work stopped before satisfying the contract;
- the reason should be visible;
- retry, revise, skip, or inspect should be available when applicable;
- evidence should explain whether anything changed before failure.

Recommended actions:

- view result;
- view files;
- view audit;
- ask about this;
- retry;
- revise and retry;
- skip when safe.

## 8. UI Implications

The UI should express Task semantics through layout, copy, state grouping, and
available actions.

### 8.1 Detail Panel

Task Detail should change its primary framing by lifecycle.

| Lifecycle | Detail title idea | Supporting copy idea |
|---|---|---|
| Proposed / Ready | Planned work | Review this step before Plato runs it. |
| Running | Active work | Plato is working on this step. You can guide or stop it. |
| Waiting for ASK | Needs your input | Plato cannot continue until you answer this. |
| Waiting for confirmation | Needs authorization | Plato knows the action but needs permission before proceeding. |
| Done | Result | This step is complete. Review the outcome and evidence. |
| Failed | Recoverable failure | This step stopped before completion. You can retry or revise it. |

### 8.2 Plan & Progress

Plan & Progress should not feel like a plain checklist. It is the visible
structure of the current Plan and its TaskNode contracts.

Raw Task authoring and published Plan views should both show the same TaskNode
set. If authoring shows one structure while published execution shows another,
users cannot review the actual work contract before approval.

The Plan & Progress area should make lifecycle visible:

- planned work is reviewable;
- running work is supervised;
- completed work is evidence-bearing;
- failed work is recoverable when possible.

Possible visual grouping:

- Planned;
- In progress;
- Completed;
- Needs recovery.

Each TaskNode should expose lifecycle meaning through label, tone, and actions.
Selecting the Plan should show plan-level intent, progress, summary, and
available Plan actions. Selecting a TaskNode should show concrete execution
detail.

### 8.3 Messages And Activity

Messages should explain what happened around a Task, but they should not become
the Task authority.

Task authority comes from:

- Task lifecycle facts;
- ASK facts;
- confirmation facts;
- result summaries;
- file summaries;
- audit records.

Activity Stream is a user-readable projection of these facts. It is not raw LLM
output and not the canonical source of Task state.

### 8.4 Plan Cycle Context

Within a Plan Cycle, Task meaning changes by phase:

- before execution, Tasks express the accepted or reviewable Plan;
- during execution, Tasks are the delegated work control surface;
- after execution, Tasks become the result map and evidence index;
- during follow-up authoring, prior Tasks become context for the next Plan, not
  mutable chat history.

Task semantics should therefore remain stable even when a Session continues
through multiple Plan Cycles.

## 9. Relationship To Input Modes

Task semantics clarify the meaning of user input:

| Input mode | Relationship to Task |
|---|---|
| Guidance | Adds constraints or preferences to delegated work without directly rewriting the work contract. |
| Command | Changes the work contract or controls delegated execution. |
| Question | Asks for understanding without changing the work contract. |
| ASK answer | Supplies missing information needed to continue execution. |
| Confirmation response | Authorizes or rejects a known side-effecting action. |

This distinction should be internal first. The primary UI can remain one input
surface, but the system must preserve the semantic difference after routing.

## 10. Relationship To Audit And Diff

Evidence is the post-execution layer of Task.

For Product 1.0, evidence may be:

- result summary;
- error summary;
- file change summary;
- audit entry;
- process message.

For Product 1.1, evidence should become stronger through:

- git status;
- file diff;
- changed line ranges;
- file viewer links;
- audit records tied to concrete workspace changes.

The user should be able to move naturally from:

```text
Task -> Result -> File changes -> Diff -> Audit
```

without learning internal EventStream or tool schemas.

## 11. Product Invariant

Every important Task view should answer four questions:

1. Intent: why does this Task exist?
2. Plan: how does Plato intend to do it?
3. Execution: what is happening now, if anything?
4. Evidence: what happened and how can the user verify it?

If a Task view cannot answer these questions, it is likely exposing internal
status without enough product semantics.

## 12. Acceptance Criteria For Future UI Work

Future Main Page, Audit Page, and Task Detail work should satisfy:

- unexecuted Tasks clearly feel reviewable and safe to edit;
- running Tasks clearly feel delegated and supervisable;
- waiting Tasks clearly show what user input or authorization is needed;
- completed Tasks clearly expose result and evidence;
- failed Tasks clearly expose recovery options and failure evidence;
- messages do not replace Task lifecycle facts;
- raw LLM output is not treated as the primary user-facing Task representation;
- Task copy uses user semantic language before internal status language.
