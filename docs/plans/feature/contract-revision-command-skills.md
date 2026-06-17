# Feature Plan: Contract Revision Command Skills

> Status: implemented for CRS-A, CRS-B, CRS-C, and CRS-D `patch_task_node`;
> planned for TaskNode create/delete and execution handoff
>
> Last Updated: 2026-06-18
>
> Owner: Product / Backend Commands / Authoring Domain / TaskBus
>
> Related:
> [Contract Revision And Execution Loops](../../architecture/contract-revision-and-execution-loops.md),
> [Plato Contract Loop Product Model](../../product/plato-contract-loop-model.md),
> [Product 1.1 Open Work](../../product/plato-1-1-open-work.md),
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md),
> [Plan / TaskNode Contract Migration](plan-tasknode-contract-migration.md)
>
> Technical Design:
> [Contract Revision Command Skills 中文详细技术方案](contract-revision-command-skills-technical-design.zh-CN.md)

---

## 1. Gap

The Contract Revision Loop needs command-backed capabilities for user requests
that change Plato product state:

- record guidance;
- patch TaskNode properties;
- create TaskNode;
- delete TaskNode;
- create workspace-changing execution work;
- resolve ASK or confirmation through the same routed input surface.

Product 1.0 has several separate command paths, but not a unified internal
skill/capability layer for Router-dispatched contract revisions.

---

## 2. Target

Internal command skills expose reusable, auditable product-state operations:

```text
Router decides
  -> command skill validates
  -> command handler persists facts
  -> event + activity projection
```

Workspace-changing requests do not write files. They create or update
executable Plan/TaskNode contract and enter TaskBus after publication or user
confirmation.

---

## 3. Product 1.1 P0 Boundary

This plan is part of the Product 1.1 P0 milestone:

```text
Runtime Input Router
  + Contract Revision Command Skills
  + durable Activity / Audit evidence
```

The command skills are the side-effect boundary for Runtime Input Router.
Router may classify and dispatch, but product-state mutation must happen
through these command-backed skills or existing ASK / confirmation commands.

This first design is intentionally internal. It is not a public skill
marketplace, custom skill authoring system, or external Agent protocol.

---

## 4. Technical Design

### 4.1 Command Skill Flow

```text
Runtime input
  -> Router decision
  -> command skill request
  -> command validation
  -> domain handler
  -> canonical store write
  -> event / Activity / Audit refs
  -> Router result projection
```

Rules:

1. One routed user input produces at most one primary side effect.
2. The command skill validates scope, state, version, and idempotency before any
   store write.
3. The command handler writes canonical product facts. Activity explains those
   facts but does not own them.
4. Workspace files are never changed by this layer. Workspace-changing requests
   create executable contract work for TaskBus.
5. Low-confidence or unsupported routes return a structured rejection or
   clarification result and must not mutate product state.

### 4.2 Shared Command Request Envelope

Implementation names may adapt to existing Python types, but every command
skill should receive this information:

| Field | Required | Meaning |
|---|---:|---|
| `commandId` | yes | Stable id for this command attempt. |
| `idempotencyKey` | yes | Replay key. A repeated command returns the same accepted result or the same rejected terminal result. |
| `workspaceId` | yes | Opaque workspace identity from the UI gateway. |
| `sessionId` | yes | Session that owns the routed input. |
| `planId` | when scoped | Active or target Plan identity. |
| `taskNodeId` | when scoped | Target TaskNode identity. |
| `source` | yes | `runtime_input`, `explicit_ui`, `system_recovery`, or `test_fixture`. |
| `routerDecisionId` | when routed | Link back to the Runtime Input Router decision. |
| `inputMessageRef` | when user-authored | Safe ref to the originating user input, not a raw diagnostic payload. |
| `expectedVersion` | when mutating existing state | Plan, TaskNode, ASK, or confirmation version guard. |
| `scopeKind` | yes | `session`, `plan`, `task`, `ask`, or `confirmation`. |
| `payload` | yes | Command-specific typed payload. |

The envelope must not include raw provider payloads, absolute workspace paths,
tool arguments, logs, SQLite rows, or secrets.

### 4.3 Shared Command Result Shape

Every command returns a typed result that the Router and UI can project without
guessing:

| Field | Required | Meaning |
|---|---:|---|
| `status` | yes | `accepted`, `rejected`, `needs_confirmation`, `conflict`, `noop`, or `unsupported`. |
| `sideEffect` | yes | One of the Activity side-effect classes: `context_effect`, `state_effect`, `authorization_effect`, `resume_effect`, or `execution_request`. |
| `scopeKind` | yes | Scope affected by the command. |
| `planId` / `taskNodeId` | when applicable | Affected Plan or TaskNode. |
| `refs` | yes | Safe refs for Activity, Audit, ASK, confirmation, Plan, Task, or result focus. |
| `activity` | yes for accepted/needs-confirmation | User-visible Activity payload or projection descriptor. |
| `audit` | yes for side effects | Audit/evidence descriptor with redacted metadata. |
| `diagnostics` | optional | Redacted diagnostic descriptor for support exports. |
| `newVersion` | when state changes | Updated version or revision token. |
| `reasonCode` | when not accepted | Stable rejection/conflict/unsupported reason. |
| `messageKey` | when UI-visible | UI system text key, not hardcoded copy. |

Accepted commands must be replay-safe. A replay with the same idempotency key
must not create duplicate TaskNodes, guidance facts, ASK answers, confirmation
resolutions, Activity items, or Audit records.

### 4.4 Canonical Stores And Projection Ownership

| Concern | Canonical owner | Command-skill responsibility |
|---|---|---|
| Guidance facts | Session / Plan / Task context store | Persist typed guidance and expose context inclusion metadata. |
| TaskNode changes | Plan / TaskNode store | Validate allowed Plan state, version, and field-level mutation policy. |
| ASK answers | Existing ASK domain | Delegate to existing ASK command lifecycle and return refs. |
| Confirmation answers | Existing confirmation domain | Delegate to existing confirmation command lifecycle and return refs. |
| Execution handoff | Plan / TaskNode + TaskBus publish/execute path | Create executable contract work; never run workspace tools directly. |
| Activity | Session Activity projection | Emit source facts or projection metadata for durable replay. |
| Audit / diagnostics | Audit and diagnostic surfaces | Emit safe refs and redacted descriptors. |

If Activity conflicts with canonical Plan, TaskBus, ASK, confirmation, result,
file, or Audit facts, canonical facts win.

### 4.5 Command Set

#### CRS-1. `record_guidance`

Purpose: turn user guidance into typed context instead of hidden chat.

Payload:

| Field | Required | Meaning |
|---|---:|---|
| `guidanceText` | yes | User-authored guidance. Stored as product content, redacted/truncated in diagnostics. |
| `guidanceKind` | yes | `preference`, `constraint`, `instruction`, `correction`, or `context_note`. |
| `scopeKind` | yes | `session`, `plan`, or `task`. |
| `planId` | when plan/task scoped | Target Plan. |
| `taskNodeId` | when task scoped | Target TaskNode. |
| `appliesToFutureTasks` | optional | Whether guidance should affect follow-up Task authoring. |
| `expiresAt` | optional | Optional expiry for time-bounded guidance. |

Validation:

- session exists in the selected workspace;
- Plan/Task scope exists when provided;
- guidance text is non-empty after trimming;
- scope matches the current UI selection or explicit Router scope decision;
- duplicate idempotency key returns the original guidance fact.

Effects:

- persist a typed guidance fact;
- expose the fact to Context Manager through bounded inclusion rules;
- create durable Activity item `guidance_recorded`;
- create Audit/diagnostic refs that identify scope and effect without raw
  hidden internals.

Acceptance:

- guidance is visible after reload through Activity;
- later context assembly can include the guidance with scope and truncation
  metadata;
- unsupported or ambiguous guidance routes do not create hidden facts.

#### CRS-2. `patch_task_node`

Purpose: change an existing TaskNode through a versioned contract mutation.

Allowed first fields:

- title;
- intent / instructions;
- constraints;
- acceptance criteria;
- ordering metadata, only when the Plan is still editable;
- non-execution status fields that are legal for the current Plan state.

Validation:

- active Plan and TaskNode exist;
- expected Plan/TaskNode version matches;
- Plan state allows edits;
- running, completed, or externally blocked Tasks require explicit policy;
- destructive or high-impact changes may return `needs_confirmation`.

Effects:

- persist TaskNode revision;
- create Activity item `task_changed`;
- emit Audit refs for before/after field names and safe summary, not raw hidden
  implementation payloads.

#### CRS-3. `create_task_node`

Purpose: add new executable or planning work to the active Plan.

Payload:

- title;
- intent / instructions;
- optional constraints;
- optional acceptance criteria;
- insertion position;
- source reason, such as user follow-up, execution request, or recovery.

Validation:

- active Plan exists;
- Plan state allows insertion, or command returns `needs_confirmation`;
- insertion position is stable and deterministic;
- idempotent replay does not create duplicate TaskNodes.

Effects:

- persist new TaskNode with stable identity and ordering;
- create Activity item `task_created`;
- return Plan/Task refs for focus in Main Page and Audit.

#### CRS-4. `delete_task_node`

Purpose: remove or archive a TaskNode that should no longer be part of the
contract.

Validation:

- TaskNode exists;
- TaskNode has not produced irreversible execution evidence unless the command
  is an archive/hide operation;
- destructive deletion requires explicit confirmation;
- idempotent replay returns the same archived/deleted state.

Effects:

- prefer archive/tombstone semantics over physical deletion for auditability;
- create Activity item `task_removed`;
- preserve enough refs for Audit to explain what changed.

#### CRS-5. `create_execution_task`

Purpose: convert a workspace-changing natural-language request into executable
contract work.

Validation:

- Router classified the request as workspace-changing or command-like;
- the request has enough scope to create a TaskNode or returns clarification;
- no workspace tools are invoked;
- high-risk or ambiguous requests may return `needs_confirmation`.

Effects:

- create or update executable TaskNode contract;
- optionally mark it as ready for publish/execute according to existing Plan
  lifecycle rules;
- create Activity item `task_created` or `plan_updated`;
- return `execution_request` side effect with TaskBus handoff refs only when
  the accepted path has actually been entered.

#### CRS-6. `resolve_ask` / `resolve_confirmation`

Purpose: bridge routed input to existing ASK and confirmation lifecycles.

Validation:

- active ASK or confirmation exists and belongs to the session/workspace;
- answer shape matches the expected interaction;
- expected version matches;
- repeated answers are idempotent.

Effects:

- delegate to existing ASK or confirmation command handler;
- create Activity item `ask_answered` or `confirmation_resolved`;
- return resume refs when TaskBus can continue.

### 4.6 Router Integration Rules

Runtime Input Router may dispatch a command skill only when:

1. deterministic active interaction routing applies; or
2. deterministic command phrase routing applies; or
3. selected scope plus classifier confidence is above threshold; or
4. the user explicitly chose a mode that makes the side effect unambiguous.

Router must pass `routerDecisionId` into the command envelope. The command
result must pass back enough refs for the Router response, Activity timeline,
Audit Page, and diagnostics export to agree on what happened.

The command skill should still reject invalid state even if the Router selected
the route. Router chooses intent; command skills own authority.

### 4.7 Activity, Audit, And Diagnostics

Every accepted command must produce durable user-visible evidence.

Activity requirements:

- item kind matches the product event, such as `guidance_recorded`,
  `task_changed`, `task_created`, `task_removed`, `ask_answered`, or
  `confirmation_resolved`;
- scope is Session, Plan, Task, ASK, or confirmation;
- side-effect class is explicit;
- related refs can focus the affected Plan, Task, ASK, confirmation, Audit
  record, or diagnostic export action.

Audit/diagnostic requirements:

- include command id, command kind, scope ids, result status, side-effect class,
  and redacted reason code;
- include safe before/after summaries for Plan/Task changes;
- never include secrets, provider payloads, raw prompts, raw EventStream rows,
  SQLite rows, tool args, or absolute workspace paths;
- user-authored guidance may be referenced by safe content id and may be
  redacted or truncated in diagnostics.

### 4.8 Error And Conflict Semantics

| Condition | Result status | User-facing behavior |
|---|---|---|
| Missing target Plan/Task/ASK/confirmation | `rejected` | Explain that the target no longer exists and offer refresh. |
| Version mismatch | `conflict` | Explain that the work changed and require reload or retry with latest state. |
| Unsupported route | `unsupported` | Explain that Plato cannot perform that command yet; no mutation. |
| Ambiguous side effect | `needs_confirmation` or `rejected` | Ask for confirmation or clarification before mutation. |
| Duplicate idempotency key | original status | Return original refs without duplicate effects. |
| Invalid Plan state | `rejected` or `needs_confirmation` | Explain why the current Plan state blocks the command. |

Errors must use stable reason codes. UI copy should be provided through the UI
system text registry instead of command-handler string literals.

---

## 5. Implementation Slices

### CRS-A. Command Skill Protocol

