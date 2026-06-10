# Plato Plan Cycle Semantics

> Status: product semantic baseline
>
> Last Updated: 2026-06-09
>
> Scope: user-facing meaning of Plan cycles inside a Session, especially what
> happens after a Plan has executed. This is not an implementation plan, API
> contract, or database schema.
>
> Related:
> [Plato Task Semantics](plato-task-semantics.md),
> [Plato Session Content Model](plato-session-content-model.md),
> [Plato Runtime Input Model](plato-runtime-input-model.md),
> [Plato Outcome Review Model](plato-outcome-review-model.md),
> [Workflow, Session, And Task UX Model](workflow-session-task-ux-model.md),
> [Plan / TaskNode Model Technical Design](../plans/feature/plan-tasknode-model-technical-design.zh-CN.md)

## 1. Core Definition

A Plan Cycle is one round of authoring, executing, reviewing, and accepting
work inside a Session.

```text
Authoring -> Plan Ready -> Execution -> Finalization -> Outcome Review -> Acceptance
```

A Session may contain more than one Plan Cycle, but only one Plan should be
active at a time.

The central object inside a Plan Cycle is `Plan`.

Collaborator produces a Plan, not a loose TaskTree list. In Product 1.1, the
Plan owns a flat ordered TaskNode list, the Plan-level goal, the Plan-level
context policy, and the Plan-level outcome. This gives the Session a clear loop
boundary:

```text
Session
  -> Plan 1
      -> TaskNode list
      -> Plan finalization
      -> Outcome Review
  -> Plan 2
      -> TaskNode list
      -> ...
```

Plan is therefore a context-management object as much as a planning object. It
is the unit that tells Collaborator, execution Agents, reviewer Agents, audit,
and the UI what work is in scope for the current round.

## 2. Why Plan Cycle Exists

Plan execution completed does not automatically mean the Session is over.

After execution, the user may want to:

- review the result;
- inspect file changes;
- ask questions;
- accept and close;
- recover failures;
- create follow-up work;
- continue from the accepted outcome.

Without Plan Cycle semantics, the product has no clear answer for what happens
after the first Plan finishes.

## 3. Product Lifecycle

Recommended lifecycle:

```text
Session created
  -> Plan Cycle 1 authoring
  -> Plan Cycle 1 execution
  -> Plan Cycle 1 finalization
  -> Plan Cycle 1 outcome review
  -> accepted / closed / recovered / follow-up requested
  -> optional Plan Cycle 2 authoring
```

Plan Cycle should make it clear when the user is:

- shaping a plan;
- supervising execution;
- waiting for Plan-level synthesis, validation, or summary work;
- reviewing outcome;
- starting another round.

## 3.1 Plan Lifecycle

Recommended Plan lifecycle:

```text
draft
  -> reviewing
  -> approved
  -> running
  -> finalizing
  -> awaiting_acceptance
  -> accepted / follow_up_needed / failed / archived
```

Task completion and Plan completion are not the same thing.

```text
all required TaskNodes terminal
  -> Plan finalization
  -> Plan outcome review
  -> user acceptance or follow-up decision
```

The `finalizing` phase may involve other LLM or Agent work:

- summarizing Plan outcome;
- verifying whether the original Plan objective was satisfied;
- aggregating file changes across TaskNodes;
- producing result cards or result summaries;
- identifying unresolved questions, warnings, and follow-up work;
- preparing compressed context for the next Plan.

These jobs are part of Plan finalization. They are not raw chat, and they are
not automatically user-visible TaskNodes unless the product intentionally
exposes them as work contracts.

## 4. Plan Execution Completed

When all required TaskNodes in a Plan reach terminal states, the Session should
enter Plan finalization first. Outcome Review starts after the Plan has produced
or explicitly skipped the minimum required Plan-level summary and evidence
rollups.

Outcome Review answers:

1. Was the intended work completed?
2. What was produced?
3. What files or artifacts changed?
4. Which Tasks failed, skipped, or produced warnings?
5. What evidence is available?
6. What can the user do next?

Outcome Review is not raw chat. It is a structured state around result,
evidence, recovery, and next actions.

See [Plato Outcome Review Model](plato-outcome-review-model.md) for the
recommended review workspace information structure.

## 5. Outcome Review States

Product language can stay simple, but internal product semantics should
distinguish outcome quality.

| Outcome | User meaning | Typical next actions |
|---|---|---|
| Completed successfully | Required work is done. | Accept, inspect result, ask, create follow-up. |
| Completed with warnings | Work is mostly done, but there are risks, skipped optional work, or audit warnings. | Inspect, accept with warning, recover, create follow-up. |
| Partially completed | Some required work finished, but some failed or were skipped. | Retry, revise, skip, create recovery plan. |
| Failed | The Plan did not reach its intended outcome. | Inspect failure, retry, revise plan, close as failed. |
| Awaiting acceptance | Execution is done enough for user review. | Accept, request changes, ask, close. |

UI copy can use:

- `Ready for review`
- `Work completed. Review the outcome.`
- `Completed with warnings`
- `Needs recovery`

