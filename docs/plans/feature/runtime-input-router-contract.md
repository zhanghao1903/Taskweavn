# Feature Plan: Runtime Input Router Contract

> Status: planned
>
> Last Updated: 2026-06-13
>
> Owner: Product / Backend UI Gateway / Frontend
>
> Related:
> [Plato Runtime Input Model](../../product/plato-runtime-input-model.md),
> [Plato Contract Loop Product Model](../../product/plato-contract-loop-model.md),
> [Contract Revision And Execution Loops](../../architecture/contract-revision-and-execution-loops.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md)

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

### RIR-1. Contract And Fixtures

- Define request/response contract.
- Define route decision shape:
  - intent;
  - scope;
  - confidence;
  - side-effect class;
  - dispatch target;
  - explanation;
  - activity payload.

### RIR-2. Deterministic Router Foundation

- Implement active ASK / confirmation detection.
- Implement selected scope resolver.
- Implement deterministic command phrase matcher for safe known commands.

### RIR-3. Guidance And Question Routes

- Route read-only question to inquiry placeholder or unsupported response.
- Route guidance to command-backed guidance recording.

### RIR-4. Execution Request Handoff

- Route workspace-changing requests to create or update executable Task/TaskNode
  contract.
- Do not run tools directly.

### RIR-5. Frontend Feedback

- Show concise interpretation for side-effecting input.
- Keep pure answers lightweight.
- Write activity records for routed input.

---

## 6. Non-Goals

- No direct workspace writes.
- No general-purpose autonomous Router Agent.
- No broad natural language command language.
- No prompt-only state mutation.
- No replacement for ASK or confirmation lifecycle.
