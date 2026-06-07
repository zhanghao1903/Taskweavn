# Plato Core Product Principles

> Status: product direction baseline
>
> Scope: product concept, user mental model, and interaction direction. This is
> not a screen layout spec and not a backend architecture spec.

## 1. Product Thesis

Plato is the user-facing Task-first intelligent workbench built on the TaskWeavn engine.

The user expresses an intention in natural language. The system turns that
intention into understandable, editable, confirmable, executable, and traceable
Tasks.

The core product object is not the chat transcript, not the file tree, and not
the Agent. The core product object is the Task.

A Task is a user-visible work contract between the user and Plato. Before
execution, it is a reviewed plan. During execution, it is delegated work under
user supervision. After execution, it is a result and evidence anchor. See
[Plato Task Semantics](plato-task-semantics.md) for the canonical Task product
meaning.

Session content is the typed collaboration record around Tasks and Plans, not
raw chat. It explains how intent became plan, how plan became execution, and
how execution produced outcome and evidence. See
[Plato Session Content Model](plato-session-content-model.md).

A Session may contain multiple Plan Cycles over time. Each Plan Cycle is one
round of authoring, execution, outcome review, and acceptance. See
[Plato Plan Cycle Semantics](plato-plan-cycle-semantics.md).

```text
Natural language goal
  -> Workflow
  -> Session
  -> Draft TaskTree / WorkTree
  -> Published Tasks
  -> Execution, confirmation, result, and audit
```

## 2. What Makes Plato Different

Traditional assistant products usually center one of three objects:

| Product type | Main object | User experience |
|---|---|---|
| Chat assistant | Conversation | User asks, assistant answers. |
| Coding agent | Files and terminal actions | User asks, agent edits and runs tools. |
| Workflow tool | Steps and forms | User configures a fixed process. |

Plato should center the Task:

| Plato | Main object | User experience |
|---|---|---|
| Task-first workbench | Workflow + TaskTree + TaskNode | User states a goal, reviews Tasks, confirms risky steps, tracks execution, and accepts results. |

The surprising part is that natural language becomes a structured, interactive,
traceable task system. The conservative part is that the user sees familiar
objects: tasks, status, options, results, and changes.

## 3. Design Direction

The product should feel understandable before it feels powerful.

The user should not need to know:

- which Agent is running,
- which provider is used,
- which Tool was called,
- how MessageBus routes events,
- how EventStream stores audit facts,
- what internal schema was used.

The user should understand:

- what they asked the system to do,
- what the system thinks the work is,
- what needs confirmation,
- what is running,
- what changed,
- what result was produced,
- where to continue.

## 4. Guardrail: Main Page Is A Control Plane

The Main Page is the user's control plane.

It should answer:

1. Where am I working?
2. What goal or workflow is active?
3. What Tasks exist?
4. Which Tasks need my attention?
5. What is running, completed, failed, or waiting?
6. What was produced?
7. What can I do next?

It should not try to explain every internal system detail.

Main Page information should be action-oriented:

- "Needs confirmation"
- "Waiting for your input"
- "Running"
- "Failed; can retry"
- "3 files changed"
- "Result ready"

## 5. Guardrail: Audit Page Is A Trust Plane

Audit Page is not the primary work surface. It exists to earn trust.

It should answer:

1. Why did the system do this?
2. Which Agent, Tool, provider, or system protocol participated?
3. What did the user confirm?
4. Which files changed and when?
5. Which risks were identified?
6. Can this process be traced or reconstructed?

Main Page and Audit Page may share facts, but their priorities differ.

| Page | Primary purpose | Information shape |
|---|---|---|
| Main Page | Control and progress | Simplified, actionable, user-facing |
| Audit Page | Trust and traceability | Complete, precise, replayable |

## 6. Workflow-First Entry

Users should enter the product through a Workflow, not through a raw Agent or
tool list.

Workflow is the user's semantic mode for a Session.

Examples:

- Create a Task plan.
- Execute a project.
- Research a question.
- Fix a bug.
- Package results into cards.
- Review and accept completed work.

Different Workflows may have different:

- input methods,
- confirmation policies,
- deliverables,
- default Agents,
- UI emphasis,
- audit requirements.

## 7. Draft Before Execution

For consequential work, the system should prefer draft before execution.

```text
User goal
  -> RawTask
  -> clarification if needed
  -> Draft TaskTree
  -> user review or workflow policy
  -> publish to TaskBus
  -> execution
```

This keeps ordinary users in control. They can see and adjust the plan before
the system makes meaningful changes.

Some low-risk Workflows may skip or compress this path, but the default product
direction should favor visibility before action.

## 8. TaskNode Is The Smallest Interaction Anchor

User confirmations, extra instructions, follow-up questions, result summaries,
file changes, and failure recovery should attach to TaskNodes whenever possible.

This prevents the user experience from dissolving into one long conversation.

Task-scoped interaction does not require a separate message system. The system
can store one Session message stream and project Task-scoped views by `task_id`.

## 9. Agent Routing Is Lightweight Orchestration

If users can define Agents, declare their capabilities, and assign a TaskNode to
a specific Agent, then users already have a practical form of multi-Agent
orchestration.

This should be treated as Task-routed Agent orchestration, not a full workflow
engine.

It can support:

- assigning a TaskNode to an Agent,
- expressing responsibility,
- organizing work through TaskTree hierarchy,
- letting advanced users shape Agent collaboration through Tasks.

It should not initially promise:

- arbitrary conditional branches,
- loops,
- dynamic runtime negotiation,
- complex compensation logic,
- a visual workflow programming language.

The product should keep this capability powerful but restrained.

## 10. User-Facing Complexity Budget

Plato will have real internal complexity. The product should spend that
complexity carefully.

Expose complexity when it gives the user control:

- Task status,
- confirmation options,
- editable Draft TaskTrees,
- file change summaries,
- selected Agent or capability for a Task.

Hide complexity when it only reflects implementation:

- raw tool parameters,
- provider retry internals,
- message-bus payloads,
- event serialization,
- low-level trace logs.

Advanced and audit views may expose more detail, but the Main Page should stay
focused on user intent, progress, and decisions.

## 11. Product Principle Summary

1. Task-first, not Chat-first.
2. Workflow-first entry, not Agent-first entry.
3. Draft before execution for consequential work.
4. Task is a visible work contract: Intent, Plan, Execution, and Evidence.
5. Session content is typed collaboration record, not raw chat.
6. A Session can continue through explicit Plan Cycles.
7. Runtime input has one user surface but distinct internal intent routing.
8. TaskNode is the smallest interaction anchor.
9. Main Page is a control plane.
10. Audit Page is a trust plane.
11. Agent routing is lightweight orchestration.
12. WorkTree carries power; Workflow hides initial complexity.
13. Ordinary users should see goals, tasks, status, choices, results, and changes.
14. Internal system concepts should surface only when they improve control or trust.
