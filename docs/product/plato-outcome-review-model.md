# Plato Outcome Review Model

> Status: product semantic baseline
>
> Last Updated: 2026-06-19
>
> Scope: UI information structure and product meaning for the state after a
> Plan Cycle has executed. This is not a visual design, API contract, or
> implementation plan.
>
> Related:
> [Plato Plan Cycle Semantics](plato-plan-cycle-semantics.md),
> [Plato Session Active Work Lifecycle](plato-session-active-work-lifecycle.md),
> [Plato Task Semantics](plato-task-semantics.md),
> [Plato Session Content Model](plato-session-content-model.md),
> [Plato Runtime Input Model](plato-runtime-input-model.md)

## 1. Core Definition

Outcome Review is the user-facing review workspace after a Plan Cycle has
executed.

It is not a chat ending page and not a raw execution log. It is where the user
understands, verifies, archives, recovers, or continues from the outcome.

```text
Plan execution completed
  -> Outcome Review
  -> Archive plan / Ask / Recover / Follow-up
```

## 2. Product Questions

Outcome Review should answer five questions:

1. Did this Plan finish?
2. What did Plato produce?
3. What changed in the workspace?
4. What failed, was skipped, or needs attention?
5. What can the user do next?

If the UI cannot answer these questions without forcing the user into Audit or
logs, the Outcome Review is incomplete.

## 3. Information Structure

Outcome Review should be organized as a completion review workspace with six
information areas.

### 3.1 Outcome Header

Purpose: provide the overall outcome at a glance.

Content:

- Plan Cycle identifier, if visible;
- outcome status;
- one-sentence summary;
- task completion count;
- file change count;
- warning/failure count;
- primary action;
- secondary actions.

Recommended status labels:

- `Ready for review`
- `Completed`
- `Completed with warnings`
- `Partially completed`
- `Needs recovery`
- `Ready to archive`

Example copy:

```text
Plato completed 5 of 5 tasks and changed 3 files.
```

Primary action examples:

- `Archive plan`
- `Review warnings`
- `Recover failed tasks`

Secondary action examples:

- `Ask about result`
- `View audit`
- `Start follow-up`

### 3.2 Result Summary

Purpose: answer "what was produced?"

Content:

- user-readable outcome summary;
- whether the original goal appears satisfied;
- produced artifact or result refs;
- implemented behavior;
- tests or validation summary when available;
- known limitations.

Rules:

- This should not be raw Agent final output.
- It should be product-rendered from result facts, summaries, and evidence.
- It should stay understandable without reading the full TaskTree.

### 3.3 Task Outcome Map

Purpose: answer "how did each planned unit finish?"

Content:

- TaskTree or Task list in terminal view;
- each Task terminal state;
- short per-Task outcome;
- failure, skipped, cancelled, warning, or retry indicators;
- link to Task Detail Outcome.

Terminal Task categories:

- done;
- failed;
- skipped;
- cancelled;
- warning;
- retried;
- waiting for recovery.

Product meaning:

```text
Before execution: TaskTree is the proposed contract.
During execution: TaskTree is the control surface.
After execution: TaskTree is the result map and evidence index.
```

### 3.4 Workspace Changes

Purpose: answer "what changed?"

Product 1.0 can show file summary. Product 1.1 should move toward file viewer
and diff review.

Content:

- changed file count;
- added / modified / deleted grouping;
- per-file short summary;
- changed line ranges when available;
- `View diff` action when available;
- `Open file` action when available;
- related Task links.

Rules:

- Workspace changes should be close to Result Summary.
- Agent prose is not the authority for changed files.
- File changes must be evidence-backed or explicitly marked unavailable.

### 3.5 Risks, Warnings, And Unresolved Items

Purpose: answer "what needs attention?"

Content:

- failed Tasks;
- skipped Tasks;
- incomplete evidence;
- tests not run;
- audit warning;
- permission-limited evidence;
- recoverable errors;
- suggested recovery action.

Rules:

- Important risks cannot live only in Audit.
- Audit provides proof; Outcome Review must surface the user-facing warning.
- Recovery options should be visible when available.

### 3.6 Next Actions

Purpose: answer "what can I do now?"

Actions should depend on outcome quality.

| Outcome | Primary actions |
|---|---|
| Success | Archive plan, ask about result, start follow-up, view audit. |
| Warning | Review warning, archive with warning visible, create follow-up, view evidence. |
| Partial | Retry failed tasks, revise plan, skip remaining, create recovery plan. |
| Failed | Inspect failure, retry, revise plan, close as failed. |
| Archived | Start follow-up, ask about archived result, view history. |

