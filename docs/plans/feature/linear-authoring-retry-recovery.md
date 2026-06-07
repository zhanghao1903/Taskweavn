# Feature Plan: Linear Authoring And Minimal Retry Recovery

> Status: accepted for Product 1.0 local unsigned RC
> Type: Product 1.0 authoring policy / execution recovery
> Last Updated: 2026-06-07
> Product Policy: [Plato 1.0 Line-First Authoring Policy](../../product/plato-1-0-line-first-authoring-policy.md)
> Related Plans: [RawTask And DraftTaskTree Persistence](raw-task-draft-tree-persistence.md), [Fixed-Route Task Execution Bridge](fixed-route-task-execution-bridge.md)
> Related Decisions: [ADR-0009](../../decisions/ADR-0009-single-active-session-worktree.md), [ADR-0010](../../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md)
> Release Record: Accepted on 2026-06-07. Line-first execution is controlled by
> TaskBus parent/dependency semantics; stronger generated-line guarantees and
> richer attempt UI remain follow-up hardening.

---

## 1. Problem

Product 1.0 is converging on a line-first execution model:

- one active Session owns one active work tree;
- most generated plans are sequential;
- users need reliable step-by-step progress more than parallel orchestration;
- failed upstream work should not let downstream work continue blindly.

Product 1.0 local RC accepts the existing TaskBus-controlled execution path as
the shipped boundary. The remaining risks are now follow-up hardening rather
than local RC blockers:

- Authoring Domain can still represent a tree/forest-like draft structure.
- Published root Tasks can execute independently even when users mentally see
  them as sequential.
- TaskBus dependency blocking works only when `parent_id` expresses the
  dependency.
- Stop-intent interrupted running Tasks now have sidecar startup recovery, but
  generic stale `running` Tasks without an interrupt intent still need a
  follow-up recovery policy.
- Minimal manual retry exists for failed Tasks, while richer retry-attempt UI
  remains future work.

This work package records the accepted Product 1.0 minimum without expanding
into full context governance.

### 1.1 Current Implementation Status

As of 2026-06-07:

Done:

- failed published Tasks expose retry eligibility in projection;
- retry moves the same published Task identity from `failed` back to `pending`;
- retry clears the active-attempt lifecycle fields and preserves previous
  failure evidence in append-only sources;
- Main Page command contract has a retry route;
- TaskBus dependency checks keep children blocked until the same parent Task
  reaches `done`;
- sidecar startup can recover running Tasks that had an explicit stop/interrupt
  intent into a cancelled failed state;
- Product 1.0 local unsigned RC accepts TaskBus-controlled linear execution as
  the current product boundary.

Follow-up hardening, not Product 1.0 local RC blockers:

- stronger default-generation guarantees for Collaborator-generated
  DraftTaskTrees;
- additional publish/dependency regression coverage for generated chains;
- stale `running` Tasks from a previous sidecar process without an interrupt
  intent need a product decision: mark recoverable, fail with infrastructure
  error, or require manual operator intervention;
- richer retry evidence should be surfaced through Audit/Diagnostics without
  adding a full TaskAttempt model to Product 1.0.

---

## 2. Goals

Product 1.0 accepted goals:

1. Use TaskBus parent/dependency semantics as the line-first execution control.
2. Keep minimal whole-Task retry for failed/interrupted Tasks.
3. Preserve enough task-related raw material to support retry and future
   context governance.
4. Keep full SessionContext governance, summarization, and budget management
   out of Product 1.0.
5. Prevent Authoring Domain and Task Domain from appearing as simultaneous
   active workflows in one Session.

Follow-up hardening goals:

1. Make Authoring Domain support a stricter generated linear structure.
2. Make the default generated DraftTaskTree linear by construction.
3. Add richer retry-attempt evidence and UI if Product 1.1 needs it.

---

## 3. Non-goals

