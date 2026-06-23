# Local macOS WeChat Send MVP

> Status: Accepted local MVP / controlled real smoke passed
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
> [macOS Computer-Use Capability Package](macos-computer-use-package.md),
> [macOS Computer-Use Backend](macos-computer-use-backend.md),
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
  -> macOS computer-use package adapter
  -> WeChat Desktop adapter
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
2. consume `macos-computer-use` as a package dependency through a Plato adapter;
3. support WeChat Desktop as a software-specific adapter;
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
| Desktop capability boundary | `macos-computer-use-package.md`, `macos-computer-use-backend.md` |
| Tool contract | `local-computer-use-tool.md` |
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

TaskApiService.publish_task
  -> TaskBus pending task
  -> AgentLoop execution
  -> WeChatSendSkill / fixed route handler
  -> PlatoMacOSComputerUseAdapter.readiness
  -> WeChatDesktopAdapter.open_or_focus
  -> WeChatDesktopAdapter.resolve_contact
  -> WeChatDesktopAdapter.draft_message
  -> RequestConfirmationTool
  -> TaskBus waiting_for_user
  -> confirmation response
  -> action fingerprint verification
  -> WeChatDesktopAdapter.send_after_confirmation
  -> send-boundary store
  -> TaskResult / TaskError / EvidenceRef
  -> Main Page / Activity projection
```

## 6. Implementation Slices

Current implementation status:

- W0 complete: PRD slice, plan, technical design, and gap registry links exist.
- W1 complete: Plato now has an explicit macOS computer-use package adapter,
  runtime selection helper, sidecar/dev config wiring, readiness mapping, and
  fake-client tests.
- W2 complete: Plato now has a draft-only WeChat Desktop integration layer with
  typed readiness, contact resolution, draft state, fake adapter support, and
  deterministic tests. It does not send messages.
- W3 complete: WeChat send confirmation now has a stable action fingerprint,
  confirmation payload builder, and message-stream authorizer. The generic
  confirmation action can carry structured business context without changing
  default confirmation behavior.
- W4 complete: a durable SQLite send-boundary store now persists execution id,
  idempotency key, action fingerprint, confirmation id, observation refs,
  result/error refs, status transitions, restart recovery, duplicate-key
  behavior, and manual-review states.
- W5 complete: `WeChatSendExecutionService` now consumes the W3 authorizer and
  W4 send-boundary store, gates send attempts on an approved matching
  fingerprint, calls the WeChat adapter send boundary exactly once, and projects
  safe `TaskResult` / `TaskError` summaries plus `EvidenceRef` objects. The real
  adapter uses a verified input and keyboard Return submit boundary; fake
  adapter tests cover approved, rejected, mismatch, duplicate, unknown, and
  failed-send paths.
- W6 runtime wiring complete: `EmbeddedTaskApiService` can route
  `communication.wechat.send_message` through `WeChatSendRuntimeHandler`; the
  handler validates high-risk confirmation policy/capability, drafts through the
  WeChat adapter, requests confirmation, resumes the same idempotency key after
  user response, calls the W5 send service exactly once, and projects
  result/error/evidence refs. The local sidecar assembles this handler only when
  real macOS computer-use is explicitly enabled.
- Manual local WeChat smoke passed on 2026-06-22 against `文件传输助手` with a
  fresh idempotency key. The validated path is readiness -> contact resolution
  -> clear existing draft -> type exact message -> confirmation -> keyboard
  Return submit -> result/evidence query -> same-key terminal replay. No send
  button lookup is required for the accepted MVP path.

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

- dependency wiring for `macos-computer-use` in local development;
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

- W7 tests pass.
- Controlled real confirm/send-once smoke passed on 2026-06-22.

## 7. Data And State Model Additions

The implementation should introduce only the minimum product-specific models
needed for this slice:

| Model | Responsibility |
|---|---|
| `WeChatSendTaskInput` | Validated task input for contact and message. |
| `WeChatContactResolution` | Contact candidate/result summary and confidence. |
| `WeChatDraftState` | Drafted message metadata and observation ref. |
| `WeChatSendActionFingerprint` | Confirmation/idempotency identity. |
| `WeChatSendBoundary` | Durable send-boundary state. |
| `WeChatSendResultPayload` | Safe result payload for TaskResult. |
| `WeChatSendErrorPayload` | Safe error payload for TaskError. |

These models belong in Plato / Execution Plane integration code, not in the
neutral `macos-computer-use` package.

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

Automated tests:

- package adapter readiness mapping with fake package client;
- WeChat adapter fake flows:
  - missing app;
  - needs login;
  - contact missing;
  - multiple contacts;
  - contact resolved;
  - draft success;
- confirmation authorizer:
  - unresolved blocks;
  - rejected records `not_sent`;
  - mismatched fingerprint blocks;
  - approved fingerprint permits one send;
- send-boundary idempotency:
  - duplicate publish after `sent`;
  - restart after `drafted`;
  - restart after `unknown`;
- W5 service-level result/error/evidence projection.
- W6 runtime wiring and local HTTP fake path.
- W6 manual real WeChat smoke.
- Manual smoke harness fake HTTP sidecar coverage:
   - `tests/test_manual_wechat_send_smoke_script.py` verifies request contract,
    reject safety, confirm guard, reject/no-send fake HTTP path, and
    confirm/send-once fake HTTP path. The harness also performs a terminal
    same-key replay and fails unless the replay returns the same execution and
    same terminal status.
- Non-destructive local sidecar preflight:
  - 2026-06-20: `uv run python scripts/manual_wechat_send_smoke.py
    --base-url http://127.0.0.1:<sidecar-port> --preflight-only` passed against
    a temporary local sidecar with `--computer-use-backend macos` and
    `--computer-use-allowed-apps WeChat`.
  - Result: `sidecarOk=true`, `computerUseStatus="ok"`,
    `packageReadinessStatus="ready"`, `accessibilityTrusted=true`,
    `ready=true`.
  - 2026-06-20: the same preflight was rerun with
    `--evidence-output /tmp/plato-wechat-preflight.json`; the generated JSON
    reported `ready=true` and redacted raw contact/message text.
