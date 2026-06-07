# Workflow, Session, And Task UX Model

> Status: product direction baseline
> Last Updated: 2026-06-06
>
> Scope: user-facing objects and lifecycle semantics. This document avoids
> concrete page layout, visual hierarchy, and component-level design.

## 1. Core User-Facing Objects

Plato should keep a small set of objects stable in the user's mind.

| Object | User meaning | Product role |
|---|---|---|
| Project | A user-facing project or space. | Long-lived container for Workflows, Sessions, results, and shared context. It is not the default file execution boundary. |
| Workflow | A mode of work. | Defines input style, expected deliverable, interaction rhythm, and defaults. |
| Session | One run of a Workflow. | Holds the current collaboration, messages, Tasks, results, and isolated execution workspace. |
| Session Workspace | The file execution boundary for one Session. | Keeps file writes isolated so sessions do not default to concurrent writes into the same workspace. |
| RawTask | The user's original intention before structure. | Captures natural language and clarification history. |
| Plan Cycle | One round of authoring, execution, outcome review, and acceptance inside a Session. | Lets a Session continue after outcome review without silently overwriting previous Plans. |
| TaskTree / WorkTree | A structured plan or work graph. | Lets the user review, edit, publish, and track work. |
| TaskNode | One actionable unit in the tree. | Smallest anchor for status, confirmation, instruction, result, and file changes. |
| Agent / Capability | Who or what can do a Task. | Advanced routing and collaboration concept. |
| Message | Communication in a Session. | Process feedback, questions, answers, confirmations, and summaries. |
| Result | A produced answer, artifact, or outcome. | User-facing deliverable. |
| File Change Summary | What changed in the workspace. | Acceptance and review surface. |
| Audit Record | Trace of what happened and why. | Trust, replay, and debugging surface. |

## 2. Workflow As Session Mode

Workflow is not merely metadata. It is the user-facing mode of a Session.

```text
Workflow definition
  -> Session instance
  -> Workflow-specific inputs
  -> Workflow-specific TaskTree behavior
  -> Workflow-specific deliverable
```

Different Sessions may look and behave differently because their Workflows have
different goals.

Examples:

| Workflow | Primary input | Primary deliverable |
|---|---|---|
| Task Planning | Natural language goal, clarifying answers | Draft TaskTree / WorkTree |
| Project Execution | Approved TaskTree, natural language goal | Completed Tasks, artifacts, file changes |
| Research | Question, constraints, sources | Structured answer, result cards, citations |
| Bug Fix | Problem report, repo context | Patch, tests, explanation |
| Result Packaging | Existing result or session summary | UI-ready result cards |

## 2.1 Project Vs Session Workspace

`Project` and `Session Workspace` must stay separate in the user model.

```text
Project
  -> Workflow
      -> Session
          -> Session Workspace
```

The Project is the long-lived user container. It helps the user organize related
work, sessions, results, and shared context.

The Session Workspace is the execution boundary. It is where Agents read and
write files for one Session. This is intentionally session-scoped so the first
product version does not need to solve cross-session concurrent writes,
permission conflicts, or merge semantics.

If a Session produces something valuable, the user can later promote, export,
merge, or archive it into the Project through explicit actions. It should not
happen implicitly by having every Session write into the same shared workspace.

## 3. Authoring Workflow Vs Execution Workflow

The product should distinguish Task authoring from Task execution.

Product 1.0 is line-first. A Session may preserve both authoring evidence and
execution evidence for replay, but the user must see only one active domain at a
time.

### 3.1 Authoring Workflow

The goal is to produce a TaskTree.

```text
User input
  -> RawTask
  -> feasibility / clarification if needed
  -> Draft TaskTree
  -> user review and refinement
  -> ready to publish
```

The deliverable is a plan. The user may stop here, export the plan, modify it,
or publish it later.

### 3.2 Execution Workflow

The goal is to complete work.

```text
Input goal or approved TaskTree
  -> optional Draft TaskTree
  -> publish Tasks
  -> route Tasks
  -> execute
  -> confirm risky steps
  -> deliver result
```

The TaskTree may still be visible, but it is now a control surface for work in
progress rather than the final deliverable.

### 3.3 Single Active Domain Rule

Authoring Domain and Task Domain must not be active at the same time in the
Main Page control surface.

```text
No TaskTree yet
  -> RawTask / authoring ASK can be active

TaskTree exists
  -> plan or TaskNode is active
  -> RawTask / authoring ASK becomes provenance, not the active workflow
```

This rule exists because users operate Plato through one current object. If a
Session shows an unanswered authoring ASK and an executable TaskTree at the same
time, the user cannot know whether they are correcting the original intent,
editing the plan, or affecting running work.

Product behavior:

- before a TaskTree exists, the input area may target the Session RawTask or an
  authoring ASK;
- after a TaskTree exists, the input area targets the whole plan or a selected
  TaskNode;
- answering an old authoring ASK after a TaskTree exists must not silently
  generate a new RawTask or replace the existing TaskTree;
- replanning is an explicit action such as `Revise plan`, `Start new draft`, or
  `Apply answer as plan guidance`;
- legacy/dirty Sessions that contain both active authoring facts and TaskTree
  facts should project to the TaskTree view and expose stale authoring facts
  only as history, audit, or recovery notes.

## 4. Workflow Lifecycle

```text
Available
  -> Selected
  -> Configured
  -> Running as Session
  -> Completed / Cancelled
```

User-facing meaning:

- `Available`: User can choose this kind of work.
- `Selected`: User has entered the mode.
- `Configured`: Required options, defaults, or constraints are set.
- `Running as Session`: The Workflow has an active Session instance.
- `Completed`: The Workflow produced its deliverable.
- `Cancelled`: The user or system stopped the Workflow before completion.

## 5. Session Lifecycle

```text
Created
  -> Understanding
  -> Planning
  -> Reviewing
  -> Executing
  -> Waiting for User
  -> Completed / Failed / Paused
```

User-facing meaning:

- `Created`: A new collaboration exists.
- `Understanding`: The system is interpreting the user's goal.
- `Planning`: The system is building or revising a TaskTree.
- `Reviewing`: The user can inspect and adjust the plan.
- `Executing`: Published Tasks are being worked on.
- `Waiting for User`: The system needs confirmation, input, or correction.
- `Completed`: The Session produced its intended deliverable.
- `Failed`: The Session cannot continue without recovery.
- `Paused`: The user intentionally stopped progress for now.

## 5.1 Plan Cycle Lifecycle

Plan Cycle is the lifecycle unit for one round of work inside a Session.

```text
Authoring
  -> Plan Ready
  -> Executing
  -> Outcome Review
  -> Accepted / Closed / Follow-up Requested / Recovery
```

User-facing meaning:

- `Authoring`: The user and Collaborator are shaping a Plan.
- `Plan Ready`: The Plan is reviewable and can become executable work.
- `Executing`: Published Tasks are being worked on.
- `Outcome Review`: Plan execution completed enough for result, file, warning,
  failure, and audit review.
- `Accepted`: The user accepts the outcome.
- `Closed`: The Session stops after this Plan Cycle.
- `Follow-up Requested`: The user wants related additional work in the same
  Session.
- `Recovery`: The user wants to retry, revise, or resolve failed work.

A Session may contain multiple Plan Cycles over time, but it should expose at
most one active Plan at a time. Previous Plans remain history, baseline, and
evidence; they should not be silently overwritten.

## 6. RawTask Lifecycle

```text
Captured
  -> Feasibility Checking
  -> Clarifying
  -> Converted to Draft TaskTree
  -> Accepted / Abandoned / Superseded
```

RawTask is important because ordinary natural language is exploratory. The
system should not treat every user sentence as an immediately executable Task.

RawTask can carry ASK actions, clarification turns, feasibility notes, and
conversion lineage before a Draft TaskTree exists.

Once a Draft TaskTree exists for the same Session path, the RawTask is no longer
the active control object. Its unanswered asks become stale unless the system
explicitly starts a replanning/revision flow.

User-facing recovery for stale RawTask asks:

| Situation | Product behavior |
|---|---|
| User answers an old RawTask ASK after a TaskTree exists | Do not generate a new RawTask automatically. Show that the answer is stale or offer to apply it as plan guidance. |
| RawTask and TaskTree both exist because of old fixture/runtime behavior | Prefer the TaskTree as the active object; keep RawTask evidence available in history/audit. |
| User wants to restart authoring from that answer | Use an explicit `Revise plan` or `Start new draft` action with visible consequences. |

## 7. TaskTree / WorkTree Lifecycle

```text
Generated Draft
  -> User Editing
  -> Ready to Publish
  -> Published
  -> Executing
  -> Completed / Partially Completed
```

User-facing meaning:

- `Generated Draft`: The system proposes a structured plan.
- `User Editing`: The user or Collaborator refines the tree.
- `Ready to Publish`: The tree is valid enough to enter execution.
- `Published`: The tree has become normal Tasks on the TaskBus.
- `Executing`: Some TaskNodes are being worked on.
- `Completed`: All relevant TaskNodes are done.
- `Partially Completed`: Some work finished, but failures or skips remain.

## 8. TaskNode Lifecycle

```text
Proposed
  -> Needs Clarification
  -> Ready
  -> Queued
  -> Running
  -> Waiting for Confirmation
  -> Done / Failed / Skipped / Cancelled
```

