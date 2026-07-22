# Computer-Use Runtime Observability And Execution Boundary

> Status: implemented on branch / pending review
>
> Last Updated: 2026-06-30
>
> Related:
> [Execution Plane Service And Task API](execution-plane-service-task-api.md),
> [Execution Plane Service And Task API Technical Design](execution-plane-service-task-api-technical-design.zh-CN.md),
> [Local macOS WeChat Send MVP](local-macos-wechat-send-mvp.md),
> [Local macOS WeChat Send MVP Technical Design](local-macos-wechat-send-mvp-technical-design.zh-CN.md),
> [Deprecated Plato Computer Use Helper.app Technical Design](plato-computer-use-helper-app-technical-design.zh-CN.md),
> [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md),
> [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md),
> [ADR-0020 Execution Plane As Service / Task API Boundary](../../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)

---

## 1. Decision Summary

Computer-use execution needs better debug visibility, but the fix should not
turn every low-level tool call into user-facing MessageBus activity.

The current package-backed direction is:

1. Keep `ExecutionEnv` as a capability/readiness description, not as an
   app-specific runtime implementation.
2. Treat TaskBus + Agent loop as the execution system implementation.
3. Treat WeChat as a package-backed tool capability, not as a dedicated
   `WeChatSendRuntime`.
4. Add structured logs around runtime actions, observations, computer-use API
   calls, failures, and redacted evidence.
5. Project only selected user-facing summaries to Conversation / Activity.

This means:

```text
TaskRequest(task_type="communication.wechat.send_message")
  -> TaskBus
  -> Agent loop
  -> EnvRegistry validates local app-control capability
  -> Agent loop calls wechat_desktop / computer_use tools
  -> Tool adapters write structured logs and execution evidence
  -> Product projection writes only user-facing Conversation/Activity entries
```

## 1.1 Implementation Status

Implemented in the current branch:

- Structured `runtime_action` and `runtime_observation` records for
  package-backed `wechat_desktop_tool` actions.
- Structured `computer_use_api` records at the `computer-use-macos`
  package adapter boundary.
- Redaction-safe hashes/counts for message text and idempotency keys.
- `local_macos_app_control` execution environment identity when computer-use is
  enabled.
- Fail-closed routing for `communication.wechat.send_message` when no
  package-backed app-control capability can satisfy the task.
- Diagnostic bundle coverage for runtime/computer-use records without helper
  tokens or raw message bodies.

Still not implemented in this slice:

- Remote ExecutionEnv registration, claim, lease, or log shipping.
- UI log viewer or Settings-level runtime log browsing.
- Full physical separation into `runtime_action.jsonl`,
  `runtime_observation.jsonl`, and `computer_use_api.jsonl`; records are typed
  inside the existing `runtime.jsonl` category.

## 2. Problem

Recent local WeChat send testing exposed three distinct gaps:

1. **Runtime debug gap.**
   The package-backed WeChat tool path can fail during readiness, helper
   routing, contact focus, draft, keyboard submit, or observation, but the
   debug trail is spread across tool observations, task events, sidecar logs,
   and UI projection.

2. **Computer-use API debug gap.**
   Helper/API failures need phase, operation, timeout, `failure_kind`,
   stderr/reason where safe, and request/response identity. Without this, a
   user only sees "capability unavailable" while the underlying reason may be
   helper identity, Accessibility, endpoint discovery, WeChat readiness, or
   contact resolution.

3. **Boundary ambiguity.**
   A WeChat send request should not be treated as a generic Default Agent task
   when a concrete task type and tool capability exist. The execution
   environment should answer "where and with which capabilities can this run";
   the Agent loop and selected tools should answer "how this task runs".

## 3. Goals

- Make `communication.wechat.send_message` Agent/tool execution diagnosable
  from session logs and execution evidence.
- Make computer-use helper/API calls diagnosable without exposing unsafe raw UI
  state, helper tokens, screenshots, or full chat history.
- Keep MessageBus user-facing and avoid a raw tool-call firehose in
  Conversation.
