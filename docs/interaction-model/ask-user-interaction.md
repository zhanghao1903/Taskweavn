# ASK User Interaction Model

> Status: draft interaction model
> Last Updated: 2026-06-02
> Scope: Main Page ASK Dock, active ASK card, multiple ASK queue, answer
> input behavior, and visible task/session signals.
> Related: [ASK Lifecycle Contract](../engineering/ask-lifecycle-contract.md),
> [Main Page Interaction Model](main-page.md),
> [External Calls Registry](external-calls.md).

## 1. Purpose

ASK is a high-signal user interaction. It appears when the Agent needs user
input before it can safely continue a task.

ASK must be visually and behaviorally distinct from ordinary messages:

- ordinary messages are history;
- ASK is an active required-response surface;
- the user should see which task is blocked and how to answer;
- the user should be able to answer with suggested options, free text, or both.

## 2. Source Of Truth

| Source | Responsibility |
|---|---|
| [ASK Lifecycle Contract](../engineering/ask-lifecycle-contract.md) | ASK object, answer object, lifecycle, events, API candidates, persistence and resume rules. |
| [Main Page Interaction Model](main-page.md) | Main Page component inventory and existing interaction conventions. |
| [External Calls Registry](external-calls.md) | API and navigation calls that the frontend may perform. |

This document defines frontend interaction behavior only. It must not redefine
ASK lifecycle enums or backend object semantics.

## 3. UX Decision

Default ASK placement is an ASK Dock above the sticky Context Input Bar.

```text
Main Page workspace
  TaskTree / MessageStream / DetailPanel

Sticky interaction layer
  AskDock
    ActiveAskCard
    AskQueueSummary
  ContextInputBar
```

ASK should not default to a modal because the user often needs workspace,
task, message, and detail context to answer correctly.

Modal usage is allowed only for:

- leaving the page with an unsent ASK answer draft;
- cancelling or discarding an ASK answer draft;
- dangerous actions where unresolved ASK state would be lost or hidden.

## 4. Component Model

| Component | Responsibility |
|---|---|
| `AskDock` | Sticky interaction region above Context Input Bar. Owns active ASK display and queue summary. |
| `ActiveAskCard` | Expanded answer surface for one ASK. Shows question, reason, options, free text input, and actions. |
| `AskQueueSummary` | Compact indicator for additional pending ASK objects. |
| `CollapsedAskItem` | One-line representation of a pending ASK not currently active. |
| `AskAnswerInput` | Free text input area scoped to the active ASK. |
| `AskOptionGroup` | Suggested options; supports single/multi/boolean modes from contract. |
| `TaskNeedsAnswerBadge` | TaskTree badge indicating that a task is waiting for user input. |
| `TopBarWaitingForUserStatus` | Session-level status chip when current execution is blocked on user input. |

## 5. Layout Rules

1. `AskDock` is visually stronger than MessageStream cards.
2. `AskDock` stays above the Context Input Bar, not inside MessageStream.
3. `AskDock` should not cover the main workspace content when there is enough
   vertical room; it pushes or reserves space in the sticky interaction layer.
4. The active card may be compact by default and expanded on focus.
5. Long `reason` text is truncated to a short summary with optional detail link
   when needed.
6. The input layer must remain usable at supported desktop width.
7. More than one pending ASK must not create stacked large cards by default.

## 6. Active ASK Card Content

Minimum visible content:

- label: `Needs your input`;
- question;
- short reason;
- task/session scope;
- suggested options if present;
- free text input if `allowFreeText=true`;
- submit action;
- later/defer action when allowed;
- unsupported file note: `Files are not supported in this version`;
- status and validation feedback.

Recommended answer layout:

```text
Needs your input
Question
Reason

[option] [option] [option] [option]

Add your own answer or constraints
[textarea]

Submit answer   Later
Files are not supported in this version.
```

## 7. Answer Rules

| User input | Allowed | Notes |
|---|---|---|
| Select option only | yes | Valid when at least one option is selected. |
| Free text only | yes, if `allowNoOptionWithText=true` | Critical because model options are suggestions, not full answer space. |
| Option plus free text | yes, if `allowFreeText=true` | Preferred for constrained-but-nuanced answers. |
| Empty submit | no | Submit disabled or validation shown. |
| File attachment | no for Product 1.0 | Show unsupported note; do not expose upload affordance. |

The UI must not force users to choose one of the suggested options when a free
text answer is allowed.

## 8. Multiple ASK Behavior

Product 1.0 default:

- show one expanded active ASK;
- show additional pending ASK objects in a compact queue summary;
- prefer the ASK for the currently selected or running task;
- keep other ASK objects collapsed unless the user explicitly switches.

Priority order:

1. ASK scoped to selected task.
2. Blocking ASK for current running task.
3. Oldest blocking session-level ASK.
4. Non-blocking or deferred ASK.

When multiple ASK objects exist:

```text
AskDock
  ActiveAskCard: current blocking task ASK
  AskQueueSummary: "2 more questions pending"
    CollapsedAskItem: "Choose deployment target"
    CollapsedAskItem: "Confirm content source"
```

