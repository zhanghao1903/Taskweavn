# Workflow, Session, And Task UX Model

> Status: product direction baseline
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

## 6. RawTask Lifecycle

```text
Captured
  -> Feasibility Checking
  -> Clarifying
  -> Converted to Draft TaskTree
  -> Accepted / Abandoned
```

RawTask is important because ordinary natural language is exploratory. The
system should not treat every user sentence as an immediately executable Task.

RawTask can carry ASK actions, clarification turns, feasibility notes, and
conversion lineage before a Draft TaskTree exists.

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
Agent Defined
  -> Capability Available
  -> Assigned to TaskNode
  -> Working
  -> Reported Result
```

Agent routing should be understandable as responsibility assignment:

```text
This TaskNode is handled by this Agent or capability.
```

This is enough for a first version of flexible multi-Agent orchestration.

It should remain Task-routed. The user should not need to operate a full
workflow engine to gain meaningful control over Agent assignment.

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
4. How much Agent routing should be exposed to ordinary users?
5. What is the default recovery path when a running TaskNode receives new user
   instructions?
6. When should result packaging run automatically versus as an explicit Task?

The stable baseline is not the answer to every question. The stable baseline is
the object model: Workflow, Session, TaskTree, TaskNode, Result, and Audit.
