# Feature Plan: Runtime Input Router Contract

> Status: in_progress / RIR-1-RIR-2 implemented
>
> Last Updated: 2026-06-14
>
> Owner: Product / Backend UI Gateway / Frontend
>
> Related:
> [Plato Runtime Input Model](../../product/plato-runtime-input-model.md),
> [Plato Contract Loop Product Model](../../product/plato-contract-loop-model.md),
> [Contract Revision And Execution Loops](../../architecture/contract-revision-and-execution-loops.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md),
> [Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md),
> [Runtime Input Router Technical Design](runtime-input-router-contract-technical-design.md),
> [Runtime Input Router API Contract](../../engineering/runtime-input-router-api-contract.md)

---

## 1. Gap

The Main Page has a natural-language input surface, and Product 1.0 has
separate ASK, confirmation, guidance-like session input, and task input paths.
Product 1.1 needs a single Runtime Input Router contract so one input can be
classified and dispatched without turning chat into an unrestricted Agent loop.

---

## 2. Target

Router entrypoint:

```text
user input + selected scope + active interaction state
  -> route decision
  -> one primary dispatch
  -> activity record
```

Supported first intents:

- read-only question;
- guidance;
- command;
- ASK answer;
- confirmation response;
- workspace-changing execution request.

The Router is the Contract Revision Loop entrypoint. It does not directly write
workspace files.

First Product 1.1 implementation target:

- additive Router API/command contract;
- deterministic routing for active ASK, active confirmation, selected scope,
  and safe command phrases;
- no LLM-only mutation;
- no direct workspace execution;
- typed Activity projection for every accepted decision;
- explicit unsupported/clarification result for unsupported question, guidance,
  command, or execution routes.

---

## 3. Router Tool Classes

Read-only interpretation tools may compose:

- classify intent;
- resolve selected scope;
- detect active ASK;
- detect active confirmation;
- detect deterministic command phrases;
- classify side-effect risk;
- detect ambiguity.

Side-effect tools must be command-backed:

- record guidance;
- resolve ASK;
- resolve confirmation;
- create execution task request;
- later: patch/create/delete TaskNode.

---

## 4. Dispatch Policy

Default rule:

```text
one user input -> one primary side effect
```

Routing priority:

1. active ASK / confirmation if the answer shape matches;
2. deterministic command phrase;
3. selected scope;
4. LLM classification for ambiguous input;
5. safe fallback to read-only question or clarification.

Low-confidence routes must not mutate Plan, TaskBus, or workspace.

---

## 5. Implementation Slices

### RIR-0. Plan And Technical Design Closure

Status: accepted.

- Update this plan with first-version implementation boundaries.
- Add
  [Runtime Input Router Technical Design](runtime-input-router-contract-technical-design.md).
- Mark Activity Timeline as a dependency that is now available for Router
  decision display and traceability.
- Close first-version endpoint, persistence, deterministic command, and
  unsupported-question decisions.

Acceptance:

- The technical design is accepted for RIR-1/RIR-2 implementation.
- Implementation remains limited to additive contract and deterministic Router
  foundation.
- LLM classification, default LLM-backed inquiry answer enablement, guidance
  persistence, Plan/TaskNode mutation commands, and execution handoff remain
  deferred.

### RIR-1. Contract And Fixtures

Status: implemented.

- Define request/response contract.
- Define route decision shape:
  - intent;
  - scope;
  - confidence;
  - side-effect class;
  - dispatch target;
  - explanation;
  - activity payload.
- Add backend/frontend fixture coverage.
- Add API contract notes before UI wiring.

Acceptance:

- `RuntimeInputRouteRequest`, `RuntimeInputRouteResult`, and `RouteDecision`
  are typed on backend and frontend;
- low-confidence and unsupported routes return non-mutating results;
- no existing Product 1.0 command path is removed.

### RIR-2. Deterministic Router Foundation

Status: implemented.

- Implement active ASK / confirmation detection.
- Implement selected scope resolver.
- Implement deterministic command phrase matcher for safe known commands.
- Return one primary route decision and no side effects outside accepted command
  handlers.

Implemented boundaries:

- `POST /api/v1/sessions/{sessionId}/runtime-input/route`;
- workspace-scoped alias through the existing multi-workspace route, with
  opaque `workspaceId` propagated to Read-Only Inquiry for safe evidence links;