Next actions should make clear whether they are read-only, recovery, or new
work.

## 4. Main Page Layout Semantics

This document does not prescribe final layout, but it does define semantic
regions.

Recommended Main Page semantic layout in Outcome Review:

```text
Left: Plan Cycle / Task Outcome Map
Center: Outcome Header + Result Summary + Workspace Changes + Warnings
Right: Detail for selected Task, warning, file summary, or audit entry
Bottom: Unified input, defaulting to question/read-only interpretation
```

The key change from execution mode:

- TaskTree is no longer only a control surface.
- Center panel should prioritize result trust and next action.
- Input should default toward read-only question unless the user clearly asks
  for follow-up or recovery.

## 5. Task Detail Outcome Mode

When the user selects a Task during Outcome Review, Task Detail should show:

- Task intent;
- Plan promise;
- execution outcome;
- result summary;
- file changes caused by or linked to this Task;
- warnings or errors;
- ASK/confirmation history if relevant;
- audit link;
- actions.

Recommended actions:

- ask about this;
- retry;
- revise and retry;
- create follow-up;
- view file changes;
- view audit.

Task Detail Outcome should not show running controls unless the user enters a
recovery or follow-up execution path.

## 6. Input Defaults During Outcome Review

During Outcome Review, the unified input should default to read-only question.

Examples:

| User input | Likely intent | Behavior |
|---|---|---|
| "What changed?" | Question | Answer from result/file summary. |
| "Why did this fail?" | Question | Explain failure and offer recovery. |
| "Run the failed task again." | Command | Retry / recovery command. |
| "Now add dark mode." | Command | Create follow-up Plan Cycle if related. |
| "Use this style going forward." | Guidance | Persist Session or follow-up guidance. |

The router should not create a follow-up Plan Cycle silently on low confidence.

## 7. Outcome States

Outcome Review may use UI states that are more specific than backend lifecycle
fields.

Suggested UI state names:

- `review_ready_success`
- `review_ready_with_warnings`
- `review_ready_partial`
- `review_ready_failed`
- `archived`
- `follow_up_authoring`
- `closed`

These are product semantics. They do not require these exact backend status
strings.

## 8. Relationship To Audit

Audit is the trust plane, not the primary review workspace.

Outcome Review should surface:

- audit verdict summary;
- evidence availability;
- warnings;
- permission-limited evidence;
- link to detailed audit records.

Audit should provide:

- precise trace;
- raw refs;
- tool observations;
- event/log/config evidence;
- hidden evidence boundaries;
- replay or reconstruction support.

The user path should be:

```text
Outcome Review -> suspicious item -> Audit evidence
```

not:

```text
Outcome Review missing information -> user must search Audit manually
```

## 9. Relationship To Git, Diff, And File Viewer

Product 1.0 can rely on file summaries. Product 1.1 should make Outcome Review
stronger with workspace inspection.

Product 1.1 additions:

- git status;
- changed file list;
- per-file diff;
- line-range links;
- file viewer;
- changed-line evidence;
- task-to-diff linkage.

These are evidence references under Outcome Review, not separate collaboration
scopes.

## 10. Product 1.0 / 1.1 Boundary

Product 1.0 minimum:

- result summary;
- file change summary;
- audit entry link;
- failed/skipped/warning visibility;
- retry/recovery where already supported;
- `Archive plan` affordance after completed Plan review if implemented;
- no raw LLM output as main outcome.

Product 1.1 expansion:

- diff viewer;
- file viewer;
- stronger changed-line evidence;
- follow-up Plan Cycle;
- authoring context from completed or archived outcome;
- read-only inquiry over outcome;
- richer archive and handoff flows.

## 11. Product Invariants

1. Outcome Review is a completion review workspace.
2. Plan execution completed enters review, not automatic Session death.
3. Archiving the completed Plan is a user act.
4. TaskTree after execution is a result map and evidence index.
5. Risks and unresolved items must be visible on Main Page.
6. Workspace changes should be close to result summary.
7. Input defaults to read-only question unless the user asks for recovery or
   follow-up.
8. New work should enter a follow-up Plan Cycle.
9. Audit remains the proof layer, not the main review surface.
10. Raw LLM output is not the primary outcome artifact.
