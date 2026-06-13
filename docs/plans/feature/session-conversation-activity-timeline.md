# Feature Plan: Session Conversation / Activity Timeline

> Status: planned
>
> Last Updated: 2026-06-13
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

---

## 4. Implementation Slices

### SAT-1. Product And Contract Model

- Define Activity item view model.
- Define allowed item classes, refs, and disclosure rules.
- Add fixtures for English and Chinese text.

### SAT-2. Backend Projection

- Project activity from MessageStream, Plan/Task facts, ASK/confirmation facts,
  result/file summaries, and Router outcomes.
- Do not expose raw prompts, provider payloads, raw tool arguments,
  EventStream rows, or SQLite rows.

### SAT-3. Frontend Surface

- Keep Main Page work-first.
- Show Latest Activity summary.
- Add full Conversation / Activity drawer or route.
- Preserve selected Plan/Task state when opening/closing.

### SAT-4. Router Integration

- Runtime Input Router outcomes create activity records:
  - interpreted intent;
  - affected scope;
  - side-effect class;
  - related refs.

### SAT-5. Tests

- Activity projection contract tests.
- Frontend tests for empty, loading, populated, and linked item states.
- Redaction tests for raw prompt/tool/log payloads.

---

## 5. Non-Goals

- No chat-first Main Page.
- No raw transcript default view.
- No Audit replacement.
- No full log browser.
- No provider or prompt disclosure.