Status: implemented.

Deliver:

- internal command request envelope;
- shared command result shape;
- side-effect class mapping;
- idempotency and version guard policy;
- Activity/Audit/diagnostic descriptor contract;
- focused tests for replay, conflict, rejection, and redaction.

Acceptance:

- command protocol can return accepted, rejected, conflict,
  needs-confirmation, noop, and unsupported results;
- no command result requires the Router or UI to infer side effects from prose;
- duplicate idempotency keys do not create duplicate facts or Activity.

### CRS-B. Guidance Command

Status: implemented.

Deliver:

- `record_guidance` command;
- typed guidance fact persistence;
- Context Manager inclusion metadata;
- durable Activity item `guidance_recorded`;
- Audit/diagnostic refs;
- Router integration for guidance route.

Acceptance:

- session, Plan, and Task-scoped guidance can be recorded;
- guidance survives reload and appears in Activity;
- Context Manager can include guidance with scope and truncation metadata;
- ambiguous guidance routes remain unsupported or clarification results until
  the Router has enough confidence.

### CRS-C. ASK And Confirmation Routed Resolution

Status: implemented.

Deliver:

- routed wrappers around existing ASK answer and confirmation answer commands;
- idempotent active interaction resolution;
- Activity items `ask_answered` and `confirmation_resolved`;
- resume refs when TaskBus can continue.

Acceptance:

- explicit UI answer and routed input answer share canonical domain behavior;
- repeated answers do not double-resume work;
- invalid active interaction state returns a structured rejection.

### CRS-D. Plan/TaskNode Mutation Commands

Status: partially implemented. `patch_task_node` is implemented by delegating to
the existing versioned `update_task_node` command handler. `create_task_node`
and `delete_task_node` remain planned.

Deliver:

- `patch_task_node`;
- `create_task_node`;
- `delete_task_node` archive/tombstone path;
- version and Plan-state guards;
- confirmation handoff for destructive or high-risk changes.

Acceptance:

- Plan/TaskNode changes are visible in Main Page after reload;
- Audit can explain which contract fields changed;
- rejected/conflict states never partially mutate the contract.

### CRS-E. Execution Request Handoff

Status: planned.

Deliver:

- `create_execution_task`;
- workspace-changing request to executable TaskNode conversion;
- TaskBus handoff refs only after accepted publish/execute path;
- clarification or confirmation result when scope or risk is unclear.

Acceptance:

- workspace-changing routed input never invokes shell, file, browser, web
  search, or precision file tools directly;
- created executable work has Plan/Task refs and Activity evidence;
- high-risk ambiguity is confirm-before-mutate.

### CRS-F. Router, Activity, Audit, And Diagnostics Integration

Status: partially implemented for the implemented command set.

Deliver:

- Router command dispatch integration;
- durable Router outcome Activity;
- Audit refs for command effects;
- redacted diagnostic descriptors;
- Main Page feedback through UI system text keys.

Acceptance:

- every accepted command is replayable in the Activity timeline;
- Activity, Audit, and diagnostics agree on the command id, status, scope, and
  side-effect class;
- diagnostics export does not expose raw hidden internals.

### CRS-G. Tests And Acceptance

Status: planned.

Test matrix:

- idempotent replay for every command;
- version conflict for TaskNode mutation;
- invalid state rejection;
- missing target rejection;
- destructive command confirmation path;
- Activity projection and reload;
- Audit/diagnostic redaction;
- no direct workspace writes;
- Router happy path and unsupported path;
- real sidecar/Electron smoke for guidance, ASK, confirmation, execution
  request handoff, and no-mutation guarantees.

---

## 6. First Implementation Order

1. Implement CRS-A protocol models and focused unit tests.
2. Implement `record_guidance` persistence and idempotency.
3. Project `guidance_recorded` into Session Activity.
4. Add Audit/diagnostic refs for guidance effects.
5. Wire Runtime Input Router guidance route to `record_guidance`.
6. Add routed ASK/confirmation wrappers.
7. Implement Plan/TaskNode mutation commands.
8. Implement `create_execution_task`.
9. Add real sidecar/Electron acceptance for all P0 routes.

---

## 7. Non-Goals

- No direct file writes.
- No direct shell execution.
- No generic Router Agent with unrestricted tools.
- No public skill marketplace.
- No replacement of TaskBus.
- No MCP tool execution.
- No browser automation.
- No LLM-only state mutation.
- No public custom Agent protocol.