## 6. What The User Should See

After execution completes, the Main Page should expose an Outcome area.

It should include:

- Plan result summary;
- Task completion summary;
- failed/skipped/warning list;
- file change summary;
- audit entry;
- suggested next actions;
- read-only question affordance;
- close or accept action.

Plan & Progress remains visible, but its meaning changes:

```text
before execution: proposed contract
during execution: control surface
after execution: result map and evidence index
```

Plan remains visible as the current work program. The user should be able to
tell:

- which Plan is active or under review;
- whether the Plan is waiting for acceptance;
- whether the Plan needs follow-up work;
- whether the next user input will ask a question, revise this Plan, or start a
  new Plan.

## 7. Continuing A Session

If the user wants to continue after acceptance, the product should decide
whether the input creates a follow-up Plan Cycle or stays read-only.

Recommended rules:

| User intent | Same Session? | New Plan Cycle? |
|---|---|---|
| Ask about result | Yes | No |
| Inspect files, diff, or audit | Yes | No |
| Retry failed work | Yes | Maybe, if recovery requires replanning |
| Small follow-up on same outcome | Yes | Yes |
| New independent goal | Prefer new Session | No |
| Major pivot unrelated to accepted outcome | Prefer new Session | No |

The product should avoid silently mixing unrelated work into the same Session.

## 8. Plan History And Active Plan

Product invariant:

```text
one Session may have many Plans
one Session should have at most one active Plan
previous Plans are history, baseline, and evidence
```

Old Plans should not be silently overwritten. They should remain available as:

- accepted baseline;
- execution history;
- audit/evidence context;
- source for follow-up authoring.

## 9. Follow-Up Authoring

Follow-up authoring is not the same as editing an active Task.

Follow-up authoring means:

```text
user accepted or reviewed an outcome
  -> user requests additional related work, recovery, or extension
  -> Collaborator generates a new Plan using prior outcome context
```

Examples:

- "Now add dark mode."
- "Make the result mobile-friendly."
- "Fix the warnings from the last run."
- "Add tests for the files you changed."

The new Plan should be visibly related to the previous outcome:

- continuation;
- revision;
- recovery;
- validation;
- extension.

## 10. Collaborator Context Requirement

If a Session can continue after outcome acceptance, Collaborator / Authoring
Agent must use governed authoring context.

Execution Context is not enough.

| Context kind | Primary user object | Used by | Purpose |
|---|---|---|---|
| Execution Context | Task | Execution Agent | Complete current Task. |
| Plan Context | Plan | Collaborator / Authoring Agent / reviewer Agent | Generate, revise, finalize, or continue a Plan. |
| Authoring Context | Session / Plan | Collaborator / Authoring Agent | Generate or revise a Plan. |
| Inquiry Context | Session / Plan / Task | Read-only answer path | Answer without mutating work. |

Authoring Context should include:

- current Session goal;
- active Plan goal and status;
- current or prior Plan summary;
- execution outcome summary;
- accepted/rejected status;
- completed, failed, skipped, and warning summaries;
- file change summary;
- relevant result refs;
- user follow-up request;
- active guidance.

It should not rely on raw chat as the only source of truth.

## 11. Product 1.0 Boundary

Product 1.0 does not need full multi-cycle authoring.

Product 1.0 can stop at:

- Outcome Review;
- accept/close;
- inspect result;
- inspect file summary;
- inspect audit entry;
- retry or recover failed work when already supported;
- ask read-only questions if the surface exists.

Product 1.1 should add:

- continue from result;
- follow-up Plan Cycle authoring;
- Plan history;
- Plan finalization jobs;
- Plan-level context compression;
- authoring context;
- Plan revision semantics.

## 12. Relationship To Runtime Input

After Outcome Review, runtime input must be classified carefully.

| Input example | Likely intent | Scope | Product behavior |
|---|---|---|---|
| "What changed?" | Question | Session / Task | Read-only answer. |
| "Why did this fail?" | Question | Task | Read-only answer with recovery link. |
| "Try again with smaller changes." | Command | Task / Plan | Retry or recovery plan. |
| "Now add login." | Command | Plan | New follow-up Plan Cycle if related. |
| "Use the same style next time." | Guidance | Session | Persist as guidance. |

Low-confidence classification should not create a follow-up Plan silently.

## 13. Product Invariants

1. Plan execution completed means Finalization and Outcome Review, not automatic
   Session death.
2. A Session can continue only through explicit user intent.
3. The current Session should have at most one active Plan.
4. Prior Plans become history, baseline, and evidence.
5. Follow-up work should create a new Plan Cycle.
6. Read-only questions after acceptance should not create a new Plan.
7. Collaborator follow-up authoring requires governed authoring context.
8. Raw chat must not be the only source for follow-up planning.
9. Collaborator produces a Plan, not a loose TaskTree list.
10. Product 1.1 Plan owns one flat TaskNode list and the Plan-level
    finalization workflow.
11. TaskNode terminal states are necessary but not always sufficient for Plan
    completion.