- Real WeChat confirm smoke progress:
  - 2026-06-20: controlled confirm/send-once smoke against `文件传输助手`
    reached confirmation and resumed the same idempotency key.
  - Result: readiness/open/contact resolution/draft/confirmation succeeded;
    final status was `failed` with `errorCode=wechat_send_unknown`.
  - Evidence reason: `macOS computer-use operation failed: TimeoutExpired`.
  - Terminal replay returned the same execution and same failed terminal status,
    so idempotency safety held.
  - No automatic retry was allowed before manual review and W7 hardening.
- Real WeChat confirm smoke accepted:
  - 2026-06-22: controlled confirm/send-once smoke against `文件传输助手`
    passed with keyboard Return submit.
  - Idempotency key:
    `manual-wechat-smoke-20260622-keyboard-submit-e05a-03`.
  - Execution id: `exec_c47432a39d1b5a0da94d15d16dd1827e`.
  - Confirmation id: `217fddb7310f47b4968f852734457e64`.
  - Result: `TaskResult.structuredPayload.kind=wechat_send_result`,
    `sendBoundaryStatus=sent`.
  - Evidence: `WeChat send observation` records
    `phase=keyboard_submit`, `send_method=keyboard_return`,
    `send_attempted=true`, `confirmation_required=true`, and
    `confirmed_by_user=true`.
  - Terminal replay returned the same execution and same `done` terminal status,
    so idempotency safety held.

Manual smoke:

- local macOS with Accessibility permission;
- WeChat Desktop installed and logged in;
- test contact available;
- test message explicitly safe and non-sensitive;
- operator watches the confirmation prompt before send.

Manual smoke checklist:

