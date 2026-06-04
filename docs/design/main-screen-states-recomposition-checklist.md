# Main Screen States Recomposition Checklist

> Status: draft checklist for Main Page screen-state recomposition
> Last Updated: 2026-06-04
> Scope: State-by-state visibility, action, copy, and QA rules for simplifying
> the current Plato Main Page screen states.
> Non-goals: no frontend code, no Figma write, no API contract change, no old
> Figma frame migration.

## 1. Purpose

This checklist operationalizes
`docs/design/main-screen-states-visual-simplification-brief.md`.

The simplification brief defines the visual direction. This checklist defines
what each current Main Page state should show, demote, hide, and verify before
future Figma or frontend work is accepted.

This document uses the current frontend mock catalog names from
`frontend/src/pages/main-page/mainPageStateCatalog.ts`. Those names are review
targets for the current app surface; canonical state dimensions still come
from `docs/ux/screen-state-spec.md`.

## 2. Surface Priority Vocabulary

Use these terms consistently during review:

| Term | Meaning |
|---|---|
| Primary | The user's eye should land here first. |
| Secondary | Visible, useful, but clearly subordinate. |
| Quiet | Present as metadata, link, badge, or compact hint. |
| Hidden | Not shown in the default state; available only through detail, audit, or expansion. |
| Removed | Should not appear because it repeats or confuses the state. |

Default Main Page priority:

```text
TaskTree / selected TaskNode
  -> current required action
  -> context-aware input
  -> result/file review
  -> message evidence
  -> audit/log trust detail
```

## 3. Global Recomposition Rules

Apply these rules to every screen state:

- TopBar shows route context and at most two state chips.
- State picker is hidden in production screen states.
- TaskTree keeps the central visual role whenever a task tree exists.
- MessageStream is evidence, not the primary workflow explanation.
- DetailPanel is the only place for the next decision/action.
- InputDock copy must match the actual input mode.
- Empty, loading, stale, error, and permission copy should appear once per
  state, not once per surface.
- Raw ids, backend terms, and audit evidence details stay hidden by default.
- Audit is visible as a trust entry, not a default detail dump.

## 4. State Recomposition Matrix

### S1 Empty

| Item | Decision |
|---|---|
| User question | What can I start here? |
| Primary surface | InputDock and empty TaskTree |
| Secondary surface | Sidebar selected workflow/session context |
| Quiet surface | TopBar route context, weak Audit entry if available |
| Hidden by default | MessageStream panel details, generic DetailPanel state note, workspace isolation explanation |
| Primary action | Enter the first goal |
| Copy target | One sentence: describe what Plato will turn into tasks |

Review checks:

- The page does not look like a landing page.
- There is only one empty-state explanation.
- The input placeholder is the clearest object on the screen after the
  TaskTree empty state.

### S2 Understanding

| Item | Decision |
|---|---|
| User question | Is Plato turning my goal into a task structure? |
| Primary surface | Planning progress in the TaskTree/workspace region |
| Secondary surface | One recent session update |
| Quiet surface | InputDock for additional constraints |
| Hidden by default | Full message history, technical progress details, audit |
| Primary action | Wait or add missing constraints |
| Copy target | "Plato is organizing your goal into tasks." |

Review checks:

- The UI does not imply execution has started.
- Progress is visible without "AI thinking" theatrics.
- There is one progress explanation, not a progress banner plus a repeated
  DetailPanel note plus a repeated message.

### S3 Draft Ready

| Item | Decision |
|---|---|
| User question | Does this plan look right before execution? |
| Primary surface | TaskTree |
| Secondary surface | Publish action and selected/draft status |
| Quiet surface | Message evidence that the draft was generated |
| Hidden by default | Duplicate draft-ready note in DetailPanel |
| Primary action | Review a TaskNode or publish the tree |
| Copy target | "Review the task structure before execution." |

Review checks:

- TaskTree is larger and visually stronger than MessageStream.
- Publish is discoverable but not alarmingly dominant.
- Draft and published states are visually distinct.

### S4 Task Selected

| Item | Decision |
|---|---|
| User question | What does this selected task mean and what can I do to it? |
| Primary surface | Selected TaskNode and DetailPanel title/body |
| Secondary surface | InputDock task scope |
| Quiet surface | Related updates |
| Hidden by default | Session-wide stream count unless it changes meaning |
| Primary action | Inspect or add task-specific guidance |
| Copy target | "Applies to: selected task / [task title]" |

Review checks:

- TaskTree selection, DetailPanel title, and InputDock scope all name the same
  task.
- The selected state is visible without relying on color alone.
- The user cannot confuse task-scoped input with session-wide input.

### S5 Editing

| Item | Decision |
|---|---|
| User question | Am I editing this task or the whole plan? |
| Primary surface | Task-scoped input/edit affordance |
| Secondary surface | Selected TaskNode |
| Quiet surface | Related messages |
| Hidden by default | Whole-session guidance copy |
| Primary action | Submit task-specific change or cancel local edit |
| Copy target | "This changes only [task title]." |

Review checks:

- Edit mode is structurally different from simple selection.
- Save/cancel or submit behavior is clear.
- The UI does not imply execution is happening while editing a draft.

### S6 Running

| Item | Decision |
|---|---|
| User question | What is running, and can I safely intervene? |
| Primary surface | Running TaskNode in TaskTree |
| Secondary surface | Live related updates |
| Quiet surface | Stop/guidance controls only when permitted |
| Hidden by default | Completed task result details until execution finishes |
| Primary action | Monitor, append guidance, or stop if allowed |
| Copy target | "Running: [task title]" |

Review checks:

- Running status is visible on the task itself.
- Message updates support the running task but do not replace the TaskTree.
- Stop is visible only where it is actionable and scoped.

