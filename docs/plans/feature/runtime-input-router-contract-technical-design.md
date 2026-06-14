# Runtime Input Router Contract Technical Design

> Status: accepted / RIR-1-RIR-2 implemented
>
> Last Updated: 2026-06-14
>
> Owner: Product / Backend UI Gateway / Frontend
>
> Related:
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md),
> [Plato Runtime Input Model](../../product/plato-runtime-input-model.md),
> [Contract Revision And Execution Loops](../../architecture/contract-revision-and-execution-loops.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md),
> [Contract Revision Command Skills](contract-revision-command-skills.md)

---

## 1. Purpose

Runtime Input Router is the Product 1.1 entrypoint for the Main Page natural
language input. Its job is to decide what the user meant before any product or
workspace state changes happen.

The Router is not a chat agent and not an execution agent. It belongs to the
Contract Revision Loop. It may call read-only interpretation helpers and
command-backed product-state capabilities, but it must not write workspace files
or run workspace commands.

---

## 2. First-Version Scope

RIR-1/RIR-2 implement only the deterministic foundation:

- request/response and `RouteDecision` contracts;
- selected Session/Plan/Task scope resolution;
- active ASK detection;
- active confirmation detection;
- safe deterministic command phrase detection for existing commands;
- structured unsupported/clarification results for unsupported routes;
- activity metadata for every accepted route decision.

Implementation status:

- RIR-1 contract models, frontend types, API client method, backend/frontend
  fixtures, and API contract notes are implemented.
- RIR-2 deterministic Router service and HTTP route are implemented for active
  ASK answer, active confirmation yes/no, selected-task stop, selected-task
  retry, and structured unsupported/clarification outcomes.
- The question route now dispatches to the Read-Only Inquiry backend foundation
  when session context is available and returns `inquiryResult` plus
  `sideEffect=no_effect`.

Deferred:

- LLM-based ambiguous classification;
- default Router/runtime enablement of LLM-backed read-only inquiry answers;
- guidance persistence if the command-backed guidance store is not ready;
- Plan/TaskNode patch/create/delete commands;
- workspace-changing execution request creation;
- durable Router decision/session content persistence;
- Main Page default input migration;
- Audit/diagnostic linkage for Router decisions;
- full frontend mode override menu.

---

## 3. Core Contract

### 3.1 Request

```ts
type RuntimeInputRouteRequest = {
  commandId: string;
  sessionId: SessionId;
  workspaceId?: WorkspaceId | null;
  content: string;
  mode?: "auto" | "ask" | "guide" | "change";
  selection: {
    scopeKind: "session" | "plan" | "task";
    planId?: PlanId | null;
    taskNodeId?: TaskNodeId | null;
    refs?: ObjectRef[];
  };
  inquiryRefs?: ReadOnlyInquiryRef[];
  clientState?: {
    activeAskId?: AskId | null;
    activeConfirmationId?: ConfirmationId | null;
  };
};
```

Rules:

- `content` is user-visible text, not a prompt transcript.
- `mode=auto` is the default.
- `workspaceId` is an optional opaque id injected by workspace-scoped routes
  and used only for safe downstream evidence links.
- `inquiryRefs` is optional and applies only to the
  `question/no_effect/read_only_inquiry` route. It carries explicit
  `ReadOnlyInquiryRef` anchors already known to the UI, such as file, diff,
  Audit, diagnostic, result, and Activity refs.
- Router may translate safe `selection.refs` into Inquiry refs, but explicit
  `inquiryRefs` must be preserved and merged for the read-only question route.
- `inquiryRefs` must be ignored for mutating dispatch targets and cannot
  authorize guidance, Plan/TaskNode mutation, TaskBus work, or workspace writes.
- `clientState` is a hint only. Backend projection remains authoritative for
  active ASK and confirmation state.
- File, diff, audit, result, message, ASK, and confirmation refs are references,
  not primary collaboration scopes.

### 3.2 Response

```ts
type RuntimeInputRouteResult = {
  sessionId: SessionId;
  decision: RouteDecision;
  outcome: RuntimeInputOutcome;
  activity?: SessionActivityItemView | null;
  commandResponse?: CommandResponse | null;
  inquiryResult?: ReadOnlyInquiryResult | null;
  generatedAt: string;
};
```

`commandResponse` is present only when the Router dispatches an existing
command-backed product-state operation. `inquiryResult` is present only when the
Router dispatches to Read-Only Inquiry. Unsupported and clarification routes
return no command response.

### 3.3 Route Decision