1. Enable real runtime config:
   - `PLATO_COMPUTER_USE_BACKEND=macos`;
   - `PLATO_COMPUTER_USE_ALLOWED_APPS=WeChat`;
   - sidecar/dev runtime uses the Python environment where
     `macos-computer-use` is importable.
2. Verify readiness before publish:
   - macOS Accessibility trusted;
   - WeChat installed, logged in, unlocked, and frontmost actions observable;
   - screenshot evidence remains disabled.
   - Optional package/adapter preflight before opening WeChat:

     ```bash
     python scripts/manual_wechat_send_smoke.py \
       --base-url http://127.0.0.1:<sidecar-port> \
       --preflight-only \
       --evidence-output /tmp/plato-wechat-preflight.json
     ```

     The preflight must report `ready=true`,
     `computerUseStatus="ok"`, `packageReadinessStatus="ready"`, and
     `accessibilityTrusted=true` before a real WeChat smoke is attempted.
3. Publish a single `communication.wechat.send_message` task with:
   - a controlled test contact;
   - non-sensitive test message text;
   - `policy.requiresHumanConfirmation=true`;
   - `policy.riskLevel=high`;
   - `policy.requiredCapability=communication.wechat_desktop_send`;
   - stable idempotency key.
   - Recommended harness command for the safe reject/no-send path:

     ```bash
     python scripts/manual_wechat_send_smoke.py \
       --base-url http://127.0.0.1:<sidecar-port> \
       --session-id <session-id> \
       --contact "<controlled-test-contact>" \
       --message "Plato Local WeChat smoke test" \
       --response reject \
       --evidence-output /tmp/plato-wechat-reject-smoke.json
     ```
4. Confirm first stage:
   - WeChat opens/focuses;
   - target contact is selected;
   - text is drafted but not sent;
   - Main Page / Activity shows waiting for confirmation.
5. Reject path:
   - reject confirmation;
   - verify boundary becomes `not_sent`;
   - verify no send action occurs.
6. Approved path:
   - run a new task with a new idempotency key;
   - use the harness only with both explicit send controls:

     ```bash
     python scripts/manual_wechat_send_smoke.py \
       --base-url http://127.0.0.1:<sidecar-port> \
       --session-id <session-id> \
       --contact "<controlled-test-contact>" \
       --message "Plato Local WeChat smoke test" \
       --response confirm \
       --allow-send \
       --evidence-output /tmp/plato-wechat-confirm-smoke.json
     ```

   - approve confirmation;
   - verify exactly one send action;
   - verify `TaskResult.kind=wechat_send_result` and evidence refs are queryable.
7. Replay guard:
   - the smoke harness automatically repeats the same POST with the same
     idempotency key after the task reaches terminal state;
   - verify `terminalReplaySameExecution=true` and
     `terminalReplayStatus` matches the terminal status;
   - verify no second send occurs.
8. Evidence retention:
   - retain the three JSON files from preflight, reject, and confirm smoke;
   - JSON evidence intentionally records only contact/message presence and
     message length, not the raw contact or raw message text;
   - use only a controlled test contact and non-sensitive message because
     WeChat UI itself remains visible during the manual smoke.

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
Harden Local macOS WeChat Send MVP error mapping after the accepted
keyboard-submit smoke.

Do not change frontend UI.
Do not bypass confirmation.
Do not auto-retry unknown or send_attempted boundaries.
Do not add remote ExecutionEnv, LAN auth, Windows, or screenshot evidence.

Required work:
1. Read local-macos-wechat-send-mvp.md and technical design.
2. Keep the accepted flow: contact resolution -> clear input -> draft ->
   confirmation -> keyboard Return submit.
3. Add focused mappings for contact/search/input failures into WeChat-specific
   error codes.
4. Preserve `wechat_send_unknown` for submit failures where side effects cannot
   be ruled out.
5. Add tests for the new failure taxonomy.
6. Do not rerun real send smoke unless an error-mapping change touches the
   real send boundary; if rerun is needed, use the local-wechat-send-smoke
   skill and a fresh idempotency key.
```