- Do not redesign the Task authoring UX in this work package.
- Do not remove tree support from the domain model.
- Do not implement multi-agent parallel scheduling.
- Do not implement full post-publish editing strategy.
- Do not implement a general context summarizer or `SessionContextStore`.
- Do not retry partial tool operations inside one AgentLoop step.
- Do not guarantee safe retry for non-idempotent external side effects.

---

## 4. Product Decisions

### 4.1 Default Authoring Shape

The Product 1.0 policy prefers a linear DraftTaskTree. For local unsigned RC,
the accepted control point is TaskBus parent/dependency execution; generated
line enforcement is follow-up hardening.

Recommended representation:

```text
Task A
  -> Task B
    -> Task C
      -> Task D
```

This uses the existing `parent_id` dependency model instead of introducing a
new dependency DSL.

Rationale:

- TaskBus already blocks children until parent status is `done`.
- The UI can still render the plan as a line-like task list.
- The backend keeps tree extensibility for Product 1.1+.
- We avoid introducing a second execution dependency model.

### 4.2 Root Task Semantics

The intended line-first policy is for generated plans to normally have one root
Task.

Multiple root Tasks should be treated as an advanced or imported shape, not the
default output of authoring.

If multiple roots exist, fixed-route execution may still claim eligible root
Tasks unless a separate fail-stop policy blocks the Session. Therefore stronger
authoring hardening should encode sequence explicitly.

### 4.3 Retry Semantics

Product 1.0 should support minimal whole-Task retry:

- retry continues on the same published Task identity;
- the previous failed/interrupted execution evidence remains auditable through
  append-only MessageStream, result/error summaries, Audit, and logs;
- retry mutates only the current lifecycle fields on the TaskDomain fact:
  `failed` returns to `pending`, while historical failure records stay outside
  the current status fields;
- the Main Page control plane should keep the same Task card and show it moving
  from `failed` back to `queued` / `running`;
- retry should preserve dependency semantics: downstream Tasks remain blocked
  until the retried Task reaches `done`;
- retry is manual first. Automatic retry is deferred unless the failure is a
  clearly safe infrastructure error.

Implementation decision for the initial manual retry slice:

- keep retry as an explicit user command;
- move the same failed Task back to `pending` through TaskBus lifecycle retry;
- clear current `result_ref`, `error_ref`, `claimed_by`, `started_at`, and
  `completed_at` fields so they describe only the active attempt;
- keep failure evidence in MessageStream, result/error summaries, Audit, and
  diagnostics rather than storing attempt history in TaskDomain;
- keep the same Task card in the Main Page control plane;
- treat the Task dependency as satisfied only when that same Task reaches
  `done`, so downstream Tasks remain blocked while retry is pending, running,
  or failed;
- do not add automatic retry policy or a full TaskAttempt history UI in this
  slice.

### 4.4 Context Governance Boundary

Agent lifecycle is Task-run scoped, but retry needs durable context material.

Product 1.0 should persist raw material already available from current systems:

- RawTask and active DraftTaskTree facts;
- published TaskDomain fields;
- task-level EventStream entries;
- task-level MessageStream entries;
- result refs and error refs;
- file/evidence refs when available.

Product 1.0 does not need a new general context governance layer. Product 1.1
can later introduce session summaries, context budgets, task-local pruning, and
context assembly policies using this durable material.

### 4.5 Active Domain Guard

Product 1.0 must enforce a single active domain in the user control surface.

```text
RawTask / RawTaskAsk active
  -> no TaskTree yet

TaskTree / TaskNode active
  -> RawTask / RawTaskAsk is history unless explicit revision starts
```

This addresses the dirty-session case where an old pending authoring ASK is
answered after a TaskTree already exists, accidentally producing a new RawTask
beside the current TaskTree.

Initial policy:

- Gateway projection prefers Task Domain once `TaskTreeView` exists.
- Pending authoring asks are marked or projected as `superseded`.
- Answering a superseded authoring ask returns `command_rejected` with
  `details.reason = "stale_authoring_context"`.
- Reusing a late answer requires explicit `Apply as plan guidance` or
  `Revise plan` behavior.
- No data is deleted; old RawTask/ASK/answer facts remain available for audit
  and replay.