- Define a thin Product 1.0 `ExecutionEnv` / Agent-tool boundary that can later
  support remote app-control environments.
- Preserve the package-backed local helper/app-control path and avoid new
  service extraction in this slice.

## 4. Non-Goals

- No remote ExecutionEnv registration, claim, lease, heartbeat, or scheduling.
- No Windows UI Automation.
- No new UI log viewer.
- No automatic TCC permission grant.
- No screenshot evidence expansion.
- No app-specific execution environment such as `wechat_env`.
- No raw helper token, full Accessibility tree, full chat history, or
  unredacted long message body in logs.
- No requirement that every tool call become a MessageBus event.

## 5. Boundary Model

### 5.1 ExecutionEnv

`ExecutionEnv` represents **where** work can run and which capabilities are
currently available.

For Product 1.0 local computer-use, use a general app-control env identity:

```text
env_id: local_macos_app_control
display_name: Local macOS App Control
status: online | disabled | degraded | offline
capabilities:
  - app_control.macos.accessibility
  - computer_use.macos
  - communication.wechat_desktop_send
tool_pool:
  - computer_use
  - wechat_desktop
```

Rules:

- WeChat is not the environment.
- The helper app is part of the environment readiness, not the task type.
- If `communication.wechat_desktop_send` is unavailable, the request fails
  before attempting a send side effect.
- Future LAN/remote environments can register the same capability with a
  different `env_id`.

### 5.2 Agent/tool runtime

The Agent loop and tools represent **how** a task type is executed once an
environment can support it.

For Product 1.0:

```text
task_type: communication.wechat.send_message
runtime log value: wechat_desktop_tool
required_capability: communication.wechat_desktop_send
computer-use backend: helper | direct | fake/scripted
```

Rules:

- The runtime skill and Agent loop own sequencing: readiness, focus contact,
  draft, product authorization when policy requires it, submit, observation,
  and terminal result/error mapping.
- The `wechat_desktop` tool owns package command mapping and tool observation
  conversion. It does not decide product intent.
- Generic workspace-only execution should not be used as a fallback for this
  task type.
- If package-backed app-control capability is unavailable, fail closed with
  structured error evidence and a Router reply.

### 5.3 Adapter / API

Adapter/API boundaries own concrete operations:

```text
Agent loop
  -> wechat_desktop tool
  -> wechat-desktop-tool package
  -> app-control-protocol ToolCommand / ToolObservation / ToolEvent
  -> computer-use-macos direct/helper backend
  -> macOS Accessibility / app-control APIs
```

The adapter/API must log safe request/response metadata for every bounded
operation it performs.

## 6. Logging Sinks

### 6.1 Session Logs

Session logs are the primary debug sink:

```text
.plato/sessions/<session_id>/logs/
```

Use structured JSONL records so diagnostics can later export them safely.

Recommended categories:

```text
runtime_action.jsonl
runtime_observation.jsonl
computer_use_api.jsonl
```

If adding files is too disruptive in the first implementation, use existing
logging manager categories with explicit `record_type` values. The record
schema below remains the contract.

### 6.2 Execution Evidence

Execution evidence remains the audit-worthy, queryable record for product
state:

- result summary;
- error summary;
- safe tool observation;
- send-boundary status;
- evidence refs.

Evidence is durable and product-queryable. It must be safe to show in Audit or
diagnostic bundles after redaction.

### 6.3 MessageBus / Conversation

MessageBus should receive only user-facing projection:

- user input;
- Router interpretation summary;
- Router reply or execution error summary;
- confirmation / ASK;
- task result/error summary;
- important state transitions.

MessageBus should not receive every helper request, AX lookup, contact
candidate, text insertion observation, or retry probe.

## 7. Runtime Log Record Schema

Every runtime action/observation record should include:

```json
{
  "schema": "plato.runtime_observability.v1",
  "recordType": "runtime_action",
  "timestamp": "2026-06-27T00:00:00Z",
  "sessionId": "9302df9b",
  "workspaceId": "4ad94d3921ee285b",
  "taskId": "61559d4a25e84644aa210ab6a93cdbf1",
  "executionId": "exec_...",
  "taskType": "communication.wechat.send_message",
  "runtime": "wechat_desktop_tool",
  "envId": "local_macos_app_control",
  "requiredCapability": "communication.wechat_desktop_send",
  "phase": "command.dispatch",
  "operation": "focus_contact",
  "actionId": "act_...",
  "attempt": 1,
  "status": "ok",
  "success": true,
  "durationMs": 312,
  "failureKind": null,
  "errorCode": null,
  "safeSummary": "WeChat Desktop focus_contact command dispatched.",
  "evidenceId": "ev_...",
  "confirmationId": null,
  "idempotencyKeyHash": "sha256:...",
  "messageHash": "sha256:...",
  "redaction": {
    "message": "hash_only",
    "contact": "safe_display_name",
    "accessibilityTree": "not_logged",
    "screenshot": "not_logged"
  }
}
```

Required fields:

- `schema`
- `recordType`
- `timestamp`
- `sessionId`, when available
- `taskId`, when available
- `executionId`, when available
- `taskType`
- `runtime`
- `envId`
- `requiredCapability`
- `phase`
- `operation`
- `status`
- `success`
- `safeSummary`

Recommended fields:

- `workspaceId`
- `actionId`
- `observationId`
- `attempt`
- `durationMs`
- `timeoutSeconds`
- `failureKind`
- `errorCode`
- `errorMessage`
- `recoveryHint`
- `evidenceId`
- `confirmationId`
- `sendBoundaryStatus`
- `idempotencyKeyHash`
- `messageHash`

## 8. Computer-Use API Log Record Schema

Computer-use API records should describe bounded operation calls without
leaking unsafe payloads:

```json
{
  "schema": "plato.runtime_observability.v1",
  "recordType": "computer_use_api",
  "timestamp": "2026-06-27T00:00:00Z",
  "backend": "helper",
  "helperEndpointId": "manifest:/path/to/helper-endpoint.json",
  "helperBundleId": "com.taskweavn.plato.computer-use-helper.dev",
  "helperVersion": "0.1.0",
  "operation": "wechat.draft_message",
  "phase": "draft_message",
  "requestId": "req_...",
  "status": "failed",
  "success": false,
  "durationMs": 5000,
  "timeoutSeconds": 5,
  "failureKind": "contact_not_found",
  "errorCode": "wechat_contact_resolution_failed",
  "errorMessage": "WeChat contact could not be uniquely resolved.",
  "recoveryHint": "Open WeChat and verify the contact is searchable.",
  "clickAttempted": false,
  "sendAttempted": false,
  "metadata": {
    "targetApp": "WeChat",
    "contactDisplayName": "文件传输助手",
    "messageChars": 2
  },
  "redaction": {
    "helperToken": "not_logged",
    "rawResponseBody": "not_logged",
    "stdout": "not_logged",
    "stderr": "safe_excerpt_only"
  }
}
```

Rules:

- Log request/response identity, operation, phase, duration, status, and safe
  error details.
- Preserve `failure_kind`, `phase`, `click_attempted`, and `send_attempted`
  from helper/package results.
- Log safe stderr/reason excerpts only when they do not contain secrets or raw
  UI contents.
- Do not log helper auth tokens.
- Do not log full HTTP bodies by default.

## 9. WeChat Tool Phases

The package-backed tool path should emit at least one action and one
observation around each major command phase:

| Phase | Meaning | Terminal risk |
|---|---|---|
| `command.dispatch` | Agent/tool adapter dispatched a package command. | depends on operation |
| `command.observe` | Package observation was mapped into Plato evidence. | depends on operation |
| `open_wechat` | Open/focus WeChat. | app side effect only |
| `focus_contact` | Search/focus the target contact. | no send side effect |
| `draft_message` | Insert draft text. | draft side effect |
| `observe_current_chat` | Observe current chat state. | no send side effect |
| `read_visible_messages` | Read bounded visible messages. | privacy risk |
| `submit_draft` | Submit the current draft. | external send side effect |
| `send_message` | Package one-shot send command, if deliberately used. | external send side effect |
| `failure` | Map tool/helper/package failure. | depends on operation |