User-facing rules:

- Proposed TaskNodes can be edited freely.
- TaskNodes needing clarification should invite user correction, not execution.
- Ready TaskNodes are publishable.
- Queued TaskNodes are waiting for scheduling or routing.
- Running TaskNodes can accept additional information but should not be heavily
  restructured without explicit recovery behavior.
- Waiting TaskNodes should present clear choices or a focused input request.
- Done TaskNodes are read-oriented: result, summary, file changes, and audit.
- Failed TaskNodes should offer retry, modify-and-retry, skip, or inspect.

## 9. Agent Routing Lifecycle

```text
Routing Agent Available
  -> TaskNode Awaiting Assignment
  -> Assigned to Execution Agent
  -> Working
  -> Reported Result
```

Agent routing should be understandable as responsibility assignment, not as a
workflow-programming surface:

```text
This TaskNode is handled by this Agent or capability.
```

This is enough for a first version of flexible multi-Agent orchestration.

It should remain Task-routed. The user should not need to operate a full
workflow engine to gain meaningful control over Agent assignment.

Product 1.0 should treat routing as mostly system-internal. A default Routing
Agent can decide which Execution Agent should receive a TaskNode and submit an
assignment command. This assignment should be traceable, but ordinary users
should not be forced to confirm it because assignment changes system
responsibility, not the user's external world.

High-impact confirmation belongs closer to execution:

```text
Routing Agent assigns TaskNode
  -> Execution Agent prepares high-privilege action
  -> user confirmation if needed
  -> tool/action executes
```

Advanced users may later configure or replace the Routing Agent.

### 9.1 Interruption UX

Stopping a running TaskNode is cooperative by default.

```text
User clicks Stop
  -> Main Page shows "Stopping..."
  -> system asks the running Agent to stop at the next safe point
  -> Agent acknowledges stopped / failed / completed
```

The UI should not promise immediate cancellation. Safe points belong to the
Agent/runtime because only the executor knows whether the current action can be
stopped without leaving partial writes, orphan processes, or inconsistent
external state.

For Product 1.0:

- queued / unclaimed TaskNodes may stop quickly;
- running TaskNodes enter a visible stopping affordance until acknowledged;
- "pause/resume" is not part of the first product contract;
- hard cancellation is best-effort and runtime-specific.

## 10. Message Model In UX

The system may have one Session message stream underneath.

The UX can project different views:

- Session-wide messages: all important communication in chronological order.
- Task-scoped messages: messages filtered by selected TaskNode.
- Confirmation messages: actionable messages requiring a decision.
- Result messages: user-facing deliverables or summaries.

This keeps the backend simple while preserving the user's mental model:

```text
The Session has a conversation.
Each Task can show the parts relevant to it.
```

## 11. Result Lifecycle

```text
Generated
  -> Packaged
  -> Reviewed
  -> Accepted / Needs Follow-up
```

The result may be plain text, files, structured cards, summaries, reports, or
other artifacts. The product should increasingly prefer structured presentation
when it improves user comprehension.

Result packaging can itself be modeled as a Task.

## 12. File Change Summary Lifecycle

```text
No Changes
  -> Changes Proposed / Made
  -> Summarized
  -> Reviewed
  -> Accepted / Needs Follow-up
```

Parent TaskNodes should aggregate child file changes. Child TaskNodes own their
direct changes; parent nodes present rolled-up summaries.

This lets users review at different levels:

- one TaskNode,
- one branch of work,
- the whole TaskTree,
- the whole Session.

## 13. Control Plane Vs Trust Plane

Main Page and Audit Page should share facts but not compete.

| Concern | Main Page | Audit Page |
|---|---|---|
| Task status | Primary | Supporting evidence |
| User confirmation | Actionable | Historical record |
| File changes | Summary and acceptance | Full trace |
| Agent and Tool use | Simplified responsibility | Precise call chain |
| Risk | User-readable warning | Detailed assessment |
| Logs and events | Hidden by default | Inspectable |

## 14. Open Product Questions

These questions are intentionally left open for future design work:

1. How many Workflow templates should be visible in the first product version?
2. When should the system auto-select a Workflow versus asking the user?
3. Should Authoring Workflow and Execution Workflow appear as two explicit
   steps, or as one guided experience with a visible transition?
4. How much Routing Agent configuration should be exposed to advanced users?
5. What is the default recovery path when a running TaskNode receives new user
   instructions?
6. When should Product 1.0 show routing notices to the user versus keeping them
   in Audit / diagnostics?
7. When should result packaging run automatically versus as an explicit Task?

The stable baseline is not the answer to every question. The stable baseline is
the object model: Workflow, Session, TaskTree, TaskNode, Result, and Audit.