### S7 Confirmation

| Item | Decision |
|---|---|
| User question | What exactly am I approving or changing? |
| Primary surface | DetailPanel confirmation card |
| Secondary surface | Waiting TaskNode in TaskTree |
| Quiet surface | Related message evidence |
| Hidden by default | Non-actionable messages and audit details |
| Primary action | Confirm the recommended action |
| Copy target | Action + impact + choices, attached to one task |

Review checks:

- One primary confirmation button is visually dominant.
- Revise/skip are secondary but available.
- The confirmation clearly belongs to the selected or waiting TaskNode.
- MessageStream does not compete with the action buttons.

### S8 Completed

| Item | Decision |
|---|---|
| User question | What was produced? |
| Primary surface | Result summary in DetailPanel |
| Secondary surface | Done TaskNode and file-review entry |
| Quiet surface | Audit entry |
| Hidden by default | Raw file ownership ids, full message history |
| Primary action | Review result or continue with a follow-up |
| Copy target | "Result is ready. Review summary or changed files." |

Review checks:

- Completed/read-only copy does not invite unavailable task edits.
- Result appears before file/audit details.
- The user can still ask a follow-up only if the input mode supports it.

### S9 File Changes

| Item | Decision |
|---|---|
| User question | What changed, and how do I verify it? |
| Primary surface | File change summary |
| Secondary surface | Result return link and Audit entry |
| Quiet surface | Done TaskNode context |
| Hidden by default | Raw task ids, low-value metadata, full audit evidence |
| Primary action | Inspect changed files or open audit |
| Copy target | "3 files changed in this task subtree." |

Review checks:

- File paths are readable and not visually crowded.
- Change type badges are compact.
- Audit is presented as verification, not as another primary panel.

### S10 Permission Denied

| Item | Decision |
|---|---|
| User question | Why can't I change this? |
| Primary surface | Disabled action/input reason |
| Secondary surface | Selected TaskNode remains visible |
| Quiet surface | TopBar status |
| Hidden by default | Controls that are irrelevant rather than merely disabled |
| Primary action | Return, inspect, or wait for permission context to change |
| Copy target | One plain reason, close to the disabled control |

Review checks:

- Permission boundary is visible without a full-page error feeling.
- The user can still understand the current task/session.
- Unavailable actions do not look like primary next steps.

### S11 Stale Snapshot

| Item | Decision |
|---|---|
| User question | Is this screen safe to act on? |
| Primary surface | Resync action and stale marker |
| Secondary surface | Last-known TaskTree |
| Quiet surface | Live/stale TopBar chip |
| Hidden by default | High-risk mutation controls |
| Primary action | Refresh/resync |
| Copy target | "This view is stale. Refresh before making changes." |

Review checks:

- Last-known context remains visible.
- Risky controls are disabled or hidden.
- Resync is the clear next safe action.

### S12 Backend Busy

| Item | Decision |
|---|---|
| User question | Did my command go through? |
| Primary surface | Pending-command state near the originating control |
| Secondary surface | Current TaskTree/DetailPanel remains stable |
| Quiet surface | Message evidence if available |
| Hidden by default | Global blocking overlays unless interaction is truly blocked |
| Primary action | Wait |
| Copy target | "Command accepted. Waiting for the next update." |

Review checks:

- Duplicate submit is disabled.
- The screen does not jump to an optimistic terminal state.
- Busy state is local to the command when possible.

### S13 Command Failed

| Item | Decision |
|---|---|
| User question | What failed, and how can I recover? |
| Primary surface | Inline recoverable error |
| Secondary surface | Retry/revise action |
| Quiet surface | Preserved TaskTree and selected object |
| Hidden by default | Raw backend payloads or stack traces |
| Primary action | Retry or revise |
| Copy target | "The command failed. Retry or revise the instruction." |

Review checks:

- The page does not collapse into a generic error screen.
- Context and selection are preserved.
- Error copy is safe and actionable.

## 5. Cross-State Surface Matrix

| Surface | Default role | Collapse first? | Never remove when |
|---|---|---:|---|
| TopBar | route and state context | No | user can mutate or navigate |
| Sidebar | session navigation | Tablet/mobile only | multiple sessions are available |
| TaskTree | primary control object | No | task tree exists |
| MessageStream | evidence and recent updates | Yes | a running/confirmation state needs process evidence |
| DetailPanel | selected object and next action | No | selection, confirmation, result, file, stale, or error exists |
| InputDock | scoped instruction surface | No | user can submit or needs disabled reason |
| AuditEntry | verification path | Yes | result/file/failure/trust state exists |

## 6. Review Script

Use this script during visual review:

1. Identify the state.
2. Ask: what is the user's next likely question?
3. Confirm the primary surface answers that question.
4. Check whether MessageStream repeats DetailPanel or TaskTree copy.
5. Check whether DetailPanel has a generic state note.
6. Check whether InputDock scope matches selection and permissions.
7. Check whether top-level status chips exceed two.
8. Check 1280px desktop for horizontal clipping.
9. Check that hidden raw ids/logs/audit evidence remain out of the default
   view.
10. Decide whether the state passes, needs copy reduction, needs layout
    reduction, or needs interaction clarification.

## 7. Acceptance Criteria

A future recomposition pass is acceptable only when:

- every state has one primary user question and one primary answer surface;
- TaskTree remains primary whenever it exists;
- MessageStream is subordinate and collapsible;
- DetailPanel does not duplicate generic state explanations;
- InputDock scope and disabled/read-only state are unambiguous;
- result, file change, and audit form one review path instead of three
  competing surfaces;
- 1280px desktop has no primary content clipping;
- Figma or frontend review screenshots can be checked against this document.
