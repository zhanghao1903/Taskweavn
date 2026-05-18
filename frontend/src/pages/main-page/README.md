# Plato Main Page States

The Main Page prototype uses nine baseline states. They are not just visual samples:
they describe the user-visible lifecycle of a Workflow Session, from natural-language
input to TaskTree planning, execution, confirmation, and review.

The typed source of truth is `mainPageStateCatalog.ts`. The fixture data in
`fixtures.ts` must stay aligned with that catalog.

| State | Lifecycle | User situation | Page focus | Expected user action |
| --- | --- | --- | --- | --- |
| S1 Empty | empty | The user opened a Workflow but has not entered a goal. | Show the Workflow entry point and make natural-language input obvious. | Describe the goal they want Plato to plan. |
| S2 Understanding | understanding | Plato is interpreting the user's goal before a TaskTree exists. | Make progress legible without pretending that execution has started. | Add constraints, examples, or missing context. |
| S3 Draft Ready | planning | A draft TaskTree exists and needs review before publication. | Present the generated TaskTree as the main object of interaction. | Review the draft, select a TaskNode, or refine the plan. |
| S4 Task Selected | task_focus | The user selected a TaskNode while reviewing the TaskTree. | Narrow the interaction scope from the session to a single TaskNode. | Inspect the TaskNode or add guidance that only applies to it. |
| S5 Editing | task_focus | The user is actively refining a selected TaskNode. | Show that task-scoped input changes the TaskNode, not the whole plan. | Provide task-specific instructions or corrections. |
| S6 Running | execution | A published TaskNode is executing. | Keep the running Task visible while still allowing guidance. | Monitor progress or append guidance to the running TaskNode. |
| S7 Confirmation | execution | Execution is waiting for a user decision attached to a TaskNode. | Put the confirmation action in the detail panel without hiding context. | Confirm, revise, or skip the pending action. |
| S8 Completed | review | The session has produced a result card. | Shift from execution progress to result review. | Review the result or request follow-up packaging. |
| S9 File Changes | review | The user is reviewing file changes created by a TaskNode subtree. | Explain concrete workspace changes before acceptance or audit. | Inspect changed files or ask Plato to explain a change. |

## Surface Rules

- The TaskTree is the primary interaction object once it exists.
- The Session Message Stream remains a single stream, but the UI may project it by selected TaskNode.
- The Detail Panel is contextual: Workflow before planning, TaskNode during planning/execution, confirmation during gates, and Result/File Change during review.
- The bottom input always has an explicit scope. When a TaskNode is selected, input is task-scoped unless the current state deliberately pins a broader session/review scope.
- File Change Summary is recursive: parent TaskNodes may summarize all child TaskNode changes.

## Maintenance Rules

- Add new states to `mainPageStateCatalog.ts` first.
- Add matching fixture data in `fixtures.ts`.
- Keep `mockPlatoApi.test.ts` coverage green; it verifies that fixture states and catalog states do not drift.