---

## 5. Proposed Implementation Phases

### P8.L1 Linear Authoring Shape

Status: follow-up hardening, not a Product 1.0 local RC blocker.

Deliver:

- Authoring service option or default policy for linear draft output.
- Conversion helper that turns an ordered task list into a parent-child chain.
- Tests proving generated draft nodes form a single chain by default.
- Projection remains compatible with existing tree rendering.

Acceptance:

- default generated DraftTaskTree has one root;
- every later node points to the previous node as parent;
- existing non-linear/imported tree fixtures still work when explicitly used;
- no Main Page UI rewrite is required.

### P8.A1 Active Domain Projection And Stale ASK Guard

Deliver:

- snapshot projection rule that hides/supersedes pending RawTaskAsk when a
  TaskTree exists;
- command guard for authoring ASK answers after Task Domain is active;
- dirty fixture covering RawTaskAsk + TaskTree coexistence;
- UI/API docs and tests proving the Main Page shows plan/TaskNode targets, not
  stale authoring controls.

Acceptance:

- a Session cannot show active RawTaskAsk controls and active TaskTree controls
  at the same time;
- answering an old authoring ASK after TaskTree generation cannot create a new
  RawTask silently;
- the user is offered an explicit path to apply the answer as plan guidance or
  start a plan revision;
- audit/replay can still explain the old ask and late answer.

### P8.L2 Publish Linear Dependencies

Status: follow-up validation after generated-line hardening.

Deliver:

- publish preserves draft parent-child chain into published Task parent ids;
- restart -> snapshot -> publish tests verify dependency shape survives
  persistence;
- fixed-route `claim_next` only exposes the next line step.

Acceptance:

- after publishing a linear draft, only the first Task is immediately claimable;
- after first Task completes, second Task becomes claimable;
- if first Task fails, second Task remains blocked.

### P8.R1 Minimal Retry Model

Status: accepted for the Product 1.0 minimum.

Deliver:

- define retry command semantics for failed/interrupted Task;
- add a retry path that moves the same Task back to pending;
- preserve previous failure evidence;
- expose retry eligibility and command handling through the Main Page backend
  contract.

Recommended initial model:

- reset the failed Task in place through TaskBus retry;
- keep the Task card identity stable in the Main Page control plane;
- keep deeper attempt history and automatic policies out of Product 1.0.

Acceptance:

- user can retry a failed Task without regenerating the whole plan;
- retry does not unblock downstream Tasks until retried Task succeeds;
- retry result is visible in snapshot/audit-ready refs;
- unsupported retry returns a structured command error.

Implementation notes:

- `TaskBus.retry(...)` and `SqliteTaskBus.retry(...)` reset the same Task row
  from failed back to pending and clear active-attempt fields.
- `TaskPublisher.retry_task(...)`, task command services, UI command gateway,
  and sidecar HTTP routes expose the retry path.
- Projection keeps the original failed Task card and exposes retry eligibility
  instead of creating replacement retry Task cards.
- Fixed-route execution tests cover parent retry without unblocking children
  early.

### P8.R2 Interrupted Running Recovery

Status: accepted for explicit stop/interrupt recovery; generic stale-running
policy remains follow-up hardening.

Deliver:

- detect `running` Tasks from a previous sidecar process after restart;
- expose an interrupted/recoverable state instead of silently leaving Tasks
  stuck;
- provide manual retry or mark-failed behavior.

Acceptance:

- restart with old `running` Task does not auto-continue silently;
- Main Page can show recovery-required state;
- user-triggered retry follows P8.R1 semantics.

Implementation notes:

- Stop-intent interrupted running Tasks are recovered on sidecar startup through
  `recover_interrupted_running_tasks(...)` into failed/cancelled state with a
  `sidecar_recovery` safe point.
- This does not yet cover a generic stale `running` Task without an interrupt
  intent. That edge policy is deferred out of Product 1.0 local RC.

### P8.C1 Retry Evidence Capture

