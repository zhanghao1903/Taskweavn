# Plato Main Page States

The Main Page prototype uses fourteen baseline states. They are not just visual samples:
they describe the user-visible lifecycle of a Workflow Session, from natural-language
input to TaskTree planning, ASK clarification, execution, confirmation, recovery,
and review.

The typed source of truth is `mainPageStateCatalog.ts`. The fixture data in
`fixtures.ts` must stay aligned with that catalog.

| State | Lifecycle | User situation | Page focus | Expected user action |
| --- | --- | --- | --- | --- |
| S1 Empty | empty | The user opened a Workflow but has not entered a goal. | Show the Workflow entry point and make natural-language input obvious. | Describe the goal they want Plato to plan. |
| S2 Authoring ASK | understanding | Plato needs structured answers before a TaskTree exists. | Replace the work area with batch ASK questions and keep the input disabled. | Select answers and submit them together. |
| S3 Draft Ready | planning | A draft TaskTree exists and needs review before publication. | Present the generated TaskTree as the main object of interaction. | Review the draft, select a TaskNode, or refine the plan. |
| S4 Task Selected | task_focus | The user selected a TaskNode while reviewing the TaskTree. | Narrow the interaction scope from the session to a single TaskNode. | Inspect the TaskNode or add guidance that only applies to it. |
| S5 Editing | task_focus | The user is actively refining a selected TaskNode. | Show that task-scoped input changes the TaskNode, not the whole plan. | Provide task-specific instructions or corrections. |
| S6 Running | execution | A published TaskNode is executing. | Keep the running Task visible while still allowing guidance. | Monitor progress or append guidance to the running TaskNode. |
| S7 Confirmation | execution | Execution is waiting for a user decision attached to a TaskNode. | Put the confirmation action in the detail panel without hiding context. | Confirm, revise, or skip the pending action. |
| S8 Completed | review | The session has produced a result card. | Shift from execution progress to result review. | Review the result or request follow-up packaging. |
| S9 File Changes | review | The user is reviewing file changes created by a TaskNode subtree. | Explain concrete workspace changes before acceptance or audit. | Inspect changed files or ask Plato to explain a change. |
| S10 Permission Denied | recovery | The session is read-only because the permission context disallows mutation. | Preserve context while clearly disabling mutation surfaces. | Return to a valid state or wait for permission context. |
| S11 Stale Snapshot | recovery | The local projection is stale and should not accept mutations. | Disable interaction controls and make resync the recovery path. | Refresh the snapshot before acting. |
| S12 Backend Busy | recovery | A command was accepted but the durable event has not arrived yet. | Keep current facts visible while preventing duplicate submit. | Wait for the event or retry after timeout policy. |
| S13 Command Failed | recovery | A recoverable command failure occurred before canonical facts changed. | Show the error and keep the TaskTree available for retry or revision. | Retry or revise the task instruction. |
| S14 Execution ASK | execution | A running TaskNode is waiting for user input. | Keep TaskTree context and place ASK actions in the detail panel. | Answer, defer, or cancel the ASK. |

## Surface Rules

- The TaskTree is the primary interaction object once it exists.
- The Session Message Stream remains a single stream, but the UI may project it by selected TaskNode.
- The Detail Panel is contextual: Workflow before planning, TaskNode during planning/execution, execution ASK and confirmation during gates, and Result/File Change during review.
- Authoring ASK uses the main work area and submits answers in a batch; execution ASK uses the detail panel and targets one concrete ASK.
- Local command pending state is temporary. `command.completed` and `command.failed` events invalidate the snapshot, and the refreshed MainPageSnapshot remains the durable convergence source.
- The bottom input always has an explicit scope. When a TaskNode is selected, input is task-scoped unless the current state deliberately pins a broader session/review scope.
- File Change Summary is recursive: parent TaskNodes may summarize all child TaskNode changes.

## Maintenance Rules

- Add new states to `mainPageStateCatalog.ts` first.
- Add matching fixture data in `fixtures.ts`.
- Keep `mockPlatoApi.test.ts` coverage green; it verifies that fixture states and catalog states do not drift.