```ts
type RouteDecision = {
  id: string;
  intent:
    | "question"
    | "guidance"
    | "command"
    | "ask_answer"
    | "confirmation_response"
    | "execution_request"
    | "clarification"
    | "unsupported";
  scope: {
    kind: "session" | "plan" | "task";
    planId?: PlanId | null;
    taskNodeId?: TaskNodeId | null;
  };
  confidence: "high" | "medium" | "low";
  sideEffect:
    | "no_effect"
    | "context_effect"
    | "state_effect"
    | "authorization_effect"
    | "resume_effect"
    | "execution_request";
  dispatchTarget:
    | "read_only_inquiry"
    | "record_guidance"
    | "resolve_ask"
    | "resolve_confirmation"
    | "existing_command"
    | "execution_handoff"
    | "clarification"
    | "unsupported";
  explanation: string;
  relatedRefs: SessionActivityRefView[];
};
```

The decision is user-traceable. It must be concise and safe to expose through
Activity Timeline.

### 3.4 Outcome

```ts
type RuntimeInputOutcome = {
  status:
    | "dispatched"
    | "answered"
    | "needs_clarification"
    | "unsupported"
    | "rejected";
  userMessage: string;
  recoveryActions?: ProductRecoveryAction[];
};
```

First version should prefer `unsupported` over speculative behavior when a
required downstream capability does not exist.

---

## 4. Routing Policy

The Router executes in this order:

1. Normalize input and reject empty or unsafe oversized content.
2. Resolve authoritative active ASK and confirmation state.
3. If an active ASK answer shape matches, route `ask_answer`.
4. If an active confirmation response shape matches, route
   `confirmation_response`.
5. Apply deterministic command phrase rules for existing safe commands.
6. Resolve selected scope from backend state and client selection.
7. Apply explicit mode override if present.
8. Return unsupported/clarification for low-confidence or deferred
   capabilities.

Default invariant:

```text
one user input -> one primary side effect
```

Multiple read-only interpretation steps are allowed. Multiple side effects are
not allowed in RIR-1/RIR-2.

---

## 5. Dispatch Semantics

| Intent | First-version dispatch | Side effect |
|---|---|---|
| Question | Read-Only Inquiry backend foundation when context exists; unsupported fallback otherwise | `no_effect` |
| Guidance | Unsupported until guidance command exists | `context_effect` |
| Existing command | Existing command handler if deterministic and valid | `state_effect` |
| ASK answer | Existing ASK answer command | `resume_effect` |
| Confirmation response | Existing confirmation resolve command | `authorization_effect` |
| Execution request | Unsupported until execution handoff exists | `execution_request` |

No Router path may directly:

- mutate Plan/TaskNode without a command;
- write workspace files;
- run shell commands;
- bypass ASK or confirmation lifecycle validation;
- dispatch a low-confidence side effect.

---

## 6. Activity And Audit Semantics

Every accepted Router decision should produce Activity metadata.

First implementation options:

1. If the dispatch target already creates a safe projection source, Activity
   should project from that source.
2. If no source exists, Router may return an `activity` item in the route
   result as a display projection, but this item must not become source of truth
   for product state.

Required Activity rules:

- `router_interpretation` records the interpreted intent and scope.
- `guidance_recorded`, `ask_answered`, and `confirmation_resolved` are emitted
  only after corresponding command success.
- Unsupported and clarification routes may produce an `execution_update` or
  `recovery_note` item when useful.
- Raw prompts, provider payloads, raw tool args, EventStream rows, SQLite rows,
  secrets, and absolute workspace paths remain prohibited.

Audit remains separate. Router Activity explains the user-facing consequence;
Audit records command facts and evidence where available.

---

## 7. Backend Components

Planned components:

- `RuntimeInputRouter`: orchestration service.
- `RuntimeInputScopeResolver`: resolves Session/Plan/Task scope from backend
  state.
- `RuntimeInputActiveInteractionResolver`: resolves ASK and confirmation state.
- `RuntimeInputDeterministicClassifier`: handles explicit answer/confirmation
  shapes and known command phrases.
- `RuntimeInputDispatcher`: calls existing command gateways when a deterministic
  route is allowed.
- `RuntimeInputActivityProjector`: creates safe Activity metadata.

RIR-1 may add only protocols/models and fixtures. RIR-2 adds deterministic
service implementation without LLM classification.

---

## 8. Program Dependency Reference

This technical design owns the accepted RIR-1/RIR-2 implementation boundary:
request/response contract, deterministic routing, safe unsupported outcomes,
and additive HTTP wiring.