Switching active ASK should preserve unsent local draft text per ASK id.

## 9. Main Page Signals

ASK must be visible in more than one place without duplicating answer controls.

| Surface | Required behavior |
|---|---|
| Top Bar | Show session-level `Waiting for User` or equivalent status when a blocking ASK is active. |
| TaskTree | Show `needs answer` badge on the blocked task. |
| MessageStream | Append passive history entry such as `Agent asked: ...`; do not embed the main answer form there. |
| DetailPanel | Show selected task context and that execution is waiting for user input. |
| ContextInputBar | Switch mode to `ask_answer` or show answer scope while ASK is active. |

## 10. Interaction Table

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `ASK-UI-001` | `target` | `ask.created` arrives or snapshot contains active ASK. | ASK status is `pending`. | Show `AskDock`, expand active ASK, show task/session waiting signal. | None immediately; optional snapshot refetch if event incomplete. | `ask.created`, snapshot refresh. | MessageStream also shows passive history entry. |
| `ASK-UI-002` | `target` | User selects suggested option. | Active ASK has options and allows selection. | Option visual state toggles according to answer type. | None until submit. | None. | Single choice allows one selected option. |
| `ASK-UI-003` | `target` | User types free text. | `allowFreeText=true`. | Local draft text updates; submit enabled if valid. | None until submit. | None. | Draft is frontend-local until submitted. |
| `ASK-UI-004` | `target` | User submits answer. | At least one option selected or non-empty text. | Submit enters pending; options/input disabled. | `EXT-C-010`. | `ask.answered`, `task.node.changed`, `message.appended`, snapshot refresh. | Command accepted is not final truth. |
| `ASK-UI-005` | `target` | Answer command rejected. | API returns error. | Keep active ASK open; show recoverable error; re-enable controls when safe. | Retry same answer with same idempotency key or new key according to command policy. | Refresh from API hint. | Do not mark ASK answered locally. |
| `ASK-UI-006` | `target` | User chooses Later / defer. | ASK permits defer. | Active ASK collapses or remains queued; task/session still shows waiting or deferred policy state. | `EXT-C-011`. | `ask.deferred`, snapshot refresh. | Defer is not an empty answer. |
| `ASK-UI-007` | `target` | User switches to another pending ASK. | More than one pending ASK. | Preserve current draft by ASK id; expand selected ASK. | None. | None. | Queue order remains deterministic. |
| `ASK-UI-008` | `target` | ASK is answered by current or another client. | Event or refetch returns `answered`. | Close active card if it matches; show answered history. | None. | `ask.answered`, snapshot refresh. | Restore workspace focus to task. |
| `ASK-UI-009` | `target` | ASK expires or is cancelled. | Event or refetch returns terminal ASK state. | Remove answer controls; show terminal reason/history. | None. | `ask.expired` / `ask.cancelled`. | Task state follows backend fact. |
| `ASK-UI-010` | `disabled` | User attempts file attachment. | Product 1.0. | No upload affordance; show unsupported note. | None. | None. | Contract reserves `attachmentsSupported=false`. |

## 11. UI States

| State | Required UI |
|---|---|
| No pending ASK | `AskDock` hidden; ContextInputBar uses normal mode. |
| Pending active ASK | `AskDock` visible with active card and answer controls. |
| Submitting answer | Controls disabled; pending indicator visible; no local answered fact yet. |
| Submit failed | Error text shown in card; answer draft preserved. |
| Multiple pending ASK | Active card plus compact queue summary. |
| Permission denied | Card visible read-only; submit disabled with reason. |
| Stale snapshot | Disable submit; show resync state; refetch snapshot. |
| Answered | Card closes or becomes compact history; task resumes by backend fact. |
| Expired/cancelled | Card shows terminal state and no answer controls. |

## 12. Accessibility And Keyboard

- ASK Dock receives programmatic focus when a blocking ASK appears, unless the
  user is actively typing elsewhere.
- `Submit answer` must be reachable by keyboard.
- Option chips must expose selected state.
- Free text area must have a visible label.
- Validation error must be announced near the submit control.
- Esc must not silently dismiss a blocking ASK.

## 13. Non-Goals

- ASK modal as default interaction.
- File upload or file selection.
- Full custom form builder.
- Editing historical ASK answers.
- Treating MessageStream as the primary ASK answer surface.
- Combining Confirmation and ASK into one generic component.

## 14. Acceptance Criteria

ASK interaction is acceptable for Product 1.0 when:

1. Active ASK is visually distinct from ordinary messages.
2. The answer surface is above the Context Input Bar.
3. Users can answer with options, free text, or both.
4. Users can answer with free text only when allowed.
5. File input is clearly unsupported.
6. Multiple pending ASK objects use one active card plus a compact queue.
7. TaskTree and TopBar both show waiting-for-user signals.
8. MessageStream records ASK history without owning the answer form.
9. Submit pending, failure, permission, stale, answered, expired, and cancelled
   states are represented.
10. No ASK answer is treated as final until backend facts confirm it.
