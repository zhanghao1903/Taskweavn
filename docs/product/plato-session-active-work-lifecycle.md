# Plato Session Active Work Lifecycle

> Status: product semantic baseline
>
> Last Updated: 2026-06-19
>
> Scope: user-facing lifecycle rules for Session, active Plan, Direct Task, Plan
> completion, manual Plan archive, Conversation continuity, and Context Manager
> behavior. This is not an API contract, database schema, or implementation
> plan.
>
> Related:
> [Plato Session Content Model](plato-session-content-model.md),
> [Plato Conversation And Direct Task PRD](plato-conversation-and-direct-task-prd.md),
> [Plato Conversation And Direct Task UX Flow](plato-conversation-and-direct-task-ux-flow.md),
> [Plato Plan Cycle Semantics](plato-plan-cycle-semantics.md),
> [Workflow, Session, And Task UX Model](workflow-session-task-ux-model.md)

## 1. Core Product Model

Session is the product's core user-facing work unit.

Plan is not the product's core node. Plan is a structured work segment inside a
Session. It organizes a larger round of work, but it should not own the user's
primary continuity.

```text
Session = continuous collaboration timeline and product root
Conversation = Session perception layer
Active Work = current Plan or Direct Task inside the Session
Plan = structured multi-step work segment
Direct Task = lightweight executable work segment
Task = executable work contract
Archived Plan = read-only historical work segment
```

The user enters, resumes, and understands Plato through Session. Plan and Direct
Task are how the Session performs work.

## 2. Active Work Invariant

A Session should expose at most one active work item at a time:

```text
No active work
  | current Plan
  | current Direct Task
```

This keeps the UI and Context Manager deterministic. A user input should always
have a clear target:

- Session-level when there is no active work or when the user asks a general
  question;
- Plan-level when a Plan is active or completed but not archived;
- Task-level when a Task is selected or waiting for the user.

## 3. Plan Completion Is Not Archive

Plan completion is a system outcome. Archive is a user control action.

```text
Plan running
  -> Plan completed
  -> user reviews outcome
  -> user clicks "Archive plan"
  -> Plan archived
  -> Session returns to no active work / ready for next work
```

The product must not auto-archive a completed Plan. A completed Plan remains the
active work until the user explicitly archives it.

Recommended control copy:

```text
Archive plan
```

Recommended helper copy:

```text
Plan completed. Archive it when you are ready to move it into history and start
the next work in this Session.
```

Avoid `Finish` as the primary action because completion already happened. The
user action is not finishing execution; it is moving completed work out of the
active work surface.

## 4. Page Behavior After Archive

After the user archives a completed Plan:

- Conversation does not reset.
- Conversation remains the same Session timeline.
- A boundary item is inserted, for example `Plan archived: <plan title>`.
- The Plan is removed from the active work surface.
- The input returns to Session-level scope.
- The user can start a new Plan-required request, a Direct Task, or ask a
  read-only question.
- The archived Plan remains available from Session history.

The page should not show a blank conversation. The Session is continuous.

## 5. Conversation Continuity

Conversation belongs to Session, not to Plan.

Users should be able to scroll backward across Plan boundaries and see prior
work. Plan boundaries should be explicit so the timeline stays understandable:

```text
Plan started
Task completed
Plan completed
Plan archived
Next user request
New Plan started
```

Conversation items may still carry scope metadata:

```text
Session
Plan
Task
```

Scope filters can help the UI focus, but they must not imply that old Plan
conversation content disappeared.

## 6. Archived Plan Entry

The primary entry for historical Plans should be Session-level, not workspace
navigation.

Recommended entries:

1. Conversation topbar: `Plans` or `History`.
2. Plan boundary items in the Conversation timeline.
3. Optional Detail Panel state when a historical Plan is selected.

Archived Plans should not become left-sidebar navigation items by default. The
left sidebar is for workspace/session navigation, while archived Plans are
content inside the current Session.

## 7. Archived Plan Behavior

Archived Plans are read-only history.

Users can:

- view Plan summary;
- view Task list and outcomes;
- view result, file changes, and audit links;
- ask read-only questions about the archived Plan;
- start follow-up work that references the archived Plan.

Users should not directly edit an archived Plan. Follow-up work creates a new
active Plan or Direct Task with an explicit reference to the archived Plan.

## 8. Direct Task Lifecycle

Direct Task is also active work, but it does not need a Plan archive ceremony.

```text
User input
  -> Direct Task created
  -> Direct Task running / waiting / completed / failed
  -> result or recovery projected
  -> active work clears when terminal and no recovery is pending
```

Direct Task history remains in Conversation and Activity. If a Direct Task
becomes complex, Plato may suggest creating a Plan.

## 9. Context Manager Policy

Context Manager uses Session as the root, but active work determines the default
LLM input.

Default policy:

| Context source | Default inclusion |
|---|---|
| Current active Plan / Direct Task | Full relevant facts. |
| Current selected Task | Full relevant task facts. |
| Session conversation recent messages | Bounded recent window. |
| Archived Plan summaries | Compact summary only when useful. |
| Archived Plan full messages/tasks/results | On demand only. |
| Audit/log/tool payloads | Never by default; retrieved by explicit need. |

Archived Plans must not be copied wholesale into each new LLM request. They are
available evidence and continuity, not the default active objective.

When the user explicitly refers to previous work, the Context Manager may
retrieve the relevant archived Plan summary, result, Task outcomes, file
changes, or audit refs.

## 10. Acceptance Criteria

Product behavior is correct when:

1. A completed Plan remains visible until the user clicks `Archive plan`.
2. Archiving a Plan removes it from active work without clearing Conversation.
3. The user can scroll back to previous Plan conversation content.
4. Historical Plans are reachable from a Session-level history entry.
5. Archived Plans are read-only and can be referenced by follow-up work.
6. Context Manager defaults to current active work and bounded Session
   continuity, not full archived Plan replay.
7. Direct Task can complete without forcing Plan creation or Plan archive.