The cross-feature closure map for read-only inquiry, guidance persistence,
Plan/TaskNode command skills, execution handoff, durable Router session content,
ambiguous classification, Audit/diagnostic linkage, and end-to-end acceptance
is maintained in
[Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md).

---

## 9. Frontend Integration

First UI integration should be additive:

- Main Page keeps one input surface.
- Existing explicit ASK and confirmation UI remains.
- Router route result can show concise interpretation copy.
- Activity drawer displays typed Router outcomes through the existing Activity
  Timeline.
- Existing Product 1.0 commands remain available until the Router is accepted
  as the default path.

Do not add full Settings, global prompt tuning, or chat transcript UI in this
slice.

---

## 10. Tests

RIR-1 contract tests:

- request/response JSON fixture round-trip;
- invalid scope rejection;
- unsupported response shape;
- activity metadata redaction.

RIR-2 deterministic tests:

- active ASK answer routes to ASK command;
- active confirmation routes to confirmation command;
- low-confidence text does not mutate state;
- selected task scope is preserved;
- deterministic stop/retry/publish/cancel phrases map only to existing allowed
  commands;
- workspace-changing request returns unsupported until execution handoff exists.

Integration tests:

- Main Page submit can call Router without breaking existing input state;
- Activity Timeline can display `router_interpretation`;
- legacy Product 1.0 command paths still work during migration.

Program-level closure acceptance is maintained in
[Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md).

---

## 11. Acceptance Criteria For Implementation Start

Implementation may start from RIR-1/RIR-2 after this RIR-0 closure.

Minimum accepted implementation scope:

- RIR-1 models, API contract, fixtures, and tests;
- RIR-2 deterministic service with no LLM classifier;
- no direct workspace mutation;
- no speculative read-only inquiry answer generation beyond the accepted
  Read-Only Inquiry backend service;
- no Plan/TaskNode mutation commands except existing command-backed operations;
- Activity metadata for every dispatched or rejected decision.

Current implementation evidence:

- `RuntimeInputRouteRequest`, `RuntimeInputRouteResult`, and
  `RuntimeInputRouteDecision` are implemented in backend and frontend types.
- `POST /api/v1/sessions/{sessionId}/runtime-input/route` is implemented as an
  additive route.
- Unsupported and clarification outcomes are successful non-mutating query
  responses.
- Question outcomes dispatch to Read-Only Inquiry when session context is
  available and otherwise fall back to non-mutating unsupported.
- Deterministic command-backed dispatch is limited to active ASK,
  confirmation, selected-task stop, and selected-task retry.

---

## 12. RIR-0 Closure Decisions

### Endpoint

Use an additive Router endpoint:

```text
POST /api/v1/sessions/{sessionId}/runtime-input/route
```

The endpoint returns `RuntimeInputRouteResult`. If the Router dispatches an
existing command-backed operation, the result may include the downstream
`CommandResponse`. It must not reuse the existing command endpoint as the
primary public contract because routing is an interpretation step before any
command side effect.

### Decision Persistence

RIR-1/RIR-2 do not add a durable Router decision store. Route decisions are
returned as safe Activity metadata and may be displayed in the Activity
Timeline. Product-state facts still come from existing command/message/store
sources. Durable typed Session content remains a later Session Content
Management slice.

### Deterministic Command Phrases

RIR-2 supports only narrow deterministic command phrases that map to existing
safe command handlers. The accepted starting set is:

- stop selected task;
- retry selected task.

Publish, cancel, Plan/TaskNode create/delete, guidance mutation, and
workspace-changing requests are deferred until command-backed contract revision
skills define explicit permission, audit, and recovery semantics.

### Unsupported Question UX

Question-like inputs dispatch to Read-Only Inquiry after active ASK and
confirmation handling. If Inquiry is unavailable, lacks enough context, or
rejects the question under the no-mutation boundary, the Router returns a
concise `unsupported`, `needs_clarification`, or `rejected` outcome with
`no_effect`. It should not enqueue execution or mutate Plan/Task state.

### Implementation Boundary

The accepted implementation start is limited to:

- backend/frontend contract models and fixtures;
- HTTP route shape;
- deterministic Router service plus Read-Only Inquiry backend foundation;
- non-mutating unsupported/clarification outcomes;
- command-backed dispatch only for accepted deterministic paths.

Any LLM classifier, default LLM-backed inquiry enablement, guidance
persistence, Plan/TaskNode mutation, or workspace execution handoff requires
its own accepted slice.
