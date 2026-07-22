# Local macOS WeChat Send MVP

> Status: Historical MVP. The repo-local WeChat runtime, deterministic
> adapter, durable send-boundary store, and old smoke scripts described here
> were retired by
> [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md).
> The active path is TaskBus / Agent loop / package-backed `wechat_desktop`
> and `computer_use` tools.
>
> Last Updated: 2026-06-22
>
> PRD:
> [Remote WeChat Message Task Via Execution Plane](../../product/remote-wechat-message-task-prd.md)
>
> Technical Design:
> [Local macOS WeChat Send MVP Technical Design](local-macos-wechat-send-mvp-technical-design.zh-CN.md)
>
> Related:
> [Local Computer-Use Tool Foundation](local-computer-use-tool.md),
> [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md),
> [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md),
> [Confirmation UI Spec](../../ux/confirmation-ui-spec.md),
> [Execution Plane Service And Task API](execution-plane-service-task-api.md),
> [ADR-0020 Execution Plane As Service / Task API Boundary](../../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)

---

## 1. Problem

The remote WeChat task PRD defines the full direction:

```text
External app
  -> Task API
  -> execution environment
  -> computer-use Agent
  -> WeChat message
  -> result / evidence
```

That target is too large for the next implementation slice because it combines
network execution, remote environment trust, desktop automation, WeChat-specific
interaction, high-risk confirmation, idempotency, and evidence.

The product needs a smaller executable proof:

```text
Local Plato sidecar
  -> local Task API / AgentLoop
  -> package-backed computer_use / wechat_desktop tools
  -> computer-use-macos / wechat-desktop-tool packages
  -> draft message
  -> confirmation-gated send
  -> result / evidence projection
```

This slice proves the core user value without taking on LAN routing or remote
worker lifecycle first.

## 2. Product Decision

Implement the first WeChat send proof as a local macOS MVP.

The MVP must:

1. run on one local macOS machine;
2. consume `computer-use-macos` and `wechat-desktop-tool` through package-backed
   Plato tools;
3. support WeChat Desktop as a semantic tool capability;
4. draft the exact message before sending;
5. require explicit confirmation before the final send action;
6. track the send boundary durably;
7. project result/error/evidence back into Main Page / Activity.

The MVP must not:

- implement remote ExecutionEnv registration;
- implement LAN auth, claim, lease, heartbeat, or remote result upload;
- implement Windows support;
- silently send external messages;
- retry an unknown send boundary automatically;
- store raw unrelated WeChat chat history.

## 3. Scope

In scope:

- `communication.wechat.send_message` local task type;
- local sidecar Task API / AgentLoop path;
- `PlatoMacOSComputerUseAdapter` over the external package;
- local feature flag / runtime config for real computer use;
- WeChat Desktop readiness checks;
- contact search, selection, and ambiguity handling;
- draft-only message preparation;
- high-risk confirmation before send;
- action fingerprint verification before send;
- send-boundary idempotency store;
- result/error/evidence projection;
- deterministic tests using fake package and fake WeChat adapter;
- manual local smoke checklist for real WeChat.

Out of scope:

- remote Control Plane deployment;
- external LAN clients;
- remote ExecutionEnv registry and claim/lease;
- callbacks/webhooks;
- public internet API;
- bulk messaging;
- generated marketing content;
- files/images/voice messages;
- screenshot evidence unless redaction is explicitly implemented;
- full Audit Page deep evidence UI.

## 4. Source-Of-Truth Hierarchy

| Layer | Source |
|---|---|
| Product requirement | `remote-wechat-message-task-prd.md`, section 6 MVP slice |
| Desktop capability boundary | `app-control-tool-package-migration.zh-CN.md`, `macos-computer-use-package.md`, `macos-computer-use-backend.md` |
| Tool contract | `local-computer-use-tool.md`, `app-control-tool-package-smoke-runbook.zh-CN.md` |
| Confirmation UX/lifecycle | `confirmation-ui-spec.md`, ASK/confirmation backend docs |
| Execution boundary | `execution-plane-service-task-api.md`, ADR-0020 |
| Result/evidence projection | existing Result Exposure Surface and Activity timeline implementation |