Status: accepted for Product 1.0 minimum through existing durable streams;
richer TaskAttempt evidence UI remains follow-up hardening.

Deliver:

- document and test which existing raw materials are sufficient for retry;
- ensure task-level EventStream and MessageStream queries can reconstruct the
  previous attempt;
- record result/error refs in a stable form usable by future Audit Page and
  context assembly.

Acceptance:

- failed/interrupted Task has enough persisted evidence to explain why retry is
  offered;
- retry does not depend on an in-memory Agent instance;
- context governance can remain Product 1.1 without blocking Product 1.0 retry.

---

## 6. Product 1.0 Accepted Coverage

Accepted behavior:

- failed published Tasks expose retry eligibility;
- retry moves the same published Task identity from `failed` back to `pending`;
- retry clears active-attempt lifecycle fields while preserving append-only
  failure evidence;
- snapshot projection keeps the same Task card stable across retry;
- TaskBus parent/dependency checks keep downstream Tasks blocked until the
  upstream Task reaches `done`;
- explicit stop/interrupt startup recovery moves interrupted running Tasks into
  a cancelled failed state that can be retried manually;
- unsupported retry returns a structured command error.

Follow-up regression coverage:

- generated default plan shape can be tightened to one parent-child chain;
- explicit non-linear tree input should remain supported when intentionally
  used;
- generated-chain publish tests can prove draft parentage reaches TaskBus
  parent ids;
- generic stale `running` Tasks without interrupt intent need a product policy;
- richer retry evidence can be projected through Audit/Diagnostics or a future
  TaskAttempt UI.

---

## 7. Risks And Decisions Needed

### 7.1 Retry Domain Shape

Decision for Product 1.0:

- use minimal Task reset metadata and append-only evidence streams;
- defer first-class TaskAttempt history and attempt UI to Product 1.1+.

This is acceptable only if previous failure evidence remains available through
MessageStream, result/error summaries, Audit, logs, and the diagnostic bundle.

### 7.2 Non-idempotent Side Effects

Retry can duplicate external side effects. Product 1.0 should keep retry manual
and disclose that retry reruns the Task.

### 7.3 Context Raw Material Completeness

Current durable streams are likely enough for small tasks. Larger workflows need
Product 1.1 context governance before retry quality can be considered robust.

### 7.4 UI Scope

Main Page does not need a full retry UX redesign initially. It only needs a
clear recover/retry affordance for failed/interrupted current Task.

---

## 8. Product 1.0 Boundary

Product 1.0 local unsigned RC includes:

- TaskBus-controlled dependency-safe sequential execution;
- minimal manual retry for failed/interrupted Tasks on the same Task identity;
- explicit stop/interrupt startup recovery;
- enough persisted evidence for retry explanation through existing append-only
  records.

Product 1.0 local unsigned RC does not require:

- stricter default generated DraftTaskTree chain guarantees;
- generic stale-running recovery without explicit interrupt intent;
- richer TaskAttempt history UI;
- automatic retry policy.

Product 1.1+ includes:

- context governance and summarization;
- richer task attempt history UI;
- automatic retry policy;
- branch-aware execution policies;
- post-publish editing strategy beyond minimal retry.

---

## 9. Follow-Up Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Audit or harden Linear authoring / retry behavior after Product 1.0 local RC
acceptance.

Context:
docs/plans/feature/linear-authoring-retry-recovery.md records Product 1.0
local unsigned RC acceptance. Current linear execution is controlled by TaskBus
dependency semantics. Do not reopen Product 1.0 local RC unless that
TaskBus-controlled execution behavior regresses.

Scope:
1. Add focused regression tests for generated chain shape if still needed.
2. Document or implement the generic stale-running policy without interrupt
   intent.
3. Add richer retry evidence / TaskAttempt UI only if Product 1.1 needs it.
4. Preserve explicit non-linear tree support.

Do not implement automatic retry policy in this slice.
Do not rewrite Main Page UI unless a concrete Product 1.1 acceptance need is
accepted first.

Output:
- files changed
- tests run
- remaining follow-up hardening gaps
```