Unknown send boundary remains special:

- `unknown` means an external side effect might have happened but could not be
  verified.
- Do not auto-retry `unknown`.
- Require explicit user action or operator investigation.

## 10. Redaction Policy

Allowed in logs:

- task type;
- phase and operation;
- contact display name when explicitly provided by the user;
- message character count;
- message hash;
- idempotency key hash;
- helper bundle id/path/version;
- safe failure kind/code/message;
- safe recovery hint;
- short safe stderr excerpt.

Not allowed by default:

- helper token;
- full message body for long content;
- full chat history;
- full Accessibility tree;
- screenshots;
- clipboard contents;
- raw HTTP request/response body;
- private account identifiers unless explicitly approved.

For the current MVP, short user-specified smoke messages may appear in
Conversation because the user typed them there. Runtime debug logs should still
prefer message hashes and character counts.

## 11. Implementation Slices

### Slice A: WeChat tool structured logs

Status: implemented.

- Add a small runtime logger helper used by the package-backed
  `wechat_desktop` tool wrapper.
- Emit runtime action/observation records for each package command.
- Include `execution_id`, `task_id`, `task_type`, `runtime`, `phase`,
  `status`, `failure_kind`, `evidence_id`, safe package event summaries, and
  idempotency metadata.
- Unit-test success and unknown failure records.

### Slice B: Computer-use API structured logs

Status: implemented.

- Add request/response/error logging in the helper backend/client boundary.
- Preserve helper/package fields: `failure_kind`, `phase`, `click_attempted`,
  `send_attempted`, `timeout_seconds`, and safe stderr/reason.
- Test redaction of helper token and raw response body.

### Slice C: Routing boundary hardening

Status: implemented.

- Ensure `communication.wechat.send_message` is routed only through the
  package-backed TaskBus/Agent/tool path.
- If no environment/tool path can satisfy `communication.wechat_desktop_send`,
  return a structured `capability_not_available` error and write a Router
  reply.
- Do not fall back to a generic workspace-only task for this task type.

### Slice D: Diagnostics bundle descriptor

Status: implemented through existing runtime log summaries.

- Add diagnostic descriptors for runtime/computer-use logs.
- Export redacted records only.
- Keep screenshots and raw AX trees excluded.

### Slice E: Naming cleanup

Status: implemented for local env identity.

- Document and, if needed, rename local computer-use env display identity to
  `local_macos_app_control`.
- Keep task type and tool app-specific:
  `communication.wechat.send_message` / `wechat_desktop`.

## 12. Acceptance Criteria

- A controlled WeChat send smoke produces a readable phase-by-phase runtime
  trail without requiring raw screenshots or full AX dumps.
- A helper/API failure exposes operation, phase, `failure_kind`, timeout, and
  safe recovery hint in logs/evidence.
- A capability mismatch fails before side effects and projects a user-readable
  Router reply.
- MessageBus remains readable and does not receive raw tool-call spam.
- `communication.wechat.send_message` is not executed as a generic
  workspace-only fallback task.
- Logs are safe for diagnostic export after redaction.

## 13. Open Questions

- Should new log categories be physical files
  (`runtime_action.jsonl`, `runtime_observation.jsonl`,
  `computer_use_api.jsonl`) or typed records in existing category files?
- Should Settings expose a "download runtime debug bundle" action, or should
  this remain under the existing diagnostic bundle only?
- How should remote app-control environments report logs back to the central
  Execution Plane in Product 1.1?
- Should `ExecutionEnv` health be stored durably or recomputed from helper
  readiness at startup for Product 1.0?

## 14. Product 1.0 Recommendation

Keep the implementation deliberately narrow:

1. Add logs first.
2. Harden the routing boundary second.
3. Do not introduce remote scheduling yet.
4. Do not make WeChat an environment.
5. Do not connect all tool logs to MessageBus.

This gives enough visibility to debug local app-control tasks while keeping the
future service boundary clean.