Implementation must not invent new UI/API behavior that conflicts with these
sources. If a missing field or state is needed, update the relevant contract
before adding runtime code.

## 5. Target Flow

```text
POST /api/v1/tasks
  taskType=communication.wechat.send_message
  input.contactDisplayName
  input.messageText
  policy.requiresHumanConfirmation=true
  policy.riskLevel=high

Router / TaskApiService
  -> TaskBus execution task
  -> Agent loop
  -> runtime skill selects app-control tools
  -> wechat_desktop tool builds package commands
  -> computer_use tool executes macOS app-control commands
  -> ToolObservation / ToolEvent evidence
  -> product-level confirmation policy when submit is requested
  -> idempotency key / execution result projection
  -> TaskResult / TaskError / EvidenceRef
  -> Main Page / Activity projection
```

## 6. Implementation Slices

Current implementation status:

- This document is retained as historical MVP context.
- The deterministic W1-W7 implementation described below was retired by
  [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md).
- The active path publishes `communication.wechat.send_message` to TaskBus and
  lets the Agent loop use package-backed `wechat_desktop` / `computer_use`
  tools.
- The old `WeChatSendRuntimeHandler`, repo-local WeChat adapter,
  send-boundary store, helper server/app builders, and old manual smoke scripts
  are deleted from active source and tests.
- The 2026-06-22 deterministic-runtime smoke remains historical evidence only;
  current acceptance requires package-backed smoke evidence from
  [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md).

### W0. Contract And Plan Closure

Deliverables:

- update PRD with local MVP slice;
- create this implementation plan;
- create the technical design;
- link the feature from the gap registry and feature plan index.

Acceptance:

- implementation scope is clear before code starts;
- local MVP is separate from remote ExecutionEnv work;
- high-risk confirmation and send-boundary idempotency are explicit.

### W1. macOS Package Adapter In Plato

Goal: make Plato consume the package through a narrow adapter.

Deliverables:

- dependency wiring for `app-control-protocol`, `computer-use-macos`, and
  `wechat-desktop-tool` in local development;
- `PlatoMacOSComputerUseAdapter`;
- feature flag/runtime config;
- readiness mapping into `ComputerUseObservation`;
- fake package client tests;
- TextEdit manual smoke retained as package-level proof, not WeChat proof.

Acceptance:

- package unavailable or disabled falls back to disabled backend;
- missing Accessibility returns a setup/readiness block;
- no WeChat behavior is implemented in this slice.

### W2. WeChat Draft-Only Adapter

Goal: prove the app-specific adapter can locate a contact and prepare a draft
without sending.

Deliverables:

- `WeChatDesktopAdapter`;
- allowlisted app identity for WeChat Desktop;
- readiness statuses:
  - installed / missing;
  - logged in / needs user;
  - observable / not observable;
  - unlocked / needs user;
- contact search operation;
- contact resolution model;
- ambiguity and missing-contact ASK outcomes;
- draft message operation;
- fake adapter tests.

Acceptance:

- valid contact + message drafts text without sending;
- ambiguous or missing contact does not draft/send;
- no send operation exists in this slice.

### W3. Confirmation-Gated Send

Goal: connect the high-risk send action to durable confirmation.

Deliverables:

- action fingerprint based on execution id, idempotency key, contact summary,
  message hash, app identity, and draft observation id;
- confirmation request payload;
- confirmation resolution authorizer;
- context passthrough on `RequestConfirmationAction` so the actionable message
  carries the WeChat send fingerprint.

Implemented across W4/W5:

- send-after-confirmation operation;
- `not_sent` terminal result projection.

Acceptance:

- unresolved confirmation blocks send;
- approval authorizes only the matching action fingerprint;
- `approve_session` is recorded only and does not bypass future sends.
- reject/cancel is detected by the authorizer and projected as `not_sent`
  through the durable send-boundary store.

### W4. Send-Boundary Idempotency

Goal: avoid duplicate sends across retries, restarts, and repeated idempotency
keys.

Deliverables:

- durable send-boundary store;
- statuses:
  - `not_started`;
  - `drafted`;
  - `confirmation_requested`;
  - `confirmed`;
  - `send_attempted`;
  - `sent`;
  - `not_sent`;
  - `unknown`;
- retry rules;
- duplicate publish behavior;
- restart recovery tests.

Acceptance:

- after `sent`, same idempotency key does not send again;
- after `unknown`, automatic retry is blocked;
- after `drafted` but before confirmation, task can safely recover to
  confirmation;
- after `not_sent`, task is terminal unless user starts a new task.

### W5. Send Execution / Result / Error / Evidence Projection

Goal: perform the confirmation-authorized send exactly once and make the user
and future audit surfaces understand what happened.

Deliverables:

- send-after-confirmation operation that consumes W3 authorizer and W4
  send-boundary store;
- `TaskResult` summary for successful send;
- `TaskError` summary for safe failure;
- evidence refs for:
  - task request;
  - readiness observations;
  - contact resolution summary;
  - draft observation;
  - confirmation event;
  - send result;
- Activity entries;
- Main Page final outcome projection.

Acceptance:

- success/failure is user-readable;
- evidence does not expose unrelated raw chat content;
- service-level execution records progress, confirmation, and final
  result/error refs for projection surfaces.

### W6. Runtime Wiring, Local Smoke, And Release Notes

Goal: wire the W1-W5 components into the local task execution path and validate
one real local macOS path.

Implemented deliverables:

- runtime routing from `communication.wechat.send_message` to
  `WeChatSendExecutionService`;
- fake integration tests through the local Task API / embedded Execution Plane
  HTTP path;
- durable boundary reuse across same-request idempotency replay;
- confirmation-gated resume path;
- safe result/error/evidence projection through existing Execution Plane query
  surfaces;
- sidecar assembly with opt-in real macOS computer-use runtime.

Completed W7 deliverables:

- deterministic verified-input + keyboard Return submit in the WeChat adapter;
- input clearing before typing a fresh draft;
- send observation metadata with `phase=keyboard_submit`,
  `send_method=keyboard_return`, and `send_attempted=true`;
- Plato adapter preservation of failure metadata for failed/unknown boundaries.

Pending deliverables:

- release note documenting real-device limitations after smoke;
- operator setup notes for Accessibility and WeChat readiness.

Acceptance:

- automated fake path proves:
  - accept task through local Task API / HTTP transport;
  - draft message without sending;
  - request confirmation;
  - replay same idempotency key after confirmation;
  - send once;
  - expose result/evidence refs.
- real-device progress already verified:
  - open WeChat;
  - find one test contact;
  - draft message;
  - ask confirmation;
  - approve.
- real-device acceptance:
  - send once;
  - show result/evidence;
  - same-key terminal replay returns the same execution and does not send twice.
- runtime path preserves confirmation, send-boundary idempotency, and
  unknown/manual-review safeguards.

### W7. Verified Input, Keyboard Submit, And Error Taxonomy

Goal: avoid brittle WeChat send-button lookup for the local MVP and make the
final send boundary deterministic enough to safely classify failures.

Implemented deliverables:

- bounded contact resolution and message input focus verification before
  typing;
- clear existing input with Select All + Delete before drafting the smoke
  message;
- final submit uses keyboard Return after confirmation;
- explicit metadata:
  - `phase`;
  - `send_method`;
  - `send_attempted`;
  - `input_focus_verified`;
  - `input_content_verified`;
- no raw coordinate fallback;
- no send-button click dependency;
- no raw chat transcript persistence.

Implemented Plato-side deliverables:

- preserve package metadata through `MacOSComputerUseBackend`;
- keep existing send-boundary rule: `unknown` blocks automatic retry.

Deferred downstream mapping:

- richer WeChat-specific error code mapping for contact/search/input failures;
- optional send-button lookup may be revisited later if keyboard Return becomes
  unreliable on a future WeChat version.

Acceptance:

- tests verify keyboard Return submit does not depend on `click at` or
  `AXFocusedUIElement` scanning;
- tests verify input clearing before typing;
- a controlled real confirm/send-once smoke passes.

Status:

- Historical W7 tests passed for the retired deterministic runtime.
- The controlled real confirm/send-once smoke from 2026-06-22 is historical
  evidence only. Current acceptance requires package-backed Smoke A/B/C/D from
  [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md).

## 7. Data And State Model Additions

The active package-backed implementation should introduce only the minimum
product-specific models needed for this slice:

| Model | Responsibility |
|---|---|
| `WeChatSendTaskInput` | Validated task input for contact and message. |
| `ToolCommand` | Package-neutral command request emitted by `wechat-desktop-tool`. |
| `ToolObservation` | Package-neutral action result, failure kind, and safe metadata. |
| `ToolEvent` | Optional step-level runtime trace for app-control execution. |
| Idempotency key | Product/API-level duplicate-send boundary. |
| Evidence ref | Safe reference to observation JSON or runtime logs. |

Product policy, confirmation state, and idempotency belong in Plato / TaskBus
integration code. Low-level command construction and observation schemas belong
in `app-control-protocol`, `computer-use-macos`, and `wechat-desktop-tool`.

## 8. Risk And Safety Rules

Mandatory rules:

1. WeChat send is always high-risk.
2. `type_text` can only draft. It cannot imply send.
3. Send requires a separate action and durable confirmation.
4. Confirmation must bind to action fingerprint.
5. Unknown send status blocks automatic retry.
6. Contact ambiguity blocks execution.
7. Raw chat transcript and unrelated UI tree are not persisted by default.
8. Screenshot evidence is disabled until redaction is designed.
9. WeChat credentials are never requested or stored.
10. Local MVP is not a production business rollout.

## 9. Test Strategy

Current package-backed tests:

- fake `AppControlClient` / `ToolObservation` coverage for the generic
  `computer_use` adapter;
- fake package-client coverage for `wechat_desktop` command mapping,
  observation mapping, failure preservation, and redacted runtime logs;
- Router coverage for publishing `communication.wechat.send_message` through
  TaskBus / Execution Plane instead of creating a special deterministic runtime
  execution;
- `tests/test_manual_wechat_desktop_tool_smoke_script.py` verifies the
  replacement smoke script's no-submit path, explicit submit guard, and
  `--allow-submit --confirm-submit SEND` submit path without opening WeChat.

Current manual smoke:

- use [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md);
- use `scripts/manual_wechat_desktop_tool_smoke.py`;
- Smoke A validates package import / CLI contract without opening WeChat;
- Smoke B opens WeChat, focuses `文件传输助手`, drafts a message, and observes
  without submitting;
- Smoke C requires separate explicit authorization and both `--allow-submit`
  and `--confirm-submit SEND`;
- Smoke D reuses the same idempotency key to verify no duplicate send.

## 10. Open Decisions

1. Exact WeChat app identity: localized app name, bundle id, or both.
2. Whether future business pilots need dedicated test accounts beyond
   `文件传输助手`.
3. Whether future hardening needs a stronger post-submit UI signal. MVP
   currently defines `sent` as "confirmed keyboard Return submit completed" and
   treats WeChat delivery receipt as out of scope.
4. Whether observation-only evidence is sufficient for the first demo.
5. Whether screenshot redaction should become a required precondition before
   business pilot.
6. Whether local API needs auth before this MVP or can remain trusted dev-only.

## 11. Recommended Next Task

```text
Use the product-workflow-gate skill first.

Task:
Run the package-backed Local macOS WeChat smoke and archive evidence.

Do not change frontend UI.
Do not use retired scripts or repo-local helper/runtime endpoints.
Do not run submit without explicit authorization for that run.
Do not auto-retry unknown submit or send_attempted boundaries.
Do not add remote ExecutionEnv, LAN auth, Windows, or screenshot evidence.

Required work:
1. Read app-control-tool-package-smoke-runbook.zh-CN.md.
2. Run Smoke A.
3. Run Smoke B against `文件传输助手` and archive evidence JSON.
4. After explicit authorization, run Smoke C with a fresh idempotency key.
5. Run Smoke D with the same idempotency key and verify no duplicate message.
6. Update the migration plan/runbook with the actual evidence paths and any
   blocker.
```
