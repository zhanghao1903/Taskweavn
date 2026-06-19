# Feature Plan: Session Conversation / Activity Timeline

> Status: accepted
>
> Last Updated: 2026-06-14
>
> Owner: Product / Frontend / Backend UI Contract
>
> Decision:
> [ADR-0019 Session Conversation And Activity Boundary](../../decisions/ADR-0019-session-conversation-activity-boundary.md)
>
> Related:
> [Plato Session Content Model](../../product/plato-session-content-model.md),
> [Plato Contract Loop Product Model](../../product/plato-contract-loop-model.md),
> [UI/backend communication](../../architecture/ui-backend-communication.md)

---

## 1. Gap

Plato currently has Latest Activity surfaces and message/event substrates, but
does not yet have a formal typed Session Conversation / Activity timeline.

The target product model says the user needs to review:

```text
what I told Plato
how Plato interpreted it
what consequence it had
where to inspect related work or evidence
```

Without this, Runtime Input Router outcomes will feel like a black box.

---

## 2. Target

Session owns a typed Conversation / Activity timeline.

Main Page remains work-first. It exposes:

- Latest Activity as a lightweight entry;
- full Conversation / Activity as a drawer or secondary route;
- links from timeline items to Plan, Task, result, file, Audit, or diagnostic
  refs.

The timeline is not raw MessageStream rendering.

---

## 3. Activity Item Classes

First supported classes:

- user input;
- answer;
- guidance recorded;
- Plan updated;
- Task created / changed / removed;
- ASK asked / answered;
- confirmation requested / resolved;
- execution update;
- result ready;
- file summary;
- recovery note.

Each item should carry:

- user-readable title;
- concise body;
- timestamp;
- scope: Session, Plan, or Task;
- interpreted effect when applicable;
- related refs;
- safe disclosure level.

### 3.1 SAT-1 Contract

First backend contract:

```http
GET /api/v1/sessions/{sessionId}/activity?limit=50&cursor=...
```

Response data:

```ts
type SessionActivityTimelineResult = {
  sessionId: string;
  items: SessionActivityItemView[];
  nextCursor: string | null;
  totalCount: number;
  generatedAt: string;
};
```

`SessionActivityItemView` contains:

- stable `id`;
- `kind` from the supported Activity item classes;
- user-readable `title` and concise `body`;
- `occurredAt`;
- `scopeKind`: `session`, `plan`, or `task`;
- optional `planId` and `taskNodeId`;
- `sideEffect`: `no_effect`, `context_effect`, `state_effect`,
  `authorization_effect`, `resume_effect`, `execution_request`, or
  `evidence_effect`;
- related safe refs for plan/task/message/ASK/confirmation/result/file/Audit;
- `sourceKind` and optional `sourceId`;
- `disclosureLevel`: `public`, `partial`, or `hidden`.

The first endpoint returns newest-first items and offset-style `nextCursor`.
It is intentionally separate from `MainPageSnapshot`; SAT-3 owns the frontend
drawer or secondary route.

### 3.2 SAT-2 Backend Projection

First projection sources:

| Source | Activity |
|---|---|
| MessageStream / task messages | user input, answer, execution update, recovery note, confirmation requested |
| PlanView / TaskNode facts | plan updated, task created/changed, execution update, recovery note |
| ASK projection | ASK asked |
| confirmation projection | confirmation requested |
| ResultCardView | result ready |
| FileChangeSummaryView | file summary |

Reserved but not produced until Runtime Input Router:

- `router_interpretation`;
- `guidance_recorded`;
- `confirmation_resolved`;
- `ask_answered`.

Projection rules:

- no raw provider payloads, prompts, raw EventStream rows, tool arguments,
  SQLite rows, secrets, or absolute workspace paths;
- Activity explains product facts but does not own state;
- if Activity conflicts with Plan, TaskBus, ASK, confirmation, result, file, or
  Audit facts, canonical facts win.

---

## 4. Implementation Slices

### SAT-1. Product And Contract Model

Status: implemented.

- Defined `SessionActivityTimelineResult`, `SessionActivityItemView`, and
  `SessionActivityRefView`.
- Defined allowed item classes, refs, side-effect classes, source kinds, scope
  rules, and disclosure levels.
- Added frontend/backend contract fixture coverage for the HTTP response shape.
- Bilingual presentation strings remain SAT-3 UI work; SAT-1 only defines the
  typed data contract.

### SAT-2. Backend Projection

Status: implemented backend foundation.

- Project activity from MessageStream, Plan/Task facts, ASK/confirmation facts,
  result/file summaries.
- Do not expose raw prompts, provider payloads, raw tool arguments,
  EventStream rows, or SQLite rows.
- Added `GET /api/v1/sessions/{sessionId}/activity?limit=50&cursor=...`.
- Added frontend API client/types for the query without connecting full UI.
- Router outcomes are reserved for SAT-4 because Runtime Input Router is not
  implemented yet.

### SAT-3. Frontend Surface

Status: implemented.

- Keep Main Page work-first.
- Show Latest Activity summary.
- Add full Conversation / Activity drawer from the existing Latest Activity
  entry.
- Preserve selected Plan/Task state when opening/closing.
- Load typed Activity through the Main Page adapter when the HTTP endpoint is
  available; keep a safe message-to-activity fallback for mock and legacy
  snapshots.
- Cover loading, error, empty, filtered, result-reader, and related-ref action
  states in focused frontend tests.

### SAT-4. Router Integration

Status: deferred to Runtime Input Router.

- Runtime Input Router outcomes create durable typed Conversation content:
  - user input;
  - Router interpretation trace;
  - Router clarification / ASK / confirmation question cards;
  - user answers;
  - Router outcome text.
- Runtime Input Router outcomes create activity records:
  - interpreted intent;
  - affected scope;
  - side-effect class;
  - related refs.
- Conversation rendering must use a backend-declared protocol for text,
  Router trace, and question cards/options. The frontend must not infer
  interactive cards from raw text alone.
- `router_interpretation`, `guidance_recorded`, `confirmation_resolved`, and
  `ask_answered` remain reserved item kinds until the Router writes them.
- This is tracked by
  [Runtime Input Router Contract](runtime-input-router-contract.md), not as a
  blocker for accepting the Activity Timeline surface.

### SAT-5. Tests

Status: implemented for current Activity Timeline scope.

- Implemented Activity projection contract tests.
- Implemented HTTP route and frontend fixture/API client contract tests.
- Implemented frontend overlay tests for empty/loading/error/populated/filter,
  result reader, and related item refs.
- Implemented Main Page Workbench integration coverage for loading typed
  Activity from the adapter.
- Router redaction tests remain with the Runtime Input Router slice.

---

## 5. Non-Goals

- No chat-first Main Page.
- No raw transcript default view.
- No Audit replacement.
- No full log browser.
- No provider or prompt disclosure.
