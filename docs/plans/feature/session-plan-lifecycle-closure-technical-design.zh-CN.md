# Session Plan Lifecycle Closure Technical Design

> Status: implemented for Product 1.0 minimal slice
>
> Last Updated: 2026-06-20
>
> Scope: Product 1.0 minimal backend/frontend closure for a completed Plan
> inside one Session. This document covers manual `Archive plan`, active-work
> clearing, minimal history projection, and context-governance constraints. It
> does not implement full Plan finalization agents, rich historical Plan
> browser, or cross-session baseline export.
>
> Related:
> [Plato Session Active Work Lifecycle](../../product/plato-session-active-work-lifecycle.md),
> [Plato Plan Cycle Semantics](../../product/plato-plan-cycle-semantics.md),
> [Plato Session Content Model](../../product/plato-session-content-model.md),
> [Plato UI API Contract](../../product/plato-ui-api-contract.md),
> [UI And Backend Communication](../../architecture/ui-backend-communication.md)

## 1. Problem

当前 Session 可以产生 Plan / TaskNode，并通过 TaskBus 推进 TaskNode 状态。
但 Plan 完成后的闭环不完整：

- completed Plan 还没有明确的用户控制动作把它移出 active work；
- active Plan 清空、历史 Plan 查询、Conversation 连续性没有形成端到端行为；
- Main Page 还无法稳定表达“这个 Plan 已完成，用户可以归档并开始下一轮工作”；
- Context Manager 后续策略需要知道 archived Plan 只是 compact evidence，不是新的 active objective。

## 2. Product Decision

Product 1.0 采用手动归档：

```text
Plan running/completed
  -> completed Plan remains active
  -> user clicks Archive plan
  -> Plan status = archived, archived_at set
  -> no active Plan in Main Page snapshot
  -> Conversation remains visible
  -> archived Plan is reachable from Session history
```

按钮文案使用：

```text
Archive plan
```

不使用 `Finish`，因为系统完成和用户归档是两个不同动作。

## 3. Minimal State Model

### 3.1 Current Plan Model

`Plan` already has:

- `status`
- `version`
- `outcome`
- `archived_at`

Product 1.0 minimal archive does not add a new table.

### 3.2 Archive Command Rule

`archive_plan(session_id, plan_id)`:

- requires the Plan belongs to `session_id`;
- rejects if Plan is already archived;
- rejects if Plan is in `draft`, `reviewing`, `approved`, `published`, or
  `running`;
- accepts `awaiting_acceptance`, `accepted`, `follow_up_needed`, `failed`, and
  `cancelled` as archiveable terminal/review states;
- writes `status="archived"`, `archived_at=now`, increments `version`;
- emits a session-visible activity/message boundary: `Plan archived: <title>`;
- returns refresh hints for `session.snapshot`, `session.activity`, and
  `plans.history`.

The implementation treats current-code `awaiting_acceptance` as the Product
1.0 completed/review-ready Plan state until the Plan status vocabulary is fully
normalized.

### 3.3 Active Work Rule

`PlanStore.get_active_plan(session_id)` already ignores `status='archived'`
and `archived_at IS NOT NULL`. After archive, Main Page snapshot must return:

```text
activePlan = null
taskTree = null or compatibility projection cleared
input scope = Session
```

Conversation is not cleared.

## 4. API Contract Delta

### 4.1 Command

```text
POST /api/v1/sessions/{session_id}/plans/{plan_id}/archive
```

Request:

```json
{
  "commandId": "archive-plan-...",
  "reason": "user requested archive"
}
```

Response:

```json
{
  "requestId": "...",
  "ok": true,
  "result": {
    "commandId": "...",
    "status": "accepted",
    "message": "Plan archived.",
    "affectedTaskRefs": [],
    "objectRefs": [
      {"kind": "plan", "id": "plan-id"}
    ]
  },
  "refresh": {
    "suggestedQueries": [
      "session.snapshot",
      "session.activity",
      "plans.history"
    ]
  }
}
```

Rejected cases use existing `command_rejected` envelope semantics.

### 4.2 Query

Product 1.0 minimal can use one of these:

1. include compact archived Plan summaries in `MainPageSnapshot`;
2. add `GET /api/v1/sessions/{session_id}/plans`;
3. defer rich history query and only rely on Conversation boundary item.

Implementation order:

- C1 backend command and active snapshot clearing;
- C2 compact history projection if needed by frontend;
- C3 rich read-only archived Plan detail later.

## 5. Backend Implementation Slices

### C1. PlanStore Archive API

- Add `archive_plan(session_id, plan_id, *, expected_version=None)` to
  `PlanStore`.
- Implement in `SqlitePlanStore`.
- Keep `get_active_plan` behavior unchanged, but add tests proving archived
  Plans disappear from active reads.

### C2. Command Service

- Add a small `PlanLifecycleCommandService`.
- The service owns archive validation, message/activity boundary emission, and
  command result construction.
- Do not add broad behavior directly to `main_page.py` or
  `ui_contract/gateways.py`; those files should only wire the service.

### C3. HTTP / Gateway Wiring

- Add `archivePlan` command to the UI command gateway or a thin route handler.
- Add HTTP route:
  `POST /api/v1/sessions/{session_id}/plans/{plan_id}/archive`.
- Emit `plan.archived` / `session.activity.updated` style UI event if the
  current event projection supports it; otherwise return refresh hints and let
  snapshot re-query close the loop.

### C4. Frontend Control

- Show `Archive plan` only when active Plan is archiveable.
- Disable during command submission.
- On success, re-query snapshot.
- On failure, show command error.

### C5. Minimal History Entry

- Add Session-level entry point only after archive command works.
- Product 1.0 acceptable fallback: Conversation boundary item plus Activity
  entry. Rich Plan history drawer can be follow-up.

## 6. Frontend Projection Rules

When `activePlan == null`:

- center topbar still shows Conversation;
- Plan floating control is hidden or shows no active plan;
- input scope is Session;
- user can ask read-only question, create Direct Task, or request a new Plan.

When `activePlan.status` is completed/review/terminal:

- Plan remains visible;
- `Archive plan` appears in Plan controls;
- user may still ask about the result before archive.

## 7. Context Manager Rules

Archive does not delete context. It changes default inclusion:

- active Plan facts are included while Plan is active;
- archived Plan summary may be included only as compact historical context;
- full archived Plan messages/tasks/results are retrieved only when the user
  explicitly references them.

No Product 1.0 implementation is required beyond preserving enough Plan facts
and not treating archived Plan as active work.

## 8. Acceptance Criteria

1. A completed/review Plan can be manually archived.
2. An archived Plan has `status="archived"` and non-null `archived_at`.
3. `get_active_plan(session_id)` no longer returns the archived Plan.
4. Main Page snapshot no longer exposes the archived Plan as active work.
5. Conversation is unchanged except for an archive boundary/activity item.
6. Repeated archive command is rejected or idempotently reported without
   mutating the Plan again.
7. Non-terminal active Plans cannot be archived.
8. Existing TaskBus/TaskNode lifecycle tests continue to pass.

## 9. Non-goals

- No automatic Plan archive.
- No full historical Plan browser in C1.
- No Plan finalization Agent.
- No result packaging cards.
- No cross-session Project baseline export.
- No Context Manager retrieval implementation for archived Plans beyond
  preserving the policy boundary.
