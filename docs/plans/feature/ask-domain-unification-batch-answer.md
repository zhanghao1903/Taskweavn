# Feature Plan: ASK Domain Unification And Batch Answer

> Status: in progress
> Type: Product 1.0 interaction UX/API alignment
> Last Updated: 2026-06-04
> Related: [Message, ASK, And Confirmation Backend](message-ask-confirmation-backend.md), [ASK Lifecycle Contract](../../engineering/ask-lifecycle-contract.md), [ASK User Interaction](../../interaction-model/ask-user-interaction.md), [ASK UI Spec](../../ux/ask-ui-spec.md), [ASK And Confirmation Frontend Integration](ask-confirmation-frontend-integration.md), [Authoring Domain](../../architecture/authoring-domain.md), [Interaction Layer](../../architecture/interaction-layer.md)
> Technical Design: [ASK domain unification and batch answer technical design](ask-domain-unification-batch-answer-technical-design.zh-CN.md)

---

## 1. Problem

Product 1.0 now has two ASK-like mechanisms:

- Authoring ASK: `RawTaskAsk` asks the user to clarify planning intent before
  a DraftTaskTree is generated.
- Execution ASK: durable `AskRequest` pauses a PublishedTask at
  `waiting_for_user` until the answer is persisted and execution can resume.

They look similar to the user, but they do not have the same backend authority
or lifecycle. If the frontend treats them as one undifferentiated object, it can
resume the wrong pipeline, show the wrong status, or audit the wrong domain.

There is also a UX gap: authoring questions are often related. Once users see
later questions, they may want to revise earlier answers before submitting.
Single-answer commands force premature commitment and make the planning flow
feel fragmented.

---

## 2. Product Decisions

1. ASK visual components may be shared, but ASK domain semantics remain
   explicit.
2. The UI-facing projection must carry a domain discriminator:
   `authoring` or `execution`.
3. Authoring ASK is planning-scoped. It blocks RawTask-to-DraftTaskTree
   generation, not TaskBus execution.
4. Execution ASK is task-scoped. It blocks a PublishedTask through TaskBus
   `waiting_for_user`.
5. Product 1.0 batch answer is required for authoring ASK.
6. Product 1.0 does not require execution multi-ASK groups. The execution
   backend may keep the current single active blocking ASK path.
7. Batch answer submission is all-or-nothing.
8. Duplicate ask ids in one batch are rejected.
9. Already answered ASK objects reject new non-idempotent answers.
10. Frontend draft answer state is local until the batch command succeeds.

---

## 3. Goals

- Make authoring and execution ASK differences explicit in product docs and API
  design.
- Define a shared UI projection vocabulary without merging the backend sources
  of truth.
- Add Product 1.0 authoring batch answer backend support.
- Preserve current execution ASK answer/defer/cancel behavior.
- Keep future execution ASK grouping possible without introducing it into the
  1.0 runtime loop prematurely.

---

## 4. Non-goals

- No full frontend ASK Dock in this slice.
- No merging `RawTaskAsk` into durable execution `AskStore`.
- No making MessageStream the ASK state authority.
- No execution `ask_group_id` runtime generation in Product 1.0 minimal.
- No editing historical answers after a successful batch submit.
- No multimodal or attachment answers.
- No complex recovery strategy beyond durable facts and idempotent commands.

---

## 5. Domain Model Alignment

| Field | Authoring ASK | Execution ASK |
|---|---|---|
| UI domain | `authoring` | `execution` |
| Scope | planning / RawTask | PublishedTask / TaskNode |
| Source of truth | RawTask store | ASK store |
| Blocking target | Task authoring pipeline | TaskBus execution lifecycle |
| Answer command | RawTask ask batch answer | execution ASK answer |
| After answer | generate or update DraftTaskTree | resume waiting task |
| Terminal failure | planning cannot proceed / user cancels planning | task failed/deferred/cancelled |
| TaskNode status | unchanged | `waiting_user` projection |

---

## 6. Product 1.0 Scope

### In Scope

- Docs-only domain alignment.
- Authoring batch answer backend command:
  - accepts multiple `{ask_id, value}` answers for one RawTask;
  - writes answers atomically through one authoring command batch;
  - rejects duplicate ask ids in the payload;
  - rejects already answered asks unless replayed by idempotency key;
  - emits one user message describing the submitted answer batch.
- Tests for authoring batch answer success, duplicate payload rejection, and
  already answered rejection.

### Out Of Scope

- Execution multi-ASK group runtime behavior.
- Frontend local answer draft state.
- New planning panel UI.
- Main Page snapshot planning state redesign.

---

## 7. Implementation Slices

### C1 Docs Alignment - done

- Add this feature plan.
- Add the Chinese technical design.
- Link the plan from the feature plan index.

### C2 Authoring Batch Answer Backend - done

- Add an authoring batch answer adapter method.
- Add UI contract payload types for authoring batch answers.
- Add a command gateway method for authoring batch answers.
- Keep all-or-nothing behavior in `AuthoringCommandService`.
- Add duplicate-answer validation at the RawTask operation boundary.

### C3 HTTP/API Entry Point - done

- Add a sidecar route for authoring batch answer.
- Return normal `CommandResponse` with `authoring` object refs and refresh
  hints.

### C4 Projection Follow-up

- Define or implement planning ASK projection when the Main Page is ready to
  show authoring questions as first-class UI facts.

### C5 Frontend Follow-up

- UI spec: done in `docs/ux/ask-ui-spec.md`.
- Add local draft answer state and one submit action in the ASK panel.
- Use the same visual component for both domains while keeping labels and
  commands domain-specific.

---

## 8. Acceptance Criteria

- Docs distinguish authoring ASK from execution ASK.
- Authoring batch answer command can answer multiple pending RawTaskAsk objects
  in one accepted request.
- Reusing an idempotency key replays the same accepted command response.
- Duplicate ask ids in one request are rejected.
- A new answer to an already answered RawTaskAsk is rejected.
- Existing single authoring answer behavior remains compatible.
- Existing execution ASK tests continue to pass.