- backend/frontend contract models plus unsupported and answered-question JSON
  fixtures;
- deterministic active ASK answer and active confirmation yes/no dispatch;
- deterministic selected-task stop/retry dispatch;
- read-only question dispatch to the Read-Only Inquiry backend foundation when
  session context is available;
- non-mutating unsupported responses for deferred guidance, publish, cancel,
  Plan/TaskNode mutation, workspace-changing request routes, and unavailable
  Inquiry.

### RIR-3. Guidance And Question Routes

Status: partially implemented.

- Route read-only question to the accepted Read-Only Inquiry Context. Backend
  foundation plus transient Main Page question-route Activity display are
  implemented, and answered questions now persist to durable Activity through
  MessageStream; explicit Inquiry refs and workspace-scoped file/diff/Audit
  href context are implemented; Audit evidence `recordId + evidenceId` focus
  wiring is implemented with focused tests; real sidecar acceptance covers the
  no-mutation question route including Audit evidence focused refs; diagnostic
  route links, Audit evidence Electron acceptance, and Electron acceptance
  remain open.
- Route guidance to command-backed guidance recording.
- Display the resulting answer/guidance Activity in the Main Page conversation
  surface.
- Until guidance commands exist, guidance routes must keep returning structured
  unsupported or clarification results rather than inventing hidden behavior.

Dependencies:

- [Read-Only Inquiry Context](read-only-inquiry-context.md) for no-mutation
  answer generation, evidence refs, truncation/disclosure metadata, and
  no-mutation tests.
- [Contract Revision Command Skills](contract-revision-command-skills.md) for
  `record_guidance`.

### RIR-4. Execution Request Handoff

Status: planned.

- Route workspace-changing requests to create or update executable Task/TaskNode
  contract.
- Do not run tools directly.
- Defer actual workspace mutation to TaskBus execution.

Dependencies:

- `create_execution_task` command skill.
- Plan/TaskNode mutation command policy for new follow-up work and active Plan
  edits.
- Explicit confirmation policy for high-risk or ambiguous workspace-changing
  requests.

### RIR-5. Frontend Feedback

Status: planned.

- Show concise interpretation for side-effecting input.
- Keep pure answers lightweight.
- Write activity records for routed input.
- Migrate the Main Page input submit path to call Runtime Input Router by
  default.
- Preserve explicit ASK and confirmation UI while allowing the same input
  surface to answer the active interaction.
- Add localized Router outcome copy and mode hints through the UI system text
  registry.

### RIR-6. Durable Router Session Content

Status: planned.

- Persist Router decisions and user-visible outcomes as typed Session content
  or equivalent durable facts.
- Stop treating the route-result `activity` item as the only display source.
- Preserve command/message/store sources as the product-state authority.
- Support Conversation / Activity replay after reload and diagnostics export.

### RIR-7. Ambiguous Intent Classification

Status: planned.

- Add a bounded classifier for ambiguous natural-language input.
- Keep deterministic routes first and command-backed side effects mandatory.
- Apply confidence thresholds and clarification fallback.
- Do not let LLM classification directly mutate Plan, TaskBus, or workspace.

### RIR-8. Audit, Diagnostics, And Acceptance

Status: planned.

- Link Router decisions to downstream command, Activity, Audit, and diagnostic
  refs.
- Add redacted diagnostic bundle descriptors for routed input without exposing
  raw prompt, provider, tool, log, SQLite, or absolute workspace payloads.
- Add real sidecar/Electron acceptance covering question, guidance, ASK,
  confirmation, stop/retry, unsupported execution request, and no-mutation
  guarantees.

---

## 6. Program Dependencies

Runtime Input Router is not product-complete after RIR-1/RIR-2. The current
implementation proves only the additive Router contract and deterministic
foundation.

The cross-feature dependency map, implementation order, and product-complete
closure criteria are maintained in
[Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md).
This plan owns only Router-specific slices and boundaries.

---

## 7. Non-Goals

- No direct workspace writes.
- No general-purpose autonomous Router Agent.
- No broad natural language command language.
- No prompt-only state mutation.
- No replacement for ASK or confirmation lifecycle.
- No LLM classifier in the first deterministic foundation slice.
